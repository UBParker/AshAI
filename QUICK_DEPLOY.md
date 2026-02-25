# 🚀 Quick Deploy: AshAI with FREE Claude Code (No API Costs!)

## Your Cost Savings: $580+/month!

Before: **~$600/month** in API costs
After: **$20/month** Claude subscription only!

## Quick Start (Docker)

The Docker deployment includes Playwright and all dependencies pre-installed.

### 1. Build the Claude Code Container
```bash
docker build -f Dockerfile.claude-code -t ashai-claude-code .
```

### 2. Run AshAI with Claude Code
```bash
docker run -it \
  -e HELPERAI_DEFAULT_PROVIDER=claude_code \
  -e HELPERAI_CLAUDE_CODE_ENABLED=true \
  -p 8000:8000 \
  ashai-claude-code
```

### 3. Multi-Agent System (All FREE!)
Deploy multiple agents using your subscription:
```bash
docker-compose -f docker-compose.claude-agents.yml up
```

## Local Development (Without Docker)

### Prerequisites
- Claude subscription ($20/month)
- Python 3.9+
- Node.js 16+

### Setup
```bash
# Install dependencies
source .venv/bin/activate
python -m ensurepip --upgrade  # If pip is missing
pip install playwright
playwright install chromium

# Start backend
python -m helperai

# Start frontend (new terminal)
cd src/frontend
npm run dev
```

## Verify Cost Savings

1. Check your Anthropic API dashboard
   - Before: High daily usage ($20+/day)
   - After: Near zero usage ($0/day)

2. All agents now use your Claude subscription
   - Unlimited messages
   - No rate limits
   - Better performance

## Configuration

Your `.env` is already configured:
```env
HELPERAI_DEFAULT_PROVIDER=claude_code
HELPERAI_CLAUDE_CODE_ENABLED=true
```

## Architecture

```
Your $20/month Claude Subscription
            │
      ┌─────▼─────┐
      │ Claude    │
      │   Code    │  (Desktop App in Container)
      └─────┬─────┘
            │
    ┌───────┴────────┐
    │                │
┌───▼───┐      ┌────▼────┐
│Agent 1│      │Agent 2  │  All agents FREE!
│  $0   │      │  $0     │  No API costs!
└───────┘      └─────────┘
```

## Troubleshooting

### Playwright not found?
```bash
# For local development
pip install playwright
playwright install chromium

# For Docker (already included)
docker build -f Dockerfile.claude-code -t ashai-claude-code .
```

### Want to switch back to API?
Edit `.env`:
```env
HELPERAI_DEFAULT_PROVIDER=anthropic
HELPERAI_ANTHROPIC_API_KEY=your-key
```

## Support

- Issues: https://github.com/ashai/ashai/issues
- Discord: https://discord.gg/ashai

🎉 **You're saving $580+/month with Claude Code integration!**