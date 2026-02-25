# Claude Web Automation Provider

The Claude Web Automation provider enables AshAI to interact with Claude.ai through browser automation using Playwright. This allows you to use Claude's web interface without requiring API credits, making it perfect for subscription-based access.

## Features

- ✅ **Browser Automation**: Uses Playwright to control Claude.ai web interface
- ✅ **Login Flow**: Handles email/password authentication automatically  
- ✅ **Message Streaming**: Supports streaming responses (simulated)
- ✅ **Error Handling**: Robust error handling and retry logic
- ✅ **Headless Mode**: Can run with or without visible browser
- ✅ **Provider Integration**: Full integration with AshAI's LLM registry system

## Installation

### 1. Install Dependencies

```bash
# Install with web automation support
pip install 'helperai[web-automation]'

# Or install playwright directly
pip install playwright>=1.48.0
```

### 2. Install Browser

```bash
# Install Chromium browser for Playwright
playwright install chromium
```

## Configuration

### Environment Variables

Add these to your `.env` file:

```env
# Claude Web Automation
HELPERAI_CLAUDE_WEB_EMAIL=your-email@example.com
HELPERAI_CLAUDE_WEB_PASSWORD=your-password
HELPERAI_CLAUDE_WEB_HEADLESS=true
HELPERAI_CLAUDE_WEB_TIMEOUT=30000

# Optional: Set as default provider
HELPERAI_DEFAULT_PROVIDER=claude_web
```

### Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `HELPERAI_CLAUDE_WEB_EMAIL` | Your Claude.ai email | Required |
| `HELPERAI_CLAUDE_WEB_PASSWORD` | Your Claude.ai password | Required |
| `HELPERAI_CLAUDE_WEB_HEADLESS` | Run browser in headless mode | `true` |
| `HELPERAI_CLAUDE_WEB_TIMEOUT` | Browser timeout in milliseconds | `30000` |

## Usage

### Basic Usage

```python
import asyncio
from helperai.llm.claude_web_provider import ClaudeWebProvider
from helperai.llm.message_types import Message

async def main():
    provider = ClaudeWebProvider(
        email="your-email@example.com",
        password="your-password",
        headless=True
    )
    
    try:
        messages = [Message(role="user", content="Hello Claude!")]
        
        async for chunk in provider.stream(messages, "claude-3-5-sonnet-20241022"):
            print(chunk.delta_content, end='', flush=True)
            if chunk.finish_reason:
                break
                
    finally:
        await provider.close()

asyncio.run(main())
```

### Integration with AshAI

The provider automatically registers with AshAI when credentials are provided:

```python
# Start AshAI server with Claude web automation
python -m helperai
```

Then use through the API:

```bash
curl -X POST http://localhost:8000/api/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{
    "messages": [{"role": "user", "content": "Hello!"}],
    "provider": "claude_web"
  }'
```

## How It Works

### Authentication Flow

1. **Navigate to Login**: Opens Claude.ai login page
2. **Enter Credentials**: Fills email and password fields
3. **Handle 2FA**: Currently supports basic email/password (2FA support planned)
4. **Session Management**: Maintains login session across requests

### Message Flow

1. **Start Conversation**: Creates new chat or uses existing one
2. **Send Message**: Types message into chat input
3. **Wait for Response**: Monitors DOM for Claude's response
4. **Extract Content**: Parses response text from chat interface
5. **Stream Simulation**: Yields response as streaming chunks

### Browser Management

- **Stealth Mode**: Uses anti-detection measures
- **Resource Cleanup**: Properly closes browser sessions
- **Error Recovery**: Handles network issues and timeouts
- **Session Persistence**: Maintains login across multiple requests

## Limitations

### Current Limitations

- **No Real Streaming**: Simulates streaming by yielding complete response
- **Single Conversation**: Each request starts a new conversation
- **No Tool Support**: Web interface doesn't support function calling
- **Rate Limiting**: Subject to Claude.ai's web interface rate limits

### Planned Improvements

- [ ] Real-time streaming by monitoring DOM changes
- [ ] Conversation context preservation
- [ ] 2FA/MFA support
- [ ] Better error recovery
- [ ] Session persistence across restarts
- [ ] Support for file uploads
- [ ] Model selection (if exposed in web UI)

## Security Considerations

### Credential Storage

- Store credentials in environment variables or secure vault
- Never commit credentials to version control
- Consider using encrypted credential storage

### Browser Security

- Runs in isolated browser context
- Uses standard security headers
- Cleans up sessions on shutdown

### Network Security

- All communication over HTTPS
- No credential transmission to third parties
- Local browser automation only

## Troubleshooting

### Common Issues

#### Login Failures

```
Error: Failed to login to Claude.ai
```

**Solutions:**
- Verify email/password are correct
- Check for CAPTCHA requirements
- Ensure account is not locked
- Try with `headless=False` to see browser

#### Browser Not Found

```
Error: Browser executable not found
```

**Solutions:**
```bash
# Install browser
playwright install chromium

# Or install all browsers
playwright install
```

#### Timeout Issues

```
Error: Timeout waiting for response
```

**Solutions:**
- Increase timeout: `HELPERAI_CLAUDE_WEB_TIMEOUT=60000`
- Check internet connection
- Verify Claude.ai is accessible

#### Element Not Found

```
Error: Could not find message input field
```

**Solutions:**
- Claude.ai may have updated their interface
- Try with `headless=False` to inspect page
- Check browser console for errors

### Debugging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Run with visible browser:

```python
provider = ClaudeWebProvider(
    email=email,
    password=password,
    headless=False  # Shows browser window
)
```

## Examples

See `examples/claude_web_demo.py` for comprehensive examples:

```bash
# Run the demo
python examples/claude_web_demo.py
```

## Contributing

### Adding Features

1. **DOM Selectors**: Update selectors in `claude_web_provider.py`
2. **Error Handling**: Add new error cases and recovery logic
3. **Testing**: Add tests for new functionality

### Reporting Issues

When reporting issues, include:
- Browser version and OS
- Full error traceback
- Steps to reproduce
- Screenshots if relevant

## License

This provider is part of AshAI and follows the same MIT license.