#!/bin/bash
# Send authentication code to Claude CLI container

AUTH_CODE="cMRP3Qb2Qq23FQCO6GvgHaXrGElVeCWexzZsR7P7TQrJc6Qa#TBQEuAsljEX7zjB1fn6mG96zkSEjNANsB-Xopc3dj1w"

echo "Sending authentication code to container..."
echo "$AUTH_CODE" | docker attach claude-auth-new