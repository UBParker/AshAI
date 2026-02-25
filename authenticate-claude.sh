#!/bin/bash
# Script to authenticate Claude CLI in Docker container with X11 forwarding

echo "================================================"
echo "Claude CLI Docker Authentication"
echo "================================================"
echo ""
echo "This will open a browser window on your Mac."
echo "Please complete the authentication in the browser."
echo ""

# Make sure XQuartz allows connections
echo "Configuring X11 access..."
defaults write org.xquartz.X11 enable_iglx -bool true 2>/dev/null
defaults write org.xquartz.X11 nolisten_tcp -bool false 2>/dev/null

# Get IP for X11 display
DISPLAY_IP=$(ifconfig en0 | grep "inet " | awk '{print $2}')
if [ -z "$DISPLAY_IP" ]; then
    DISPLAY_IP="host.docker.internal"
fi

echo "Using display: $DISPLAY_IP:0"

# Run container with X11 forwarding
echo ""
echo "Starting authentication container..."
echo "================================================"

docker run -it \
    --name claude-auth-session \
    -e DISPLAY=${DISPLAY_IP}:0 \
    -e CHROMIUM_FLAGS="--no-sandbox" \
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
    ashai-claude-auth:latest \
    auth

echo ""
echo "================================================"
echo "To save the authenticated container:"
echo "docker commit claude-auth-session ashai-claude-final:latest"
echo "================================================"