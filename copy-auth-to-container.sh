#!/bin/bash
# Script to copy local Claude authentication into Docker container

# Extract auth from macOS keychain
security find-generic-password -s "Claude Code" -w > /tmp/claude-auth.json 2>/dev/null

if [ ! -s /tmp/claude-auth.json ]; then
    echo "Could not extract auth from keychain. Trying config file..."
    # Try to find auth in config directory
    AUTH_FILE="$HOME/.config/@anthropic-ai/claude-code/auth.json"
    if [ -f "$AUTH_FILE" ]; then
        cp "$AUTH_FILE" /tmp/claude-auth.json
    else
        echo "No auth file found at $AUTH_FILE"
        exit 1
    fi
fi

echo "Auth extracted successfully"

# Build container with auth embedded
cat > /tmp/Dockerfile.authenticated <<EOF
FROM ashai-claude-cli:latest

# Copy auth file into container
COPY claude-auth.json /home/claude/.config/@anthropic-ai/claude-code/auth.json
RUN chown -R claude:claude /home/claude/.config

USER claude
WORKDIR /home/claude

EXPOSE 8000
CMD ["python3", "claude_cli_server.py"]
EOF

# Build authenticated image
cd /tmp
docker build -f Dockerfile.authenticated -t ashai-claude-authenticated:latest .

echo "Authenticated image built successfully: ashai-claude-authenticated:latest"

# Clean up temp files
rm -f /tmp/claude-auth.json /tmp/Dockerfile.authenticated

echo "You can now run authenticated containers with:"
echo "docker run -d -p 8001:8000 --name claude-agent-1 ashai-claude-authenticated:latest"