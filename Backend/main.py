from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pci_compliance_logic

app = FastAPI(
    title="PCI DSS Compliance Assistant API",
    description="Analyzes PCI DSS observation files using a cloud-based AI model.",
    version="1.0.0"
)

# --- THIS IS THE CORS CONFIGURATION THAT FIXES THE ERROR ---
origins = [
    "http://localhost",
    "http://localhost:8080", # For `python -m http.server 8080`
    "http://127.0.0.1:8080",
    "http://localhost:5500", # For VS Code Live Server
    "http://127.0.0.1:5500",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ---------------------------------------------------------

@app.get("/", summary="Root endpoint to check server status")
def read_root():
    """A simple endpoint to confirm the server is running."""
    return {"status": "PCI Compliance Backend is running"}

@app.post("/analyze/", summary="Analyze a PCI observation Excel file")
async def analyze_observations(file: UploadFile = File(...)):
    """
    Accepts an Excel file (XLSX), processes its observations, and returns
    a full compliance report as a single text block.
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an Excel file (.xlsx or .xls).")

    try:
        print(f"Received file: {file.filename}")
        report = pci_compliance_logic.run_analysis_on_file(file.file)
        return {"filename": file.filename, "report": report}
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")