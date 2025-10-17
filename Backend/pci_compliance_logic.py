import os
import re
import json
import pandas as pd
import io
from langchain_google_genai import ChatGoogleGenerativeAI
import chromadb
from sentence_transformers import SentenceTransformer

# --- CONFIGURATION ---
PCI_DATA_FILE = "pci_data.json"
DB_PATH = "pci_vector_db"
COLLECTION_NAME = "pci_requirements"

# --- Global objects ---
print("Loading embedding model for search...")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
print("Connecting to vector database...")
chroma_client = chromadb.PersistentClient(path=DB_PATH)
collection = chroma_client.get_collection(name=COLLECTION_NAME)

def load_pci_data() -> dict:
    if not os.path.exists(PCI_DATA_FILE): return None
    with open(PCI_DATA_FILE, 'r', encoding='utf-8') as f: return json.load(f)

def clean_observation(text: str) -> str:
    cleaned_text = re.split(r'\bAction Required\b', text, flags=re.IGNORECASE)[0]
    cleaned_text = re.sub(r'^\s*Observation:\s*', '', cleaned_text, flags=re.IGNORECASE)
    return cleaned_text.strip()

def get_expanded_keywords(observation: str, model) -> list:
    print("🧠 Step 1/3: Expanding keywords...")
    prompt = f"Based on the following PCI DSS observation, list up to 10 relevant requirement numbers and technical keywords. Return only a comma-separated list.\n\nObservation: \"{observation}\"\nKeywords:"
    try:
        response = model.invoke(prompt)
        keywords = [k.strip() for k in response.content.replace("*", "").split(',') if k.strip()]
        print(f"✅ Expanded keywords: {', '.join(keywords)}")
        return keywords
    except Exception:
        print("   ⚠️ Could not expand keywords, using basic search.")
        return list(set(re.findall(r'\b\w{4,}\b', observation.lower())))

def find_hybrid_context(pci_data: dict, observation: str, keywords: list, top_k=5) -> str:
    print("🔎 Step 2/3: Performing hybrid search...")
    query_embedding = embedding_model.encode([observation])
    vector_results = collection.query(query_embeddings=query_embedding.tolist(), n_results=top_k)
    vector_ids = set(vector_results['ids'][0])
    keyword_ids = set()
    for req_num, req_text in pci_data.items():
        if any(keyword.lower() in req_num.lower() or keyword.lower() in req_text.lower() for keyword in keywords):
            keyword_ids.add(req_num)
    combined_ids = vector_ids.union(keyword_ids)
    if not combined_ids: return "No relevant requirements could be found."
    relevant_texts = [f"--- From Requirement {req_num} ---\n{pci_data[req_num]}" for req_num in combined_ids]
    print(f"✅ Found {len(relevant_texts)} relevant requirement section(s) via hybrid search.")
    return "\n\n".join(relevant_texts)

def _get_verified_requirement(context: str, observation: str, model) -> str:
    print("🔍 Step 3a/3b: Verifying the most relevant requirement...")
    prompt = f"""
    You are a meticulous PCI DSS compliance analyst. Your task is to identify the single most relevant PCI DSS requirement number that directly addresses the issue in the observation, based *only* on the provided context.
    Respond with ONLY the single requirement number (e.g., "3.4.1" or "12.5.2").

    --- Context from PCI DSS v4.0.1 ---
    {context}
    --- End of Context ---

    Observation: "{observation}"

    The single most relevant requirement number is:
    """
    try:
        response = model.invoke(prompt)
        verified_req_num = response.content.strip()
        print(f"✅ Verified requirement: {verified_req_num}")
        return verified_req_num
    except Exception as e:
        print(f"   ⚠️ Could not verify requirement, proceeding with full context. Error: {e}")
        return None

# --- THIS IS THE FULLY CORRECTED FUNCTION ---
def get_structured_recommendation(pci_data: dict, context: str, observation: str, model, verified_req_num: str) -> str:
    final_context = context
    # Ensure the final context is ONLY the verified requirement if it exists
    if verified_req_num and verified_req_num in pci_data:
        final_context = f"--- From Requirement {verified_req_num} ---\n{pci_data[verified_req_num]}"

    print("🧠 Step 3b/3b: Generating structured recommendations with final, verified logic...")
    prompt = f"""
    You are an expert compliance auditor. Your task is to provide a structured analysis of the observation.
    Based *only* on the provided context, you must provide a four-part response using the exact headings.

    **Heading 1: "Title:"**
    Provide a short, descriptive title for the finding.

    **Heading 2: "Category:"**
    Classify the finding into ONE category: Network Security, Application Security, Server & Desktop Security, Physical Security, or Information Security.

    **Heading 3: "Recommendation:"**
    Write the recommendation content.

    **Heading 4: "Required Actions:"**
    Provide a list of required action items.

    ---
    **CRITICAL INSTRUCTION FOR 'Recommendation':**
    Your recommendation MUST be based on PCI DSS Requirement {verified_req_num if verified_req_num else "identified in the context"}. You must explicitly cite this requirement number in your response.
    ---

    **LOGIC HIERARCHY FOR 'Recommendation' and 'Required Actions':**
    1.  **Internal Policy Violation:** If the observation mentions a stricter "internal policy," base your findings on that, and DO NOT mention PCI DSS in the recommendation.
    2.  **Documentation Finding:** If the issue is incomplete/inaccurate documentation (per 12.5.1/12.5.2), focus the recommendation on keeping documentation current and the actions on fixing the specific document.
    3.  **Significant Change:** If the observation describes a change to the environment, the recommendation must cite the need for re-validation (e.g., Req 11.3.1.3, 11.4.2), and the actions must include the mandatory VAPT/change ticket items.
    4.  **Standard Finding:** For all other issues, apply the rule from the primary requirement directly.
    ---

    **FORMATTING RULES:**
    - For 'Required Actions', use a standard numbered list (e.g., "1.", "2.").
    - Do not add any preamble or markdown like '**' around the headings.
    ---

    **Context from PCI DSS v4.0.1:**
    {final_context}

    **Observation:** "{observation}"

    **Your four-part response:**
    """
    try:
        return model.invoke(prompt).content.strip()
    except Exception as e:
        return f"Title: Error\nCategory: Error\nRecommendation: An error occurred during analysis.\nRequired Actions: 1. {e}"


