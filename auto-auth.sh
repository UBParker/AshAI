#!/bin/bash
# Automated authentication script for Claude CLI in Docker

AUTH_CODE="cMRP3Qb2Qq23FQCO6GvgHaXrGElVeCWexzZsR7P7TQrJc6Qa#TBQEuAsljEX7zjB1fn6mG96zkSEjNANsB-Xopc3dj1w"

# Start container and get its ID
echo "Starting authentication container..."
CONTAINER_ID=$(docker run -d --name claude-auth-auto ashai-claude-auth:latest tail -f /dev/null)

echo "Container started: $CONTAINER_ID"
sleep 2

# Run authentication in background and capture PID
echo "Starting authentication process..."
docker exec -i claude-auth-auto sh -c 'claude auth login' &
AUTH_PID=$!

# Wait for the prompt (give it some time to start)
sleep 3

# Send the auth code
echo "Sending authentication code..."
echo "$AUTH_CODE" | docker attach claude-auth-auto

# Wait for completion
wait $AUTH_PID

echo "Checking authentication status..."
docker exec claude-auth-auto sh -c 'ls -la ~/.config/@anthropic-ai/claude-code/'

echo "To save the authenticated container:"
echo "docker commit claude-auth-auto ashai-claude-authenticated:latest"