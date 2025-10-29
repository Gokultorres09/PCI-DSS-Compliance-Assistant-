document.addEventListener("DOMContentLoaded", () => {
    // --- Element References ---
    const uploadForm = document.getElementById("upload-form");
    const fileInput = document.getElementById("file-input");
    const analyzeButton = document.getElementById("analyze-button");
    const resultContainer = document.getElementById("result-container");
    const spinner = document.getElementById("spinner");
    const viewReportButton = document.getElementById("view-report-button");
    const downloadReportButton = document.getElementById("download-report-button");
    const modal = document.getElementById("report-modal");
    const modalCloseButton = document.getElementById("modal-close-button");
    const modalReportOutput = document.getElementById("modal-report-output");
    // No reportStorage needed for HTML, we fetch it on demand

    // --- Check if elements were found ---
     if (!uploadForm || !fileInput || !analyzeButton || !resultContainer || !spinner || !viewReportButton || !downloadReportButton || !modal || !modalCloseButton || !modalReportOutput) {
         console.error("Initialization Error: One or more essential DOM elements not found. Check IDs in index.html and script.js.");
         // Display error prominently if elements are missing
         const body = document.querySelector('body');
         if(body) {
             const errorDiv = document.createElement('div');
             errorDiv.innerHTML = '<h1 style="color: red; background: yellow; padding: 10px; border: 2px solid red; position: fixed; top: 10px; left: 10px; z-index: 9999;">Error: Page elements missing. Cannot initialize. Check console (Cmd/Ctrl+Shift+J).</h1>';
             body.prepend(errorDiv);
         }
         return; // Stop script
     } else {
          console.log("All essential DOM elements found.");
     }

    // --- API URLs for the 3 endpoints ---
    const ANALYZE_API_URL = "http://localhost:8000/analyze/";
    const FORMAT_HTML_API_URL = "http://localhost:8000/format/html/";
    const FORMAT_EXCEL_API_URL = "http://localhost:8000/format/excel/";

    // --- State Variable ---
    let analysisResults = null; // Store the JSON data
    let originalFilename = "";   // Store the original filename

    // --- Event Listeners ---
    // Prevent the form itself from causing a page reload if accidentally submitted
    uploadForm.addEventListener("submit", (e) => {
        e.preventDefault();
        console.log("Form submit intercepted and prevented.");
    });

    // Attach listener to the main UPLOAD button
    analyzeButton.addEventListener("click", () => {
        console.log("Analyze button clicked."); // Log for debugging
        fileInput.click(); // Programmatically click the hidden file input
    });

    // Attach listener to the hidden file input to trigger analysis when a file is chosen
    fileInput.addEventListener("change", handleFileAnalysis);

    // Attach listeners to the result buttons (View/Download)
    viewReportButton.addEventListener("click", handleViewHtmlReport);
    downloadReportButton.addEventListener("click", handleExcelDownload);

    // Attach listeners for modal closing
    modalCloseButton.addEventListener("click", closeModal);
    modal.addEventListener("click", (e) => {
        // Close modal if user clicks on the background overlay
        if (e.target === modal) {
            closeModal();
        }
    });

    // --- Core Functions ---

    /** Step 1: Analyze file, get JSON data */
    async function handleFileAnalysis() {
        if (!fileInput || fileInput.files.length === 0) {
             console.log("handleFileAnalysis called but no file selected.");
             return;
        }

        console.log("handleFileAnalysis triggered (Analyze-Once Workflow).");
        setLoadingState(true);
        analysisResults = null; // Clear previous results
        originalFilename = fileInput.files[0].name; // Store filename

        const formData = new FormData();
        formData.append("file", fileInput.files[0]);

        console.log("Requesting URL:", ANALYZE_API_URL);

        try {
            // Call the /analyze endpoint (expects JSON response)
            const response = await fetch(ANALYZE_API_URL, { method: "POST", body: formData });

            console.log("Analysis Response status:", response.status);
            const contentType = response.headers.get('content-type');
            console.log("Analysis Response content type:", contentType);

            if (!response.ok) {
                 // Robust error handling (read as text first)
                let errorMsg = `Analysis failed (HTTP ${response.status})`;
                try {
                    const errorText = await response.text();
                    if (contentType && contentType.includes('application/json')) {
                        const errorData = JSON.parse(errorText);
                        errorMsg = errorData.detail || errorText;
                    } else { // Handle non-JSON error responses (like HTML error pages)
                        const match = errorText.match(/<pre>(.*?)<\/pre>/i);
                        errorMsg = match ? match[1].trim() : errorText.substring(0, 500);
                    }
                } catch (e) { console.error("Could not read analysis error response body:", e); }
                throw new Error(errorMsg);
            }

            // --- Expect JSON data ---
            if (!contentType || !contentType.includes('application/json')) {
                const responseText = await response.text();
                throw new Error(`Expected JSON from /analyze but received ${contentType}. Response: ${responseText.substring(0,100)}...`);
            }

            analysisResults = await response.json(); // Store the structured JSON data
            console.log("Received analysis results (JSON):", analysisResults);

            // Check if results are empty
            if (!analysisResults || analysisResults.length === 0) {
                 console.warn("Analysis successful but returned no findings.");
                 // Optionally display a message in the modal area later
            }

            setLoadingState(false, true); // Analysis complete, show buttons

        } catch (error) {
            console.error("Error during analysis:", error);
            // Display error in modal content area for visibility
            modalReportOutput.innerHTML = `<h3>Analysis Error</h3><p>Could not process the file.</p><p><strong>Details:</strong> ${error.message}</p><p>Please check console & backend logs.</p>`;
            openModal(modalReportOutput.innerHTML); // Open modal to show the error
            analysisResults = null; // Clear results on error
            setLoadingState(false, true); // Still show buttons, user might want to try download if analysis partially worked before
        } finally {
            if (fileInput) fileInput.value = ""; // Reset file input
        }
    }

    /** Step 2a: Request HTML formatting and open modal */
    async function handleViewHtmlReport() {
        if (!analysisResults) { // Check if results exist
            alert("No analysis data available to display. Please analyze a file first.");
            return;
        }
        if (analysisResults.length === 0) {
            alert("Analysis completed, but no findings were generated from the file.");
            // Open modal with a "No Findings" message
             openModal("<h1>PCI DSS Gap Analysis Report</h1><p><strong>Source File:</strong> "+originalFilename+"</p><hr/><p>No findings were generated from the provided file.</p>");
            return;
        }

        viewReportButton.textContent = "Loading View...";
        viewReportButton.disabled = true;

        try {
            console.log("Requesting HTML format from:", FORMAT_HTML_API_URL);
            // Call the /format/html endpoint, sending the stored JSON data
            const response = await fetch(FORMAT_HTML_API_URL, {
                method: "POST",
                headers: { 'Content-Type': 'application/json' },
                // Send the stored JSON data and original filename
                body: JSON.stringify({ report_data: analysisResults, filename: originalFilename })
            });

            console.log("HTML Format Response status:", response.status);
            const contentType = response.headers.get('content-type');
            console.log("HTML Format Response content type:", contentType);

            if (!response.ok) {
                 // Robust error handling
                let errorMsg = `HTML formatting failed (HTTP ${response.status})`;
                 try {
                     const errorText = await response.text();
                     if (contentType && contentType.includes('application/json')) {
                         const errorData = JSON.parse(errorText);
                         errorMsg = errorData.detail || errorText;
                     } else {
                         const match = errorText.match(/<pre>(.*?)<\/pre>/i);
                         errorMsg = match ? match[1].trim() : errorText.substring(0, 500);
                     }
                 } catch (e) { /* ignore */ }
                 throw new Error(errorMsg);
            }

            if (!contentType || !contentType.includes('text/html')) {
                 const responseText = await response.text();
                 throw new Error(`Expected HTML from /format/html but received ${contentType}. Resp: ${responseText.substring(0,100)}...`);
            }

            const htmlContent = await response.text();
            console.log("Received formatted HTML (first 100 chars):", htmlContent.substring(0, 100));
            openModal(htmlContent); // Pass HTML directly to modal

        } catch (error) {
            console.error("Error fetching HTML report:", error);
            alert(`Could not display report: ${error.message}`);
        } finally {
            viewReportButton.textContent = "View Analysis Report";
            viewReportButton.disabled = false;
        }
    }

    /** Step 2b: Request Excel formatting and download */
    async function handleExcelDownload() {
        if (!analysisResults) { // Check if results exist
            alert("No analysis data available to download. Please analyze a file first.");
            return;
        }
         if (analysisResults.length === 0) {
             alert("Analysis completed, but no findings were generated to download.");
             return;
         }

        downloadReportButton.textContent = "DOWNLOADING...";
        downloadReportButton.disabled = true;

        try {
            console.log("Requesting Excel format from:", FORMAT_EXCEL_API_URL);
             // Call the /format/excel endpoint, sending the stored JSON data
            const response = await fetch(FORMAT_EXCEL_API_URL, {
                method: "POST",
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ report_data: analysisResults, filename: originalFilename }) // Send stored data
            });

            console.log("Excel Format Response status:", response.status);

            if (!response.ok) {
                 // Robust error handling
                let errorMsg = `Excel generation failed (HTTP ${response.status})`;
                try {
                     const errorText = await response.text();
                     const contentType = response.headers.get('content-type');
                     if (contentType && contentType.includes('application/json')) {
                         const errorData = JSON.parse(errorText);
                         errorMsg = errorData.detail || errorText;
                     } else {
                          const match = errorText.match(/<pre>(.*?)<\/pre>/i);
                         errorMsg = match ? match[1].trim() : errorText.substring(0, 500);
                     }
                 } catch (e) { /* ignore */ }
                 throw new Error(errorMsg);
            }

            // Check content type for Excel
            const contentType = response.headers.get('content-type');
             console.log("Excel Format Response content type:", contentType);
             // More specific check for Excel MIME types
             if (!contentType || !(contentType.includes('spreadsheetml') || contentType.includes('ms-excel'))) {
                  const responseText = await response.text(); // Try reading as text to see error
                  throw new Error(`Expected Excel file but received ${contentType}. Response: ${responseText.substring(0,100)}...`);
             }


            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            const cleanFilename = originalFilename.replace(/\.(xlsx|xls)$/, '');
            a.href = url;
            a.download = `PCI_DSS_Action_Report_${cleanFilename}.xlsx`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
            console.log("Excel download initiated.");

        } catch (error) {
            console.error("Error downloading Excel:", error);
            alert(`Could not download report: ${error.message}`);
        } finally {
            downloadReportButton.textContent = "Download Report";
            downloadReportButton.disabled = false;
        }
    }

    /** Manages the UI loading and result states */
    function setLoadingState(isLoading, showButtons = false) {
        // Add checks for element existence
        if (spinner) spinner.style.display = isLoading ? "block" : "none";
        if (analyzeButton) {
            analyzeButton.disabled = isLoading;
            analyzeButton.textContent = isLoading ? "ANALYZING..." : "UPLOAD & ANALYZE";
        }
        if (resultContainer) resultContainer.classList.toggle("hidden", !showButtons);
        if (viewReportButton) viewReportButton.style.display = showButtons ? "inline-block" : "none";
        if (downloadReportButton) downloadReportButton.style.display = showButtons ? "inline-block" : "none";
    }

    /** Opens the report modal WITH the provided HTML */
    function openModal(htmlContent) {
        // Check elements before using
        if (modalReportOutput) {
            modalReportOutput.innerHTML = htmlContent;
        } else {
             console.error("Cannot open modal: modalReportOutput element not found.");
             return;
        }
        if (modal) {
            modal.style.display = "flex";
        } else {
            console.error("Cannot open modal: modal element not found.");
        }
    }

    function closeModal() {
        if (modal) modal.style.display = "none";
    }

    console.log("Script loaded and event listeners attached (Analyze-Once Workflow).");

}); // --- End of DOMContentLoaded ---