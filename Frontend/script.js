/**
 * Utility function to download the given content as a text file.
 * @param {string} content The text content to download.
 */
const downloadReport = (content, modalReportOutput, modal) => {
  if (!content || content.trim().length < 10) {
    console.error("Download failed: No report content available.");
    // Display error message in the modal output area
    if (modalReportOutput)
      modalReportOutput.textContent =
        "Download failed: No analysis report has been generated yet.";
    if (modal) modal.style.display = "flex";
    return;
  }

  const blob = new Blob([content], { type: "text/plain" });
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = "PCI_DSS_Analysis_Report.txt";

  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

document.addEventListener("DOMContentLoaded", () => {
  // --- Element References ---
  const uploadForm = document.getElementById("upload-form");
  const fileInput = document.getElementById("file-input");
  const analyzeButton = document.getElementById("analyze-button");
  const resultContainer = document.getElementById("result-container");
  const spinner = document.getElementById("spinner");

  // Report action buttons (including download)
  const viewReportButton = document.getElementById("view-report-button");
  const downloadReportButton = document.getElementById(
    "download-report-button"
  );

  // Modal elements
  const modal = document.getElementById("report-modal");
  const modalCloseButton = document.getElementById("modal-close-button");
  const modalReportOutput = document.getElementById("modal-report-output");
  const modalDownloadButton = document.getElementById("modal-download-button");

  // Hidden element to temporarily hold the API response text (required ID)
  const reportOutput = document.getElementById("report-output");

  // --- Configuration ---
  const BACKEND_API_URL = "http://localhost:8000/analyze/";

  // --- Primary Button Click Handler ---
  // Attaches click to the visible button, which then triggers the hidden file input
  analyzeButton.addEventListener("click", () => {
    fileInput.click();
  });

  // --- Modal Control Functions ---

  /** Closes the report modal. */
  const closeModal = () => {
    if (modal) modal.style.display = "none";
  };

  /** Opens the report modal and populates it with the stored report content. */
  const openModal = () => {
    if (modal && reportOutput) {
      // Copy the stored report text (from the hidden element) into the visible modal element
      modalReportOutput.textContent = reportOutput.textContent;
      modal.style.display = "flex";
    }
  };

  // --- Modal and Download Event Listeners ---

  if (modalCloseButton) modalCloseButton.addEventListener("click", closeModal);
  if (viewReportButton) viewReportButton.addEventListener("click", openModal);

  // Download Handlers
  if (downloadReportButton) {
    downloadReportButton.addEventListener("click", () => {
      downloadReport(reportOutput.textContent, modalReportOutput, modal);
    });
  }
  if (modalDownloadButton) {
    modalDownloadButton.addEventListener("click", () => {
      downloadReport(reportOutput.textContent, modalReportOutput, modal);
    });
  }

  // Close modal if user clicks on the dark overlay
  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) {
        closeModal();
      }
    });
  }

  // --- Analysis Trigger Logic ---

  // Analysis is triggered immediately when a file is selected using the hidden input
  fileInput.addEventListener("change", async () => {
    // Check if the user selected a file or clicked cancel
    if (fileInput.files.length === 0) {
      return;
    }

    // --- UI updates for loading state ---
    analyzeButton.disabled = true;
    analyzeButton.textContent = "Analyzing...";
    resultContainer.classList.remove("hidden");
    spinner.style.display = "block";
    viewReportButton.style.display = "none"; // Hide the "View" button
    downloadReportButton.style.display = "none"; // Hide the "Download" button

    reportOutput.textContent = ""; // Clear temporary data
    modalReportOutput.textContent = "Report generation in progress..."; // Default modal message

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    try {
      const response = await fetch(BACKEND_API_URL, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        // Handle API error response
        const errorData = await response.json().catch(() => ({
          detail: "Server returned a non-JSON error or empty response.",
        }));
        throw new Error(
          errorData.detail || `HTTP error! Status: ${response.status}`
        );
      }

      const result = await response.json();

      // 1. Store the successful report text in the hidden element
      reportOutput.textContent = result.report;

      // 2. Open the report pop-up immediately after success
      openModal();
    } catch (error) {
      console.error("Error during analysis:", error);
      let errorMessage;
      if (error.message.includes("Failed to fetch")) {
        errorMessage = `An error occurred: Network connection failed.\n\nPlease ensure your backend server is running and accessible at ${BACKEND_API_URL}.`;
      } else {
        errorMessage = `An error occurred:\n\n${error.message}\n\nPlease ensure your backend server is running and accessible at ${BACKEND_API_URL}.`;
      }

      // Store and display the error message in the modal
      reportOutput.textContent = errorMessage;
      modalReportOutput.textContent = errorMessage;

      openModal(); // Open modal to show the error
    } finally {
      // --- UI updates to restore initial state ---
      analyzeButton.disabled = false;
      analyzeButton.textContent = "UPLOAD & ANALYZE";
      spinner.style.display = "none"; // Hide spinner

      // Only show action buttons if the reportOutput has content (i.e., not a network error before the try block)
      if (reportOutput.textContent.length > 0) {
        viewReportButton.style.display = "inline-block"; // Show the "View" button for re-opening
        downloadReportButton.style.display = "inline-block"; // Show the "Download" button
      }

      // Reset file input value to allow the same file to be selected again
      fileInput.value = "";
    }
  });
});
