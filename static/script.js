// Update character count
const promptTextarea = document.getElementById('prompt');
const charCountSpan = document.getElementById('charCount');

promptTextarea.addEventListener('input', () => {
    charCountSpan.textContent = promptTextarea.value.length;
});

// Handle Enter key (Ctrl+Enter to submit)
promptTextarea.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'Enter') {
        generateContent();
    }
});

async function generateContent() {
    const prompt = document.getElementById('prompt').value.trim();
    const generateBtn = document.getElementById('generateBtn');
    const loader = document.getElementById('loader');
    const errorDiv = document.getElementById('error');
    const responseSection = document.getElementById('responseSection');
    const responseContent = document.getElementById('responseContent');
    
    // Validation
    if (!prompt) {
        showError('Please enter a prompt before generating.');
        return;
    }
    
    // Clear previous error and response
    errorDiv.classList.remove('active');
    errorDiv.textContent = '';
    
    // Show loader and disable button
    loader.classList.add('active');
    generateBtn.disabled = true;
    generateBtn.textContent = 'Generating...';
    responseSection.style.display = 'none';
    
    try {
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ prompt: prompt })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to generate response');
        }
        
        // Display the response
        responseContent.textContent = data.response;
        responseSection.style.display = 'block';
        
        // Smooth scroll to response
        responseSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        
    } catch (error) {
        console.error('Error:', error);
        showError(`Error: ${error.message}`);
    } finally {
        // Hide loader and enable button
        loader.classList.remove('active');
        generateBtn.disabled = false;
        generateBtn.textContent = 'Generate Response';
    }
}

function showError(message) {
    const errorDiv = document.getElementById('error');
    errorDiv.textContent = message;
    errorDiv.classList.add('active');
    
    // Auto-hide error after 5 seconds
    setTimeout(() => {
        errorDiv.classList.remove('active');
    }, 5000);
}

// Add example prompts functionality
window.addEventListener('DOMContentLoaded', () => {
    // Focus on textarea when page loads
    promptTextarea.focus();
});

// Optional: Add keyboard shortcut hint
const helpText = document.createElement('div');
helpText.style.cssText = 'text-align: center; color: #999; font-size: 14px; margin-top: 10px;';
helpText.textContent = 'Tip: Press Ctrl+Enter to submit';
promptTextarea.parentElement.appendChild(helpText);
