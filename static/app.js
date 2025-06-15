document.addEventListener('DOMContentLoaded', () => {
    const callForm = document.getElementById('callForm');
    const callButton = callForm.querySelector('.call-button');
    const buttonText = callButton.querySelector('.button-text');
    const loadingSpinner = callButton.querySelector('.loading-spinner');
    const callStatus = document.getElementById('callStatus');
    const callId = document.getElementById('callId');
    const callDuration = document.getElementById('callDuration');
    const conversationContainer = document.getElementById('conversationContainer');

    let callStartTime = null;
    let durationInterval = null;

    // Format phone number as user types
    const phoneInput = document.getElementById('phoneNumber');
    phoneInput.addEventListener('input', (e) => {
        let value = e.target.value.replace(/\D/g, '');
        if (value.length > 0) {
            value = '+' + value;
        }
        e.target.value = value;
    });

    // Handle form submission
    callForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Disable form and show loading state
        setLoadingState(true);
        
        const formData = {
            phone_number: document.getElementById('phoneNumber').value,
            amount: parseFloat(document.getElementById('amount').value),
            due_date: document.getElementById('dueDate').value,
            account_number: document.getElementById('accountNumber').value || null
        };

        try {
            const response = await fetch('/api/call', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(formData)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Failed to initiate call');
            }

            const data = await response.json();
            
            // Update UI with call information
            callId.textContent = data.call_id;
            callStatus.textContent = 'Call in progress';
            callStatus.style.color = 'var(--success-color)';
            
            // Start duration timer
            startCallTimer();
            
            // Add system message
            addMessage('Call initiated successfully', 'system');
            
            // Start WebSocket connection for real-time updates
            connectWebSocket(data.call_id);
            
        } catch (error) {
            console.error('Error:', error);
            addMessage(`Failed to initiate call: ${error.message}`, 'system');
            callStatus.textContent = 'Call failed';
            callStatus.style.color = 'var(--error-color)';
        } finally {
            setLoadingState(false);
        }
    });

    function setLoadingState(isLoading) {
        callButton.disabled = isLoading;
        buttonText.textContent = isLoading ? 'Initiating Call...' : 'Start Call';
        loadingSpinner.style.display = isLoading ? 'block' : 'none';
    }

    function startCallTimer() {
        callStartTime = Date.now();
        durationInterval = setInterval(updateDuration, 1000);
    }

    function updateDuration() {
        const duration = Math.floor((Date.now() - callStartTime) / 1000);
        const minutes = Math.floor(duration / 60).toString().padStart(2, '0');
        const seconds = (duration % 60).toString().padStart(2, '0');
        callDuration.textContent = `${minutes}:${seconds}`;
    }

    function addMessage(text, type) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        messageDiv.textContent = text;
        conversationContainer.appendChild(messageDiv);
        conversationContainer.scrollTop = conversationContainer.scrollHeight;
    }

    function connectWebSocket(callId) {
        const ws = new WebSocket(`ws://${window.location.host}/ws/call/${callId}`);

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            switch (data.type) {
                case 'transcript':
                    addMessage(data.text, data.speaker === 'agent' ? 'agent' : 'customer');
                    break;
                    
                case 'call_ended':
                    clearInterval(durationInterval);
                    callStatus.textContent = 'Call ended';
                    callStatus.style.color = 'var(--text-secondary)';
                    addMessage('Call ended', 'system');
                    ws.close();
                    break;
                    
                case 'error':
                    addMessage(`Error: ${data.message}`, 'system');
                    break;
            }
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            addMessage('Connection error occurred', 'system');
        };

        ws.onclose = () => {
            console.log('WebSocket connection closed');
        };
    }
});

// Test interface code
let mediaRecorder;
let audioChunks = [];

function logMessage(message, type = 'info') {
    const log = document.getElementById('log');
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.textContent = `${new Date().toLocaleTimeString()}: ${message}`;
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
}

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };

        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            
            // Convert blob to base64
            const reader = new FileReader();
            reader.readAsDataURL(audioBlob);
            reader.onloadend = async () => {
                const base64Audio = reader.result.split(',')[1]; // Remove data URL prefix
                
                try {
                    logMessage('Sending audio for transcription...');
                    const response = await fetch('/api/test-stt', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            audio_data: base64Audio,
                            file_name: 'recording.wav'
                        })
                    });
                    
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    
                    const data = await response.json();
                    if (data.transcript) {
                        logMessage(`Transcription: ${data.transcript}`, 'success');
                        document.getElementById('transcript').textContent = `Transcription: ${data.transcript}`;
                        
                        // Get LLM response
                        logMessage('Getting AI response...');
                        const llmResponse = await fetch('/api/test-llm', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ transcript: data.transcript })
                        });
                        
                        if (!llmResponse.ok) {
                            throw new Error(`HTTP error! status: ${llmResponse.status}`);
                        }
                        
                        const llmData = await llmResponse.json();
                        if (llmData.response) {
                            logMessage(`AI Response: ${llmData.response}`, 'success');
                            
                            // Get TTS response
                            logMessage('Converting response to speech...');
                            const ttsResponse = await fetch('/api/test-tts', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ text: llmData.response })
                            });
                            
                            if (!ttsResponse.ok) {
                                throw new Error(`HTTP error! status: ${ttsResponse.status}`);
                            }
                            
                            const audioBlob = await ttsResponse.blob();
                            const audioUrl = URL.createObjectURL(audioBlob);
                            const audio = new Audio(audioUrl);
                            audio.play();
                            logMessage('Playing AI response...', 'success');
                        }
                    }
                } catch (error) {
                    logMessage(`Error: ${error.message}`, 'error');
                }
            };
        };

        mediaRecorder.start();
        logMessage('Recording started...', 'success');
    } catch (error) {
        logMessage(`Error: ${error.message}`, 'error');
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        logMessage('Recording stopped...', 'success');
    }
}

async function playGreeting() {
    try {
        logMessage('Playing greeting...');
        const response = await fetch('/api/test-tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                text: "Hello, I am your AI debt collection agent. How can I help you today?"
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        audio.play();
        logMessage('Playing greeting...', 'success');
    } catch (error) {
        logMessage(`Error: ${error.message}`, 'error');
    }
} 