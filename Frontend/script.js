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
    // *** NEW: Download History Modal Elements ***
    const downloadsNavLink = document.getElementById("downloads-nav-link");
    const downloadHistoryModal = document.getElementById("download-history-modal");
    const downloadHistoryCloseButton = document.getElementById("download-history-close-button");
    const downloadHistoryOutput = document.getElementById("download-history-output");


    // --- Check if elements were found ---
     if (!uploadForm || !fileInput || !analyzeButton || !resultContainer || !spinner || !viewReportButton || !downloadReportButton || !modal || !modalCloseButton || !modalReportOutput || !downloadsNavLink || !downloadHistoryModal || !downloadHistoryCloseButton || !downloadHistoryOutput) { // Added checks for new elements
         console.error("Initialization Error: One or more essential DOM elements not found.");
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

    // --- API URLs ---
    const ANALYZE_API_URL = "http://localhost:8000/analyze/";
    const FORMAT_HTML_API_URL = "http://localhost:8000/format/html/";
    const FORMAT_EXCEL_API_URL = "http://localhost:8000/format/excel/";

    // --- State Variables ---
    let analysisResults = null;
    let originalFilename = "";
    const DOWNLOAD_HISTORY_KEY = 'pciReportDownloadHistory'; // Key for localStorage
    const MAX_HISTORY_ITEMS = 10; // Max downloads to store

    // --- Event Listeners ---
    uploadForm.addEventListener("submit", (e) => e.preventDefault());
    analyzeButton.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", handleFileAnalysis);
    viewReportButton.addEventListener("click", handleViewHtmlReport);
    downloadReportButton.addEventListener("click", handleExcelDownload);
    modalCloseButton.addEventListener("click", closeModal);
    modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });

    // *** NEW: Download History Listeners ***
    downloadsNavLink.addEventListener("click", (e) => {
        e.preventDefault(); // Prevent link default action
        displayDownloadHistory();
    });
    downloadHistoryCloseButton.addEventListener("click", closeDownloadHistoryModal);
    downloadHistoryModal.addEventListener("click", (e) => { if (e.target === downloadHistoryModal) closeDownloadHistoryModal(); });

    // --- Core Functions ---

    // (handleFileAnalysis remains the same as the correct analyze-once version)
     async function handleFileAnalysis() {
        if (!fileInput || fileInput.files.length === 0) return;
        console.log("handleFileAnalysis triggered (Analyze-Once Workflow).");
        setLoadingState(true);
        analysisResults = null;
        originalFilename = fileInput.files[0].name;
        const formData = new FormData();
        formData.append("file", fileInput.files[0]);
        console.log("Requesting URL:", ANALYZE_API_URL);
        try {
            const response = await fetch(ANALYZE_API_URL, { method: "POST", body: formData });
            console.log("Analysis Response status:", response.status);
            const contentType = response.headers.get('content-type');
            console.log("Analysis Response content type:", contentType);
            if (!response.ok) {
                let errorMsg = `Analysis failed (HTTP ${response.status})`;
                try {
                    const errorText = await response.text();
                    if (contentType && contentType.includes('application/json')) {
                        const errorData = JSON.parse(errorText);
                        errorMsg = errorData.detail || errorText;
                    } else {
                        const match = errorText.match(/<pre>(.*?)<\/pre>/i);
                        errorMsg = match ? match[1].trim() : errorText.substring(0, 500);
                    }
                } catch (e) { console.error("Could not read analysis error response body:", e); }
                throw new Error(errorMsg);
            }
            if (!contentType || !contentType.includes('application/json')) {
                const responseText = await response.text();
                throw new Error(`Expected JSON but received ${contentType}. Resp: ${responseText.substring(0,100)}...`);
            }
            analysisResults = await response.json();
            console.log("Received analysis results (JSON):", analysisResults);
            if (!analysisResults || analysisResults.length === 0) {
                 console.warn("Analysis successful but returned no findings.");
            }
            setLoadingState(false, true);
        } catch (error) {
            console.error("Error during analysis:", error);
            modalReportOutput.innerHTML = `<h3>Analysis Error</h3><p>${error.message}</p><p>Check console & backend logs.</p>`;
            openModal(modalReportOutput.innerHTML);
            analysisResults = null;
            setLoadingState(false, true); // Show buttons even on error
        } finally {
            if (fileInput) fileInput.value = "";
        }
    }


    // (handleViewHtmlReport remains the same as the correct analyze-once version)
    async function handleViewHtmlReport() {
        if (!analysisResults) {
            alert("No analysis data available. Please analyze a file first.");
            return;
        }
        if (analysisResults.length === 0) {
            openModal("<h1>Report</h1><p><strong>Source:</strong> "+originalFilename+"</p><hr/><p>No findings generated.</p>");
            return;
        }
        viewReportButton.textContent = "Loading View...";
        viewReportButton.disabled = true;
        try {
            console.log("Requesting HTML format from:", FORMAT_HTML_API_URL);
            const response = await fetch(FORMAT_HTML_API_URL, {
                method: "POST", headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ report_data: analysisResults, filename: originalFilename })
            });
            console.log("HTML Format Response status:", response.status);
            const contentType = response.headers.get('content-type');
            console.log("HTML Format Response content type:", contentType);
            if (!response.ok) {
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
                 throw new Error(`Expected HTML but received ${contentType}. Resp: ${responseText.substring(0,100)}...`);
            }
            const htmlContent = await response.text();
            console.log("Received formatted HTML (first 100 chars):", htmlContent.substring(0, 100));
            openModal(htmlContent);
        } catch (error) {
            console.error("Error fetching HTML report:", error);
            alert(`Could not display report: ${error.message}`);
        } finally {
            viewReportButton.textContent = "View Analysis Report";
            viewReportButton.disabled = false;
        }
    }


    // *** MODIFIED handleExcelDownload to save history ***
    async function handleExcelDownload() {
        if (!analysisResults) {
            alert("No analysis data available to download.");
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
            const response = await fetch(FORMAT_EXCEL_API_URL, {
                method: "POST", headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ report_data: analysisResults, filename: originalFilename })
            });
            console.log("Excel Format Response status:", response.status);
            if (!response.ok) {
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
            const contentType = response.headers.get('content-type');
             console.log("Excel Format Response content type:", contentType);
             if (!contentType || !(contentType.includes('spreadsheetml') || contentType.includes('ms-excel'))) {
                  const responseText = await response.text();
                  throw new Error(`Expected Excel file but received ${contentType}. Resp: ${responseText.substring(0,100)}...`);
             }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            const cleanFilename = originalFilename.replace(/\.(xlsx|xls)$/, '');
            // *** Construct the download filename ***
            const downloadFilename = `PCI_DSS_Action_Report_${cleanFilename}.xlsx`;
            a.href = url;
            a.download = downloadFilename; // Use the constructed filename
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a); // Clean up the link
            window.URL.revokeObjectURL(url);
            console.log("Excel download initiated for:", downloadFilename);

            // *** SAVE TO LOCALSTORAGE (only on success) ***
            saveDownloadToHistory(downloadFilename);

        } catch (error) {
            console.error("Error downloading Excel:", error);
            alert(`Could not download report: ${error.message}`);
        } finally {
            downloadReportButton.textContent = "Download Report";
            downloadReportButton.disabled = false;
        }
    }

    // *** NEW: Function to save download info ***
    function saveDownloadToHistory(filename) {
        try {
            const history = JSON.parse(localStorage.getItem(DOWNLOAD_HISTORY_KEY) || '[]');
            const newEntry = {
                filename: filename,
                timestamp: new Date().toISOString() // Store as ISO string
            };
            // Add to the beginning of the array
            history.unshift(newEntry);
            // Limit history size
            const trimmedHistory = history.slice(0, MAX_HISTORY_ITEMS);
            localStorage.setItem(DOWNLOAD_HISTORY_KEY, JSON.stringify(trimmedHistory));
            console.log("Saved download to history:", newEntry.filename);
        } catch (error) {
            console.error("Error saving download history to localStorage:", error);
        }
    }

    // *** NEW: Function to display download history ***
    function displayDownloadHistory() {
        try {
            const history = JSON.parse(localStorage.getItem(DOWNLOAD_HISTORY_KEY) || '[]');
            if (history.length === 0) {
                downloadHistoryOutput.innerHTML = "<p>No downloads recorded yet.</p>";
            } else {
                let historyHtml = "<ul>";
                history.forEach(entry => {
                    const date = new Date(entry.timestamp);
                    const formattedDate = date.toLocaleString(); // Format date nicely
                    // Escape filename to prevent potential XSS if filename contains HTML
                    const safeFilename = entry.filename.replace(/</g, "&lt;").replace(/>/g, "&gt;");
                    historyHtml += `<li><strong>${safeFilename}</strong><br/><small>${formattedDate}</small></li>`;
                });
                historyHtml += "</ul>";
                downloadHistoryOutput.innerHTML = historyHtml;
            }
            downloadHistoryModal.style.display = 'flex'; // Show the modal
        } catch (error) {
            console.error("Error reading or displaying download history:", error);
            downloadHistoryOutput.innerHTML = "<p>Error loading download history.</p>";
            downloadHistoryModal.style.display = 'flex'; // Show modal even on error
        }
    }

    // *** NEW: Function to close the history modal ***
    function closeDownloadHistoryModal() {
        downloadHistoryModal.style.display = 'none';
    }


    // (setLoadingState, openModal, closeModal remain the same)
     function setLoadingState(isLoading, showButtons = false) {
        if (spinner) spinner.style.display = isLoading ? "block" : "none";
        if (analyzeButton) {
            analyzeButton.disabled = isLoading;
            analyzeButton.textContent = isLoading ? "ANALYZING..." : "UPLOAD & ANALYZE";
        }
        if (resultContainer) resultContainer.classList.toggle("hidden", !showButtons);
        if (viewReportButton) viewReportButton.style.display = showButtons ? "inline-block" : "none";
        if (downloadReportButton) downloadReportButton.style.display = showButtons ? "inline-block" : "none";
    }
     function openModal(htmlContent) {
        if (modalReportOutput) {
            modalReportOutput.innerHTML = htmlContent;
        } else { console.error("modalReportOutput not found"); return; }
        if (modal) { modal.style.display = "flex"; }
        else { console.error("modal element not found"); }
    }
     function closeModal() {
        if (modal) modal.style.display = "none";
    }

    console.log("Script loaded and event listeners attached (Analyze-Once Workflow).");

}); // --- End of DOMContentLoaded ---