import os
import re
import json
import pandas as pd
import io
from langchain_google_genai import ChatGoogleGenerativeAI
import chromadb
from sentence_transformers import SentenceTransformer
import datetime
from typing import Dict, List, Any # Added typing for clarity

# --- CONFIGURATION (Using OLD simple JSON file) ---
PCI_DATA_FILE = "pci_data.json" # Reverted to the simple JSON
DB_PATH = "pci_vector_db"
COLLECTION_NAME = "pci_requirements" # Assumes DB was built with simple JSON structure text

# --- Global objects ---
print("Loading embedding model for search...")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
print("Connecting to vector database...")
chroma_client = chromadb.PersistentClient(path=DB_PATH)
try:
    collection = chroma_client.get_collection(name=COLLECTION_NAME)
    print(f"Successfully connected to collection '{COLLECTION_NAME}'.")
except Exception as e:
    print(f"ERROR: Could not connect to ChromaDB collection '{COLLECTION_NAME}'. Did you run create_database.py with the correct (simple) pci_data.json? Error: {e}")
    # Consider exiting or raising

# --- Helper functions (adjusted for simple JSON) ---
def load_pci_data() -> dict:
    if not os.path.exists(PCI_DATA_FILE): return None
    with open(PCI_DATA_FILE, 'r', encoding='utf-8') as f: return json.load(f)

def clean_observation(text: str) -> str:
    cleaned_text = re.split(r'\bAction Required\b', text, flags=re.IGNORECASE)[0]
    cleaned_text = re.sub(r'^\s*Observation:\s*', '', cleaned_text, flags=re.IGNORECASE)
    return cleaned_text.strip()

def get_expanded_keywords(observation: str, model) -> list:
    print("🧠 Step 1/3: Expanding keywords...")
    prompt = f"Based on the following PCI DSS observation, list up to 10 relevant requirement numbers (e.g., '3.2.1', '12.5.2') and technical keywords. Return only a comma-separated list.\n\nObservation: \"{observation}\"\nKeywords:"
    try:
        response = model.invoke(prompt)
        keywords = [k.strip() for k in response.content.replace("*", "").split(',') if k.strip()]
        print(f"✅ Expanded keywords: {', '.join(keywords)}")
        return keywords
    except Exception as e:
        print(f"   ⚠️ Could not expand keywords, using basic search. Error: {e}")
        return list(set(re.findall(r'\b\w{4,}\b', observation.lower())))

# --- Hybrid Search (Adjusted for simple JSON) ---
def find_hybrid_context(pci_data: dict, observation: str, keywords: list, top_k=5) -> str:
    print("🔎 Step 2/3: Performing hybrid search...")
    relevant_texts = []
    processed_major_keys = set()
    try:
        query_embedding = embedding_model.encode([observation])
        vector_results = collection.query(query_embeddings=query_embedding.tolist(), n_results=top_k)
        if vector_results and vector_results.get('ids'):
            vector_ids = set(vector_results['ids'][0])
            print(f"   Vector search found potential sections/IDs: {vector_ids}")
            for key in vector_ids:
                 if key in pci_data and key not in processed_major_keys:
                    relevant_texts.append(f"--- From Requirement Section {key} ---\n{pci_data[key]}")
                    processed_major_keys.add(key)
        else:
            print("   Vector search returned no results.")
    except Exception as e:
        print(f"   ⚠️ Error during vector search: {e}")

    keyword_req_ids_found = set()
    req_num_pattern = re.compile(r"^[A-Z]?\d+(\.\d+)*$")
    for keyword in keywords:
        if req_num_pattern.match(keyword):
            major_key = keyword.split('.')[0]
            if major_key in pci_data and major_key not in processed_major_keys:
                 relevant_texts.append(f"--- From Requirement Section {major_key} (Keyword Match: {keyword}) ---\n{pci_data[major_key]}")
                 processed_major_keys.add(major_key)
                 keyword_req_ids_found.add(keyword)
        else:
             # Check if keyword appears in any major section text
             for major_key, text_block in pci_data.items():
                 if major_key not in processed_major_keys and keyword.lower() in text_block.lower():
                     relevant_texts.append(f"--- From Requirement Section {major_key} (Keyword Match: {keyword}) ---\n{pci_data[major_key]}")
                     processed_major_keys.add(major_key)
    if not relevant_texts: return "No relevant requirements could be found."
    print(f"✅ Found {len(relevant_texts)} relevant requirement section(s) via hybrid search.")
    return "\n\n".join(relevant_texts)


