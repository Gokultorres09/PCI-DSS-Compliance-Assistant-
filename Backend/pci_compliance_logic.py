import os
import re
import json
import pandas as pd
import io  # <--- ADD THIS LINE
from langchain_google_genai import ChatGoogleGenerativeAI

# --- CONFIGURATION ---
PCI_DATA_FILE = "pci_data.json"

def load_pci_data() -> dict:
    if not os.path.exists(PCI_DATA_FILE):
        return None
    with open(PCI_DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def clean_observation(text: str) -> str:
    cleaned_text = re.split(r'\bAction Required\b', text, flags=re.IGNORECASE)[0]
    cleaned_text = re.sub(r'^\s*Observation:\s*', '', cleaned_text, flags=re.IGNORECASE)
    return cleaned_text.strip()

def get_expanded_keywords(observation: str, model) -> list:
    print("🧠 Step 1/3: Expanding keywords...")
    prompt = f"Based on the following PCI DSS observation, list up to 10 relevant requirement numbers (e.g., '8.3.2', '12.6') and technical keywords to search for. Return only a comma-separated list.\n\nObservation: \"{observation}\"\nKeywords:"
    try:
        # LangChain's .invoke() method is consistent across models
        response = model.invoke(prompt)
        keywords = [k.strip() for k in response.content.replace("*", "").replace("\n", ",").split(',') if k.strip()]
        print(f"✅ Expanded keywords: {', '.join(keywords)}")
        return keywords
    except Exception:
        print("   ⚠️ Could not expand keywords, using basic search.")
        return list(set(re.findall(r'\b\w{4,}\b', observation.lower())))

def find_relevant_context(pci_data: dict, keywords: list) -> str:
    print("🔎 Step 2/3: Searching structured data...")
    relevant_texts = []
    for req_num, req_text in pci_data.items():
        if any(keyword.lower() in req_num.lower() or keyword.lower() in req_text.lower() for keyword in keywords):
            relevant_texts.append(f"--- From Requirement {req_num} ---\n{req_text}")

    if not relevant_texts:
        return "No relevant requirements could be found."
    print(f"✅ Found {len(relevant_texts)} relevant requirement section(s).")
    return "\n\n".join(relevant_texts)

def get_final_recommendation(context: str, observation: str, model) -> str:
    print("🧠 Step 3/3: Generating final recommendations...")
    prompt = f"""
    You are a PCI DSS auditor. Your task is to provide only the direct remediation actions for the specific finding in the observation.
    Based *only* on the provided context, what are the specific actions required to fix the *exact issue* described in the observation?
    Do NOT suggest any other actions, even if they relate to the same PCI DSS requirement. Do NOT add any preamble or explanation.
    Output ONLY a numbered list of the direct, required actions.

    --- Context from PCI DSS v4.0.1 ---
    {context}
    --- End of Context ---

    Observation: "{observation}"

    Required Actions:
    """
    try:
        response = model.invoke(prompt)
        return response.content.strip()
    except Exception as e:
        return f"❌ An error occurred during the final API call: {e}"

def run_analysis_on_file(file_stream) -> str:
    """
    This function orchestrates the analysis on an in-memory Excel file.
    It returns the final report as a single string.
    """
    # --- MODEL & DATA INITIALIZATION ---
    try:
        # IMPORTANT: This line loads your API key from an environment variable
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set.")
            
        # Initialize the Google Gemini model
        model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key)

        
        # Test the connection to the Google API
        model.invoke("Respond with just the word 'OK' to confirm you are working.")
    except Exception as e:
        error_msg = f"❌ Error connecting to Google API: {e}\n\nPlease ensure your GOOGLE_API_KEY is set correctly."
        print(error_msg)
        return error_msg

    pci_data = load_pci_data()
    if not pci_data:
        error_msg = f"❌ Error: '{PCI_DATA_FILE}' not found in the backend directory."
        print(error_msg)
        return error_msg

    try:
        # Create a BytesIO buffer and read the file stream into it
        buffer = io.BytesIO(file_stream.read())
        # Tell pandas to read from the buffer
        excel_sheets = pd.read_excel(buffer, sheet_name=None)
        print(f"✅ Found {len(excel_sheets)} sheet(s) in the uploaded Excel file.")
    except Exception as e:
        error_msg = f"❌ Error reading Excel file: {e}"
        print(error_msg)
        return error_msg

    report_lines = []
    print("\n🚀 Starting analysis...")

    for sheet_name, df in excel_sheets.items():
        print(f"\n📄 Processing Sheet: '{sheet_name}'")
        report_lines.append(f"==================================================")
        report_lines.append(f"                  SHEET: {sheet_name}                  ")
        report_lines.append(f"==================================================\n")

        obs_column = 'Description' if 'Description' in df.columns else 'Observation'

        for index, row in df.iterrows():
            original_observation = str(row.get(obs_column, ''))
            if pd.isna(row.get(obs_column)) or not original_observation.strip():
                continue

            observation = clean_observation(original_observation)
            print(f"\n--- Processing Observation #{index + 2} from '{sheet_name}': {observation[:50]}... ---")
            report_lines.append(f"--- Observation #{index + 2} ---")
            report_lines.append(f"Original Observation Text:\n{original_observation}\n")

            keywords = get_expanded_keywords(observation, model)
            context = find_relevant_context(pci_data, keywords)
            recommendation = get_final_recommendation(context, observation, model)

            report_lines.append("Required Actions:")
            report_lines.append(recommendation)
            report_lines.append("\n" + "-"*50 + "\n")

    print("\n🎉 Analysis complete! Returning report to frontend.")
    return "\n".join(report_lines)