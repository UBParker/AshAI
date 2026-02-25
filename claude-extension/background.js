// Background script to handle communication between extension and local server
let ws = null;

// Connect to local WebSocket server
function connectWebSocket() {
  ws = new WebSocket('ws://localhost:8082');

  ws.onopen = () => {
    console.log('Connected to AshAI server');
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    // Send message to Claude.ai via content script
    chrome.tabs.query({url: "*://*.claude.ai/*"}, (tabs) => {
      if (tabs.length > 0) {
        chrome.tabs.sendMessage(tabs[0].id, {
          action: 'sendMessage',
          message: data.message
        }, (response) => {
          if (response && response.success) {
            ws.send(JSON.stringify({
              type: 'response',
              response: response.response
            }));
          }
        });
      }
    });
  };

  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
  };

  ws.onclose = () => {
    console.log('WebSocket closed, reconnecting in 5s...');
    setTimeout(connectWebSocket, 5000);
  };
}

connectWebSocket();