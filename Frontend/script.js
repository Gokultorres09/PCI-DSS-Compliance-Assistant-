document.addEventListener("DOMContentLoaded", () => {
  // --- Element References (IDs preserved) ---
  const uploadForm = document.getElementById("upload-form");
  const fileInput = document.getElementById("file-input");
  const analyzeButton = document.getElementById("analyze-button");
  const resultContainer = document.getElementById("result-container");
  const spinner = document.getElementById("spinner");

  // Modal elements
  const modal = document.getElementById("report-modal");
  const modalCloseButton = document.getElementById("modal-close-button");
  const viewReportButton = document.getElementById("view-report-button");
  const modalReportOutput = document.getElementById("modal-report-output");

  // Hidden element to temporarily hold the API response text (required ID)
  const reportOutput = document.getElementById("report-output");

  // --- Configuration ---
  // IMPORTANT: Ensure this URL matches your FastAPI backend address
  const BACKEND_API_URL = "http://localhost:8000/analyze/";

  // --- Modal Control Functions ---

  /** Closes the report modal. */
  const closeModal = () => {
    modal.style.display = "none";
  };

  /** Opens the report modal and populates it with the stored report content. */
  const openModal = () => {
    // Copy the stored report text (from the hidden element) into the visible modal element
    modalReportOutput.textContent = reportOutput.textContent;
    modal.style.display = "flex";
  };

  // --- Modal Event Listeners ---
  modalCloseButton.addEventListener("click", closeModal);
  viewReportButton.addEventListener("click", openModal);

  // Close modal if user clicks on the dark overlay
  modal.addEventListener("click", (e) => {
    if (e.target === modal) {
      closeModal();
    }
  });

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
        const errorData = await response.json();
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
      const errorMessage = `An error occurred:\n\n${error.message}\n\nPlease ensure your backend server is running and accessible at ${BACKEND_API_URL}.`;

      // Store and display the error message in the modal
      reportOutput.textContent = errorMessage;
      modalReportOutput.textContent = errorMessage;

      openModal(); // Open modal to show the error
    } finally {
      // --- UI updates to restore initial state ---
      analyzeButton.disabled = false;
      analyzeButton.textContent = "UPLOAD & ANALYZE";
      spinner.style.display = "none"; // Hide spinner
      viewReportButton.style.display = "block"; // Show the "View" button for re-opening

      // Reset file input value to allow the same file to be selected again
      fileInput.value = "";
    }
  });
});
