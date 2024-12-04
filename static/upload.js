document.addEventListener('DOMContentLoaded', () => {
    const uploadForm = document.getElementById('uploadForm');
    const fileInput = document.getElementById('fileInput');
    const uploadBtn = document.getElementById('uploadBtn');
    const statusMessage = document.getElementById('statusMessage');
    const downloadBtn = document.getElementById('downloadBtn');

    let socket = null;
    let taskId = null;

    function initWebSocket() {
        // Use wss:// for secure connections in production
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const socketUrl = `${protocol}//${window.location.host}/ws/upload/`;
        
        socket = new WebSocket(socketUrl);

        socket.onopen = () => {
            console.log('WebSocket connection established');
        };

        socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log('WebSocket message:', data);
                handleTaskUpdate(data);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };

        socket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        socket.onclose = (event) => {
            console.log('WebSocket connection closed');
            // Attempt to reconnect after a delay
            setTimeout(initWebSocket, 2000);
        };
    }

    function handleTaskUpdate(data) {
        console.log('Handling task update:', data);
        
        switch(data.status) {
            case 'PENDING':
            case 'PROCESSING':
                statusMessage.textContent = 'Processing file...';
                statusMessage.style.display = 'block';
                break;
            case 'COMPLETED':
                statusMessage.textContent = 'Conversion completed!';
                downloadBtn.style.display = 'block';
                downloadBtn.onclick = () => {
                    window.location.href = `/download/${data.file_name}`;
                };
                uploadBtn.disabled = false;
                break;
            case 'FAILED':
                statusMessage.textContent = 'Conversion failed!';
                statusMessage.style.display = 'block';
                uploadBtn.disabled = false;
                break;
        }
    }

    uploadForm.addEventListener('submit', async (event) => {
        event.preventDefault();

        if (!fileInput.files.length || !document.getElementById('conversionType').value) {
            alert('Please select a file and conversion type');
            return;
        }

        const formData = new FormData(uploadForm);
        uploadBtn.disabled = true;
        statusMessage.textContent = 'Uploading file...';
        statusMessage.style.display = 'block';
        downloadBtn.style.display = 'none';

        try {
            const response = await fetch('/api/upload/', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.task_id) {
                taskId = data.task_id;
                console.log('Conversion task started:', taskId);
                
                // Start polling as a backup
                trackConversionStatus(taskId);
            } else {
                throw new Error(data.message || 'Upload failed');
            }
        } catch (error) {
            console.error('Upload error:', error);
            statusMessage.textContent = `Error: ${error.message}`;
            uploadBtn.disabled = false;
        }
    });

    function trackConversionStatus(taskId) {
        const intervalId = setInterval(() => {
            fetch(`/api/task-status/?task_id=${taskId}`)
                .then(response => response.json())
                .then(data => {
                    console.log('Task Status:', data.status);
                    
                    if (data.status === 'COMPLETED') {
                        clearInterval(intervalId);
                        handleTaskUpdate({
                            status: 'COMPLETED', 
                            file_name: data.file_name
                        });
                    } else if (data.status === 'FAILED') {
                        clearInterval(intervalId);
                        handleTaskUpdate({ status: 'FAILED' });
                    }
                })
                .catch(error => {
                    console.error('Error checking task status:', error);
                    clearInterval(intervalId);
                });
        }, 5000);
    }

    // Initialize WebSocket on page load
    initWebSocket();
});