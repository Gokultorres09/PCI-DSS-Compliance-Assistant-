from fastapi import FastAPI, File, UploadFile, HTTPException, Body
from fastapi.responses import Response, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import pci_compliance_logic # Import your logic script
import io
import pandas as pd # Import pandas for empty Excel case
from typing import List, Dict, Any

app = FastAPI(
    title="PCI DSS Compliance Assistant API",
    description="Analyzes PCI DSS observations and generates reports.",
    version="3.1.1" # Version update
)

# --- CORS Configuration ---
origins = [
    "http://localhost", "http://localhost:8080", "http://127.0.0.1:8080",
    "http://localhost:5500", "http://127.0.0.1:5500", "null",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

@app.get("/", summary="Root endpoint")
def read_root():
    return {"status": "PCI Compliance Backend is running"}

# --- Endpoint 1: Perform Analysis ---
@app.post("/analyze/", summary="Analyze Excel file and return structured data", response_model=List[Dict[str, Any]])
async def analyze_observations(file: UploadFile = File(...)):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Invalid file type.")
    try:
        print(f"Received file for analysis: {file.filename}")
        # *** Ensure this calls the correct function returning JSON ***
        report_data = pci_compliance_logic.run_analysis_on_file(file.file)
        if not report_data:
             print("Warning: No processable observations found.")
             return [] # Return empty list
        return report_data
    except (ValueError, FileNotFoundError, ConnectionError) as e:
        print(f"Known error during analysis: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Unexpected analysis error: {e}")
        # import traceback; print(traceback.format_exc()) # Uncomment for detailed debug
        raise HTTPException(status_code=500, detail=f"Internal server error during analysis: {e}")

# --- Endpoint 2: Format Data as HTML ---
@app.post("/format/html/", summary="Format structured data as HTML", response_class=HTMLResponse)
async def format_html(report_data: List[Dict[str, Any]] = Body(...), filename: str = Body("report.xlsx")):
    if not report_data:
         # Return a minimal valid HTML response for no data
         return HTMLResponse(content="<h1>PCI DSS Gap Analysis Report</h1><p><strong>Source File:</strong> N/A</p><hr/><p>No analysis data provided or found.</p>")
    try:
        print(f"Formatting data as HTML for: {filename}")
        # *** Call the correct HTML formatter ***
        html_content = pci_compliance_logic.format_data_as_html(report_data, filename)
        return HTMLResponse(content=html_content) # Send the HTML fragment/content
    except Exception as e:
        print(f"Error formatting HTML: {e}")
        # import traceback; print(traceback.format_exc()) # Uncomment for detailed debug
        raise HTTPException(status_code=500, detail="Error generating HTML report.")

# --- Endpoint 3: Format Data as Excel ---
@app.post("/format/excel/", summary="Format structured data as Excel")
async def format_excel(report_data: List[Dict[str, Any]] = Body(...), filename: str = Body("report.xlsx")):
    filename_base = filename.rsplit('.', 1)[0] if '.' in filename else filename
    download_filename = f"PCI_DSS_Report_{filename_base}.xlsx"
    if not report_data:
        # Create minimal Excel if no data
        empty_df = pd.DataFrame([{"Title": "No Data", "Description": "No analysis data found.", "Category": "N/A"}])
        output_buffer = io.BytesIO()
        empty_df.to_excel(output_buffer, index=False, sheet_name="Action Report")
        excel_bytes = output_buffer.getvalue()
    else:
        try:
            print(f"Formatting data as Excel for: {filename}")
             # *** Call the correct Excel formatter ***
            excel_bytes = pci_compliance_logic.format_data_as_excel(report_data)
        except Exception as e:
            print(f"Error formatting Excel: {e}")
             # import traceback; print(traceback.format_exc()) # Uncomment for detailed debug
            raise HTTPException(status_code=500, detail="Error generating Excel report.")

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=\"{download_filename}\""}
    )