def _get_verified_requirement(context: str, observation: str, model) -> str:
    print("🔍 Step 3a/3b: Verifying the most relevant requirement...")
    prompt = f"""
    You are a meticulous PCI DSS compliance analyst. Your task is to identify the single most relevant PCI DSS requirement number (e.g., "3.4.1" or "12.5.2") that directly addresses the issue in the observation, based *only* on the provided context sections.

    --- Context from PCI DSS v4.0.1 ---
    {context}
    --- End of Context ---

    Observation: "{observation}"

    Respond with ONLY the single, most relevant requirement number:
    """
    try:
        response = model.invoke(prompt)
        verified_req_num = response.content.strip()
        if re.match(r"^[A-Z]?\d+(\.\d+)*$", verified_req_num):
             print(f"✅ Verified requirement: {verified_req_num}")
             return verified_req_num
        else:
             print(f"   ⚠️ Invalid requirement number format: {verified_req_num}. Proceeding with full context.")
             return None
    except Exception as e:
        print(f"   ⚠️ Could not verify requirement. Error: {e}")
        return None

# --- Main AI Prompt (4-part output + hierarchy) ---
def get_structured_recommendation(pci_data: dict, context: str, observation: str, model, verified_req_num: str) -> str:
    final_context = context
    # Refine context using verified number if possible with simple JSON
    if verified_req_num:
        major_key = verified_req_num.split('.')[0]
        if major_key in pci_data:
            final_context = f"--- Focus Requirement {verified_req_num} (within Section {major_key}) ---\n{pci_data[major_key]}"
    # else: verified_req_num = None # Implicitly handled

    print("🧠 Step 3b/3b: Generating structured recommendations with refined hierarchical logic...")
    current_date_str = datetime.date.today().strftime("%B %d, %Y")

    prompt = f"""
    You are an expert compliance auditor. Assume today's date is {current_date_str}. Your task is to provide a structured analysis based *only* on the context and observation. Output four parts using the exact headings followed by a colon.

    **Title:** [A short, descriptive title]
    **Category:** [ONE: Network Security, Application Security, Server & Desktop Security, Physical Security, or Information Security]
    **Recommendation:** [Recommendation content based on the logic below]
    **Action Required:** [Action items based on the logic below]

    ---
    **IMPORTANT LOGIC HIERARCHY FOR 'Recommendation' and 'Action Required':**

    **Step 1:** Check for "internal policy" violation.
    IF YES:
    - Recommendation: State stricter internal policy is not met. DO NOT mention PCI DSS.
    - Action Required: List actions to align with internal policy. Use numbered list (1., 2.).
    Then STOP.

    **Step 2:** Check if observation is about incomplete/inaccurate *documentation*.
    IF YES:
        **Special Handling for Scope Document:** IF the verified requirement is '12.5.2':
            - Recommendation: State "As per PCI DSS requirement 12.5.2 PCI DSS scope is documented and confirmed..." followed by the 7 bullet points (using '*' or '•' as markdown).
            - Action Required: State "1. Prepare the PCI DSS scope document with above mentioned points and ensure review annually or upon significant change."
            Then STOP.
        ELSE (other docs):
            - Recommendation: State documentation must meet frequency/accuracy per relevant PCI DSS requirement ({verified_req_num if verified_req_num else 'identified in context'}). **Special Date Handling:** If observation has date and requirement has frequency, explain violation using today's date ({current_date_str}).
            - Action Required: List specific document corrections (numbered list 1., 2.) and ask for "updated document" evidence.
            Then STOP.

    **Step 3:** Check if observation describes a "significant change" **to the environment/process**.
    **Definition:** New/upgraded HW/SW/Net; Changed data flow/storage; Changed CDE boundary; Changed infra; Changed TPSP.
    **Exclusion:** Simple documentation updates.
    IF YES (Significant Change):
    - Recommendation: State significant changes need re-validation (cite 11.3.1.3, 11.4.2) based on Requirement {verified_req_num if verified_req_num else 'identified in context'}.
    - Action Required: List implementation steps (numbered list 1., 2.), then the three mandatory points (VAPT procedure, IVA/EVA/IPT/EPT, change ticket).
    Then STOP.

    **Step 4:** IF NONE of the above (standard finding).
    - Recommendation: Apply rule from primary PCI DSS requirement ({verified_req_num if verified_req_num else 'identified in context'}) directly to observation.
    - Action Required: Numbered list ("1.", "2.") of direct actions and request specific evidence (e.g., "screenshot").
    ---

    **FORMATTING RULES:**
    - Use numbered list ("1.", "2.") for 'Action Required', EXCEPT for 12.5.2.
    - Use markdown bullets ('*' or '•') for lists in 'Recommendation'.
    - Do not use markdown '**' around headings.
    ---

    **Context from PCI DSS v4.0.1:**
    {final_context}

    **Observation:** "{observation}"

    **Your four-part response:**
    """
    try:
        response_content = model.invoke(prompt).content.strip()
        # Clean potential markdown from headings just in case
        response_content = re.sub(r"\*\*(.*?):\*\*", r"\1:", response_content)
        return response_content
    except Exception as e:
        print(f"   ⚠️ Error during final recommendation generation: {e}")
        # Return structured error for parsing
        return f"Title: Error\nCategory: Error\nRecommendation: An error occurred.\nAction Required: 1. {e}"