def _format_as_html_fragment(report_data: list, original_filename: str) -> str:
    html_findings = f"<h1>PCI DSS Gap Analysis Report</h1><p><strong>Source File:</strong> {original_filename}</p>"
    for i, finding in enumerate(report_data):
        actions_html = "".join([f"<li>{action.strip()}</li>" for action in finding['Actions'].split('\n') if action.strip()])
        html_findings += f"""
        <div class="finding-card">
            <h2>Finding #{i + 1}: {finding['Title']}</h2>
            <p><strong>Category:</strong> {finding['Category']}</p>
            <h3>Observation:</h3>
            <p class="observation-text">{finding['Original Observation']}</p>
            <h3>Recommendation:</h3>
            <p>{finding['Recommendation']}</p>
            <h3>Required Actions:</h3>
            <ol>{actions_html}</ol>
        </div>
        """
    return html_findings

def run_analysis_on_file(file_stream, filename: str, output_format: str = "excel"):
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key: raise ValueError("GOOGLE_API_KEY environment variable not set.")
        model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key)
    except Exception as e:
        raise ConnectionError(f"Error connecting to Google API: {e}")

    pci_data = load_pci_data()
    if not pci_data: raise FileNotFoundError(f"Error: '{PCI_DATA_FILE}' not found.")

    try:
        buffer = io.BytesIO(file_stream.read())
        excel_sheets = pd.read_excel(buffer, sheet_name=None)
    except Exception as e:
        raise ValueError(f"Error reading Excel file: {e}")

    report_data = []
    print("\n🚀 Starting analysis...")
    for sheet_name, df in excel_sheets.items():
        obs_column = 'Description' if 'Description' in df.columns else 'Observation'
        for index, row in df.iterrows():
            original_observation = str(row.get(obs_column, ''))
            if pd.isna(row.get(obs_column)) or not original_observation.strip(): continue

            print(f"\n--- Processing Observation #{index + 2} from '{sheet_name}'... ---")
            observation = clean_observation(original_observation)
            
            keywords = get_expanded_keywords(observation, model)
            context = find_hybrid_context(pci_data, observation, keywords)
            
            # This is the full verification chain
            verified_req_num = _get_verified_requirement(context, observation, model)
            structured_response = get_structured_recommendation(pci_data, context, observation, model, verified_req_num)

            try:
                # Use more robust parsing
                title_match = re.search(r"Title:(.*?)Category:", structured_response, re.DOTALL | re.IGNORECASE)
                category_match = re.search(r"Category:(.*?)Recommendation:", structured_response, re.DOTALL | re.IGNORECASE)
                recommendation_match = re.search(r"Recommendation:(.*?)Required Actions:", structured_response, re.DOTALL | re.IGNORECASE)
                actions_match = re.search(r"Required Actions:(.*)", structured_response, re.DOTALL | re.IGNORECASE)

                title = title_match.group(1).strip() if title_match else "N/A"
                category = category_match.group(1).strip() if category_match else "N/A"
                recommendation = recommendation_match.group(1).strip() if recommendation_match else "N/A"
                actions_text = actions_match.group(1).strip() if actions_match else "N/A"
                
                report_data.append({"Title": title, "Category": category, "Original Observation": original_observation, "Recommendation": recommendation, "Actions": actions_text})
            
            except Exception as e:
                print(f"   ⚠️ Could not parse structured response. Error: {e}. Raw Response:\n{structured_response}\n---")
                report_data.append({"Title": "Parsing Error", "Category": "Error", "Original Observation": original_observation, "Recommendation": "Failed to parse the AI's response.", "Actions": f"Error: {e}"})

    if not report_data:
        report_data.append({"Title": "No Findings", "Category": "N/A", "Original Observation": "No valid observations were found.", "Recommendation": "", "Actions": ""})

    if output_format == "html":
        print("\n🎉 Analysis complete! Returning HTML report.")
        html_content = _format_as_html_fragment(report_data, filename)
        return html_content, "text/html"
    else: # Default to Excel
        excel_report_data = []
        for item in report_data:
            full_description = f"Observation:\n{item['Original Observation']}\n\nRecommendation:\n{item['Recommendation']}\n\nAction Required:\n{item['Actions']}"
            excel_report_data.append({"Title": item['Title'], "Description": full_description, "Category": item['Category']})
        output_df = pd.DataFrame(excel_report_data)
        output_buffer = io.BytesIO()
        output_df.to_excel(output_buffer, index=False, sheet_name="Action Report")
        print("\n🎉 Analysis complete! Returning Excel file.")
        return output_buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"