# Claude Chrome Extension Setup

This Chrome extension allows you to use your regular Claude.ai browser session with AshAI, avoiding the authentication issues with automated browsers.

## Installation

1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode" in the top right
3. Click "Load unpacked"
4. Select the `claude-extension` folder

## Usage

1. **Log into Claude.ai** in your Chrome browser normally
2. **Run the WebSocket bridge** (see below for Python script)
3. **The extension icon** should show "Connected" when ready
4. **AshAI can now use Claude** through your browser session

## Benefits

- Uses your existing $20/month Claude subscription
- No authentication issues with Google/SSO
- Saves $560+/month vs API pricing
- Works with your regular browser session

## WebSocket Bridge Server

Create and run `claude-websocket-bridge.py`:

```python
# This script will be created next
```

The bridge connects AshAI to the Chrome extension, which then communicates with Claude.ai in your authenticated browser session.