# --- SEPARATE FORMATTING FUNCTIONS ---
def format_data_as_html(report_data: list, original_filename: str) -> str:
    """Formats structured data into a visually distinct HTML fragment with cards, minimizing whitespace."""
    # Main report header
    html_findings = f"<h1>PCI DSS Gap Analysis Report</h1><p><strong>Source File:</strong> {original_filename}</p>"
    action_clean_pattern = re.compile(r"^\s*[\d.\-\*]+\s*")
    rec_bullet_pattern = re.compile(r"^\s*[\*\•]\s*")
    action_nested_bullet_pattern = re.compile(r"^\s+[\*\•]\s+") # Detect nested bullets

    for i, finding in enumerate(report_data):
        # Safely get data
        title = finding.get("Title", "Error: Title Missing")
        category = finding.get("Category", "N/A")
        observation = finding.get("Original Observation", "Error: Observation Missing")
        recommendation_text = finding.get("Recommendation", "Error: Recommendation Missing")
        actions_text = finding.get("Actions", "")
        recommendation_html = ""
        actions_html = ""

        # --- Format Recommendation ---
        if re.search(r"^\s*[\*\•]\s+", recommendation_text, re.MULTILINE):
            rec_lines = [line.strip() for line in recommendation_text.split('\n') if line.strip()]
            cleaned_lines = [rec_bullet_pattern.sub('', line) for line in rec_lines]
            # Use join without extra newlines/spaces for lists
            list_items = "".join([f"<li>{cleaned_line}</li>" for cleaned_line in cleaned_lines])
            recommendation_html = f"<ul>{list_items}</ul>"
        else:
            recommendation_html = f"<p>{recommendation_text}</p>"

        # --- Format Action Required (Handling nested lists) ---
        actions_html = "<ol>" # Start ordered list
        if isinstance(actions_text, str):
            current_li_content = ""
            is_in_nested_ul = False
            lines = actions_text.split('\n')
            temp_list_items = [] # Store processed lines before joining

            for line in lines:
                line_stripped = line.strip()
                if not line_stripped: continue

                is_nested = action_nested_bullet_pattern.match(line)
                is_main_item_start = re.match(r"^\s*\d+\.\s+", line)

                if is_main_item_start or (not current_li_content and not is_nested):
                    if is_in_nested_ul:
                        current_li_content += "</ul>"
                        is_in_nested_ul = False
                    if current_li_content:
                         temp_list_items.append(f"<li>{current_li_content}</li>") # Add completed item
                    current_li_content = action_clean_pattern.sub('', line_stripped) # Start new item
                elif is_nested:
                    if not is_in_nested_ul:
                        current_li_content += "<ul>"
                        is_in_nested_ul = True
                    current_li_content += f"<li>{action_nested_bullet_pattern.sub('', line_stripped)}</li>"
                else:
                    current_li_content += " " + line_stripped

            if is_in_nested_ul: current_li_content += "</ul>"
            if current_li_content: temp_list_items.append(f"<li>{current_li_content}</li>") # Add last item

            actions_html += "".join(temp_list_items) # Join list items without extra space

        else: # Handle error case
            actions_html += f"<li>Error processing actions: {actions_text}</li>"
        actions_html += "</ol>" # Close ordered list

        card_class = "finding-card error-card" if title == "Parsing Error" else "finding-card"

        # --- Assemble HTML using the card structure (minimized whitespace in f-string) ---
        # Use single line f-string elements or carefully manage indentation
        html_findings += (
            f'<div class="{card_class}">'
            f'<h2>Finding #{i + 1}: {title}</h2>'
            f'<p><strong>Category:</strong> {category}</p>'
            f'<h3>Observation:</h3>'
            f'<p>{observation}</p>'
            f'<h3>Recommendation:</h3>'
            f'{recommendation_html}' # This already contains <p> or <ul>
            f'<h3>Action Required:</h3>'
            f'{actions_html}' # This already contains <ol>
            f'</div>'
        )
        # Use a simple <hr> for separation instead of multiple <br>
        if i < len(report_data) - 1:
            html_findings += "<hr/>"

    return html_findings # Return combined fragments
