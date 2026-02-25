#!/bin/bash

# Start virtual display
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99

# Start VNC server (optional, for debugging)
x11vnc -display :99 -forever -usepw -create &

# Start window manager
fluxbox &

# Wait for display to be ready
sleep 2

# Launch Claude Code AppImage
/opt/claude-code.AppImage --no-sandbox --disable-gpu-sandbox &

# Wait for Claude Code to start
sleep 5

# Start the automation API server
cd /home/claude/automation
python3 api_server.py