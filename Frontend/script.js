document.addEventListener('DOMContentLoaded', () => {
    const uploadForm = document.getElementById('upload-form');
    const fileInput = document.getElementById('file-input');
    const fileNameSpan = document.getElementById('file-name');
    const analyzeButton = document.getElementById('analyze-button');
    const resultContainer = document.getElementById('result-container');
    const reportOutput = document.getElementById('report-output');
    const spinner = document.getElementById('spinner');

    const BACKEND_API_URL = 'http://localhost:8000/analyze/';

    // Update the file name display when a file is chosen
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            fileNameSpan.textContent = `📄 ${fileInput.files[0].name}`;
        } else {
            fileNameSpan.textContent = '📂 Choose an Excel File...';
        }
    });

    uploadForm.addEventListener('submit', async (event) => {
        event.preventDefault(); // Prevent default form submission

        if (fileInput.files.length === 0) {
            alert('Please select a file first.');
            return;
        }

        // --- UI updates for loading state ---
        analyzeButton.disabled = true;
        analyzeButton.textContent = 'Analyzing...';
        resultContainer.classList.remove('hidden');
        spinner.style.display = 'block';
        reportOutput.textContent = ''; // Clear previous results

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);

        try {
            const response = await fetch(BACKEND_API_URL, {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                // If server returns an error, display it
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP error! Status: ${response.status}`);
            }

            const result = await response.json();
            reportOutput.textContent = result.report;

        } catch (error) {
            console.error('Error during analysis:', error);
            reportOutput.textContent = `An error occurred:\n\n${error.message}\n\nPlease check the console for more details and ensure the backend server is running.`;
            reportOutput.style.color = 'red';
        } finally {
            // --- UI updates to restore initial state ---
            analyzeButton.disabled = false;
            analyzeButton.textContent = 'Analyze File';
            spinner.style.display = 'none'; // Hide spinner
        }
    });
});