def format_data_as_excel(report_data: list) -> bytes:
    """Formats the structured report data into an in-memory Excel file."""
    excel_report_data = []
    action_clean_pattern = re.compile(r"^\s*[\d.\-\*]+\s*")
    for item in report_data:
        actions_text = item.get('Actions', '')
        recommendation_text = item.get('Recommendation', '')
        numbered_actions = ""
        if isinstance(actions_text, str):
            if "Prepare the PCI DSS scope document" in actions_text: # Keep special 12.5.2 action
                numbered_actions = actions_text
            else:
                 cleaned_actions = [action_clean_pattern.sub("", action).strip()
                                   for action in actions_text.split('\n') if action.strip()]
                 numbered_actions = "\n".join([f"{idx+1}. {action}" for idx, action in enumerate(cleaned_actions)])
        else:
             numbered_actions = f"Error: {actions_text}"

        excel_recommendation = recommendation_text.replace('\n• ','\n  • ').replace('*','\n  • ')
        full_description = f"<b>Observation:</b>\n{item.get('Original Observation', '')}\n\n<b>Recommendation:</b>\n{excel_recommendation}\n\n<b>Action Required:</b>\n{numbered_actions}"
        excel_report_data.append({"Title": item.get('Title', 'N/A'), "Description": full_description, "Category": item.get('Category', 'N/A')})

    if not excel_report_data:
         excel_report_data.append({"Title": "No Findings", "Description": "No valid observations were found or processed.", "Category": "N/A"})
    output_df = pd.DataFrame(excel_report_data)
    output_buffer = io.BytesIO()
    output_df.to_excel(output_buffer, index=False, sheet_name="Action Report")
    return output_buffer.getvalue()

