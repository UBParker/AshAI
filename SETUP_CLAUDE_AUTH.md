# Setting Up Claude CLI Authentication in Docker

## Prerequisites

### 1. Install XQuartz (for macOS)
```bash
brew install --cask xquartz
```

After installation, you need to:
1. Open XQuartz from Applications/Utilities
2. In XQuartz preferences, go to the "Security" tab
3. Check "Allow connections from network clients"
4. Restart XQuartz

### 2. Enable X11 Forwarding
```bash
# Allow Docker to connect to X11
xhost +localhost

# Or more permissive (less secure but works better with Docker)
xhost +
```

## Running the Authentication Container

### Step 1: Start the container in authentication mode
```bash
# Run with X11 forwarding
docker run -it --rm \
  -e DISPLAY=host.docker.internal:0 \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  --name claude-auth \
  ashai-claude-auth:latest auth
```

### Step 2: Complete authentication in browser
The container will open a browser window where you can:
1. Log in to your Claude account
2. Complete the authentication process
3. The CLI will save the credentials

### Step 3: Commit the authenticated container
After successful authentication, in a new terminal:
```bash
# Get the container ID
docker ps

# Commit the container with saved credentials
docker commit claude-auth ashai-claude-authenticated:latest

# Stop the auth container
docker stop claude-auth
```

## Using the Authenticated Image

Now you can spawn multiple containers using the authenticated image:

```bash
# Run authenticated containers for agents
docker run -d \
  --name claude-agent-1 \
  -p 8001:8000 \
  ashai-claude-authenticated:latest

docker run -d \
  --name claude-agent-2 \
  -p 8002:8000 \
  ashai-claude-authenticated:latest

# And so on...
```

## Alternative: Headless Authentication with VNC

If X11 forwarding doesn't work, we can use VNC:

### 1. Build VNC-enabled image
```dockerfile
# Add to Dockerfile
RUN apk add --no-cache x11vnc novnc websockify supervisor
```

### 2. Run with VNC
```bash
docker run -d \
  -p 5900:5900 \
  -p 6080:6080 \
  --name claude-auth-vnc \
  ashai-claude-auth:latest auth
```

### 3. Connect via VNC
- VNC Viewer: Connect to `localhost:5900`
- Web browser: Open `http://localhost:6080/vnc.html`

## Troubleshooting

### XQuartz not working
1. Make sure XQuartz is running
2. Check DISPLAY variable: `echo $DISPLAY`
3. Try: `defaults write org.xquartz.X11 enable_iglx -bool true`

### Container can't connect to X11
1. Check xhost permissions: `xhost`
2. Try more permissive: `xhost +local:docker`
3. Restart Docker Desktop

### Authentication fails
1. Make sure you're using the correct Claude account
2. Check container logs: `docker logs claude-auth`
3. Try clearing browser cache in container

## Security Notes

- The authenticated image contains your Claude session credentials
- Don't push this image to public registries
- Store it securely and only use locally
- Credentials may expire - rebuild when needed