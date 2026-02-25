#!/bin/sh
# Entrypoint for Claude CLI authentication with X11 forwarding

if [ "$1" = "auth" ]; then
    echo "Starting Claude CLI authentication..."
    echo "================================================"
    echo "A browser window will open on your Mac display."
    echo "Please log in to your Claude account."
    echo "After authentication completes, the container"
    echo "will save the credentials."
    echo "================================================"

    # Set display for macOS Docker Desktop
    export DISPLAY=host.docker.internal:0

    # Try to authenticate using Claude CLI
    # This will open Chromium browser on your Mac display
    claude auth login

    if [ $? -eq 0 ]; then
        echo "================================================"
        echo "Authentication successful!"
        echo "You can now commit this container to save auth:"
        echo "docker commit $(hostname) ashai-claude-final:latest"
        echo "================================================"
        # Keep container running so it can be committed
        tail -f /dev/null
    else
        echo "Authentication failed. Please try again."
        exit 1
    fi
else
    echo "Starting Claude CLI server..."
    python3 /home/claude/claude_cli_server.py
fi