# --- CORE ANALYSIS FUNCTION (NOW RETURNS RAW DATA) ---
def run_analysis_on_file(file_stream) -> List[Dict[str, Any]]: # Ensure return type hint
    """
    Performs the core analysis using simple JSON and returns structured data.
    """
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key: raise ValueError("GOOGLE_API_KEY environment variable not set.")
        model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key) # Use appropriate model
    except Exception as e:
        raise ConnectionError(f"Error connecting to Google API: {e}")

    pci_data = load_pci_data() # Using simple JSON data
    if not pci_data: raise FileNotFoundError(f"Error: '{PCI_DATA_FILE}' not found.")

    try:
        buffer = io.BytesIO(file_stream.read())
        excel_sheets = pd.read_excel(buffer, sheet_name=None)
    except Exception as e:
        raise ValueError(f"Error reading Excel file: {e}")

    report_data = [] # Stores structured results
    print("\n🚀 Starting analysis...")
    filename = getattr(file_stream, 'name', 'uploaded_file.xlsx')

    for sheet_name, df in excel_sheets.items():
        obs_column = 'Description' if 'Description' in df.columns else 'Observation'
        for index, row in df.iterrows():
            original_observation_raw = str(row.get(obs_column, ''))
            if pd.isna(row.get(obs_column)) or not original_observation_raw.strip(): continue

            print(f"\n--- Processing Observation #{index + 2} from '{sheet_name}'... ---")
            # Ensure observation variables are clearly defined
            observation_cleaned = clean_observation(original_observation_raw)
            original_observation_display = original_observation_raw.replace("Observation:", "").strip()

            try:
                # --- Analysis Steps ---
                keywords = get_expanded_keywords(observation_cleaned, model)
                context = find_hybrid_context(pci_data, observation_cleaned, keywords)
                verified_req_num = _get_verified_requirement(context, observation_cleaned, model)

                # Call the 4-part DETAILED recommendation function
                structured_response = get_structured_recommendation(pci_data, context, observation_cleaned, model, verified_req_num)

                # --- Robust Parsing ---
                title = "Parsing Error" # Default values
                category = "Error"
                recommendation = f"Failed AI parse: {structured_response}"
                actions_text = "Review manually."

                title_match = re.search(r"Title:(.*?)Category:", structured_response, re.DOTALL | re.IGNORECASE)
                category_match = re.search(r"Category:(.*?)Recommendation:", structured_response, re.DOTALL | re.IGNORECASE)
                recommendation_match = re.search(r"Recommendation:(.*?)Action Required:", structured_response, re.DOTALL | re.IGNORECASE)
                actions_match = re.search(r"Action Required:(.*)", structured_response, re.DOTALL | re.IGNORECASE)

                # Safely extract matched groups
                if title_match: title = title_match.group(1).strip().replace("**", "")
                if category_match: category = category_match.group(1).strip().replace("**", "")
                if recommendation_match: recommendation = recommendation_match.group(1).strip()
                if actions_match: actions_text = actions_match.group(1).strip()

                # Append successful result
                report_data.append({
                    "Title": title,
                    "Category": category,
                    "Original Observation": original_observation_display,
                    "Recommendation": recommendation,
                    "Actions": actions_text
                })

            # *** UPDATED EXCEPTION HANDLING BLOCK ***
            except Exception as e:
                print(f"   ⚠️ ERROR during processing observation #{index + 2}. Error: {type(e).__name__} - {e}")
                # Optionally add traceback print for server-side debugging
                # import traceback
                # print(traceback.format_exc())

                # Define the error entry clearly
                error_entry = {
                    "Title": "Processing Error",
                    "Category": "Error",
                    "Original Observation": original_observation_display,
                    "Recommendation": f"An unexpected error occurred: {type(e).__name__}", # Show error type
                    "Actions": "Please check backend logs and report this issue." # More specific action
                }
                # Append the error entry
                report_data.append(error_entry)
            # *** END UPDATED BLOCK ***

    print(f"\n🎉 Analysis complete! Returning {len(report_data)} structured finding(s).")
    return report_data