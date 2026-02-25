#!/bin/bash
# Helper script to authenticate Claude CLI in container

AUTH_CODE="cMRP3Qb2Qq23FQCO6GvgHaXrGElVeCWexzZsR7P7TQrJc6Qa#TBQEuAsljEX7zjB1fn6mG96zkSEjNANsB-Xopc3dj1w"

echo "Attempting to send auth code to container..."
docker exec -i 173ef3cd211a sh -c "echo '$AUTH_CODE' | head -1"