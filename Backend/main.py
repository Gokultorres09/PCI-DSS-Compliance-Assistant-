from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import Response, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import pci_compliance_logic
import io

app = FastAPI(
    title="PCI DSS Compliance Assistant API",
    description="Analyzes PCI DSS observation files and returns a structured report.",
    version="2.1.0"
)

# --- ROBUST CORS CONFIGURATION ---
origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "null",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ------------------------------------

@app.get("/", summary="Root endpoint to check server status")
def read_root():
    return {"status": "PCI Compliance Backend is running"}

@app.post("/analyze/", summary="Analyze an Excel file and return a report")
async def analyze_observations(
    file: UploadFile = File(...),
    format: str = Query("excel", enum=["excel", "html"])
):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an Excel file.")

    try:
        print(f"Received file: {file.filename} for format: {format}")

        file_content, media_type = pci_compliance_logic.run_analysis_on_file(
            file.file,
            file.filename,
            output_format=format
        )

        file_extension = "xlsx" if format == "excel" else "html"
        download_filename = f"PCI_DSS_Report_{file.filename.rsplit('.', 1)[0]}.{file_extension}"

        if format == "html":
            return HTMLResponse(content=file_content)
        else:
            return Response(
                content=file_content,
                media_type=media_type,
                headers={"Content-Disposition": f"attachment; filename={download_filename}"}
            )

    except (ValueError, FileNotFoundError, ConnectionError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")