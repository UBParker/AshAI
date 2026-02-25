#!/bin/bash
# Start virtual display for Claude Code
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99

# Optional: Start VNC server for debugging (view at localhost:6080)
x11vnc -display :99 -forever -nopw -quiet -shared &

# Start window manager
fluxbox &

# Wait for display to be ready
sleep 2

# Launch Claude Code
/opt/claude-code.AppImage --no-sandbox &

# Wait for Claude Code to start
sleep 5

# Start the Python automation server
cd /home/claude/automation
python3 -m claude_agent_server