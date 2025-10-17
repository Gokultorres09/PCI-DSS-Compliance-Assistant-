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
    const reportStorage = document.getElementById("report-storage"); // Hidden div to store HTML report

    // --- State Variable ---
    /**
     * @type {File | null}
     * This holds the file object after a successful analysis.
     * It's the key to fixing the "analyze a file first" bug.
     */
    let analyzedFile = null;

    const BASE_API_URL = "http://localhost:8000/analyze/";

    // --- Event Listeners ---
    // Prevents the page from reloading on form submission
    uploadForm.addEventListener("submit", (event) => event.preventDefault());

    analyzeButton.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", handleFileAnalysis);
    viewReportButton.addEventListener("click", openModal);
    downloadReportButton.addEventListener("click", handleExcelDownload);
    modalCloseButton.addEventListener("click", closeModal);

    // Close modal if clicking on the background overlay
    modal.addEventListener("click", (e) => {
        if (e.target === modal) closeModal();
    });

    /**
     * Handles the file upload and analysis process.
     */
    async function handleFileAnalysis() {
        if (fileInput.files.length === 0) return;
        
        // A new file is selected, so reset the previous state completely.
        const currentFile = fileInput.files[0];
        analyzedFile = null; // Invalidate previous analysis
        setLoadingState(true); // Show spinner and disable buttons
        reportStorage.innerHTML = ""; // Clear previous report content

        const formData = new FormData();
        formData.append("file", currentFile);
        const apiUrl = `${BASE_API_URL}?format=html`;

        try {
            const response = await fetch(apiUrl, { method: "POST", body: formData });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: "Server error or non-JSON response" }));
                throw new Error(errorData.detail);
            }
            const htmlReport = await response.text();
            reportStorage.innerHTML = htmlReport; // Store the new report
            
            // **CRITICAL FIX**: Set the state variable on success
            analyzedFile = currentFile; 
            
            setLoadingState(false, true); // Hide spinner, show report buttons

        } catch (error) {
            console.error("Error during analysis:", error);
            const errorMessage = `<h3>Analysis Failed</h3><p>${error.message}</p><p>Please ensure the backend server is running and check the console for more details.</p>`;
            reportStorage.innerHTML = errorMessage;
            // Make the error visible in the modal as well
            openModal(); 
            setLoadingState(false, false); // Hide spinner and report buttons
        } finally {
            // Clear the input to allow re-uploading the same file if needed
            fileInput.value = "";
        }
    }

    /**
     * Handles the Excel report download.
     */
    async function handleExcelDownload() {
        // **CRITICAL FIX**: Check the state variable, not the file input.
        if (!analyzedFile) {
            alert("Please complete a successful file analysis first.");
            return;
        }

        setDownloadState(true);

        const formData = new FormData();
        formData.append("file", analyzedFile); // Use the stored file object
        const apiUrl = `${BASE_API_URL}?format=excel`;

        try {
            const response = await fetch(apiUrl, { method: "POST", body: formData });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: "Server error during download" }));
                throw new Error(errorData.detail);
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            
            // Create a clean filename from the original
            const originalFilename = analyzedFile.name.split('.').slice(0, -1).join('.');
            a.href = url;
            a.download = `PCI_DSS_Action_Report_${originalFilename}.xlsx`;
            
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a); // Clean up the DOM
            window.URL.revokeObjectURL(url); // Free up memory

        } catch (error) {
            console.error("Error downloading Excel:", error);
            alert(`Could not download the report: ${error.message}`);
        } finally {
            setDownloadState(false);
        }
    }

    // --- UI State Management Functions ---

    function setLoadingState(isLoading, showReportButtons = false) {
        spinner.style.display = isLoading ? "block" : "none";
        analyzeButton.disabled = isLoading;
        analyzeButton.textContent = isLoading ? "ANALYZING..." : "UPLOAD & ANALYZE";

        resultContainer.classList.toggle("hidden", !showReportButtons);
        viewReportButton.style.display = showReportButtons ? "inline-block" : "none";
        downloadReportButton.style.display = showReportButtons ? "inline-block" : "none";
    }
    
    function setDownloadState(isDownloading) {
        downloadReportButton.disabled = isDownloading;
        downloadReportButton.textContent = isDownloading ? "DOWNLOADING..." : "Download Report";
    }

    function openModal() {
        if (!reportStorage.innerHTML.trim()) {
            modalReportOutput.innerHTML = "<p>No report has been generated yet.</p>";
        } else {
            modalReportOutput.innerHTML = reportStorage.innerHTML;
        }
        modal.style.display = "flex";
    }

    function closeModal() {
        modal.style.display = "none";
    }
});