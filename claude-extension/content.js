// Content script that runs on Claude.ai pages
console.log('Claude AshAI Bridge loaded');

// Listen for messages from background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'sendMessage') {
    // Find the message input
    const messageInput = document.querySelector('div[contenteditable="true"]') ||
                        document.querySelector('textarea');

    if (messageInput) {
      // Type the message
      messageInput.focus();
      messageInput.innerText = request.message;
      messageInput.dispatchEvent(new Event('input', { bubbles: true }));

      // Press Enter to send
      setTimeout(() => {
        const enterEvent = new KeyboardEvent('keydown', {
          key: 'Enter',
          code: 'Enter',
          bubbles: true
        });
        messageInput.dispatchEvent(enterEvent);

        // Wait for response
        setTimeout(() => {
          const responses = document.querySelectorAll('[data-testid="message-content"]');
          const lastResponse = responses[responses.length - 1];
          if (lastResponse) {
            sendResponse({success: true, response: lastResponse.innerText});
          } else {
            sendResponse({success: false, error: 'No response found'});
          }
        }, 5000);
      }, 100);

      return true; // Keep channel open for async response
    } else {
      sendResponse({success: false, error: 'Message input not found'});
    }
  }
});