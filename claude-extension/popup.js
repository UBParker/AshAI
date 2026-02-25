// Check WebSocket connection status
chrome.runtime.sendMessage({action: 'getStatus'}, (response) => {
  const statusEl = document.getElementById('status');
  if (response && response.connected) {
    statusEl.textContent = 'Connected to AshAI';
    statusEl.className = 'status connected';
  } else {
    statusEl.textContent = 'Disconnected';
    statusEl.className = 'status disconnected';
  }
});