# Agent Error Analysis

## Problem Summary
Multiple agents (Ash, DockerConsolidator, TestEngineer, FrontendDev) went into error state due to Claude CLI timeout issues.

## Root Cause Analysis

### 1. Timeout Configuration Mismatch
- **Error Message**: "Claude CLI request timed out after 120 seconds"
- **Location**: `src/helperai/llm/claude_terminal_provider.py` line 139
- **Issue**: Hardcoded error message says "120 seconds" but actual timeout is 300 seconds (5 minutes)

```python
# Line 104: Actual timeout
timeout=aiohttp.ClientTimeout(total=300)  # Increased to 5 minutes

# Line 139: Error message
raise Exception("Claude CLI request timed out after 120 seconds")
```

### 2. Cascading Failures
The errors show a pattern where multiple agents failed in sequence:
- Initial agents (603bd01c573d, 6c47fb9a1b1a, etc.) timed out
- Then DockerConsolidator, TestEngineer, FrontendDev failed
- Finally Ash itself went into error state

### 3. Signal File Errors
Before the timeouts, there were signal file processing errors:
```
Error processing signal file /Users/bravo/work/alphabravo/ashai/AshAI/.ashai_signal_7ac951b5a630.json: [Errno 2] No such file or directory
```
This suggests the old signal system was still trying to process files that had been deleted.

## What We Learned

### 1. Timeout Handling Needs Improvement
- **Current State**: 5-minute timeout might be too long for responsive UI
- **Recommendation**: Consider:
  - Shorter timeouts (30-60 seconds)
  - Different timeouts for different operations
  - Better timeout error messages that match actual values

### 2. Error State Recovery
- **Issue**: Agents get stuck in error state with no automatic recovery
- **Solution Needed**:
  - Auto-retry mechanism
  - Automatic cleanup of error agents after X minutes
  - Better error state handling in manager

### 3. Cancel Feature is Critical
- **Validation**: The cancel feature we implemented is essential
- **Why**: Without it, users would wait 5 minutes for timeouts
- **Impact**: Cancel allows immediate recovery from stuck operations

### 4. Message Queue Behavior
- **Observation**: When an agent times out, queued messages remain
- **Risk**: Could lead to cascading timeouts if not handled
- **Current Solution**: Cancel clears the queue

## Recommended Improvements

### 1. Immediate Fix - Timeout Message
```python
# Line 139 in claude_terminal_provider.py should be:
raise Exception("Claude CLI request timed out after 300 seconds")
```

### 2. Short-term - Timeout Configuration
```python
# Add configurable timeout
class ClaudeTerminalProvider:
    def __init__(self, timeout_seconds: int = 60):
        self.timeout = timeout_seconds
```

### 3. Medium-term - Error Recovery
- Add auto-cleanup for agents in error state > 5 minutes
- Implement retry logic with exponential backoff
- Add health check endpoint for Claude CLI container

### 4. Long-term - Resilience
- Circuit breaker pattern for Claude CLI calls
- Fallback to alternative providers on timeout
- Better error messages with actionable steps

## Status After Cleanup
- Deleted 3 error agents (DockerConsolidator, TestEngineer, FrontendDev)
- Ash needs to be reset to idle
- System is ready for normal operation
- Cancel feature prevents future stuck states

## Root Cause: File Permission Issue

### Discovery
The Claude CLI container has a permissions mismatch:
- **Files are owned by**: `root:root`
- **Claude CLI runs as**: `claude` user
- **Mount point**: `/app/workspace` → `/Users/bravo/work/alphabravo/ashai/AshAI`

### Evidence
```bash
# Files in /app/workspace are owned by root
drwxr-xr-x 95 root   root    3040 Feb 25 05:18 .
-rw-r--r--  1 root   root    1380 Feb 22 05:38 .env

# But Claude CLI runs as claude user
claude    11413  /home/claude/.local/bin/claude --dangerously-skip-permissions
```

### Impact
- Claude CLI cannot write to `/app/workspace`
- Operations requiring file modifications timeout
- Agents fail when trying to edit or create files

### Solution Options

1. **Quick Fix**: Change ownership of mounted files
   ```bash
   docker exec claude-cli chown -R claude:claude /app/workspace
   ```

2. **Docker Compose Fix**: Add user mapping
   ```yaml
   volumes:
     - ./:/app/workspace
   user: "${UID}:${GID}"  # Match host user
   ```

3. **Dockerfile Fix**: Run as root (security concern)
   ```dockerfile
   USER root  # Instead of USER claude
   ```

4. **Recommended**: Use init script to fix permissions on startup
   ```bash
   # In entrypoint script
   chown -R claude:claude /app/workspace
   ```