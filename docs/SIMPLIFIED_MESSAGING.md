# Simplified Agent Messaging System

## Overview
Replaced complex signal file system with direct HTTP API messaging between agents.

## Original Problem
- Complex signal file watching system
- Agents couldn't receive messages when idle
- Reports from sub-agents weren't reaching Ash
- Over-engineered file-based communication

## Solution Implemented

### 1. Direct API Messaging Tools
Created simple Python scripts for agent communication:

#### `message_agent_simple.py`
```python
# Send message directly to any agent via HTTP API
response = requests.post(f"http://localhost:8000/api/agents/{agent_id}/message",
                         json={"message": message})
```

#### `report_to_eve_simple.py`
```python
# Report back to Eve/Ash using inject_message
manager.inject_message(parent_id, f"Report from {agent_name}: {report}")
```

### 2. Auto-Start for Idle Agents
Added automatic agent startup when receiving messages:

```python
# In API endpoint
if not manager.is_agent_started(agent_id):
    await manager.start_agent(agent_id)

# In inject_message
if not self.is_agent_started(agent_id):
    await self.start_agent(agent_id)
```

### 3. Message Queue System
- Confirmed existing `asyncio.Queue` for busy agents
- Messages queue when agent is RUNNING
- Process queue when agent returns to IDLE
- Cancel clears the queue

## Benefits
- **Simple**: Direct HTTP calls instead of file watching
- **Reliable**: Agents auto-start when needed
- **Efficient**: Built-in queuing for busy agents
- **Clean**: No leftover signal files

## Usage
Agents can now simply:
1. Send messages via HTTP POST
2. Report back using inject_message
3. Messages automatically queue if busy
4. Auto-start if agent is idle

## Files Created
- `message_agent_simple.py` - Direct agent messaging
- `report_to_eve_simple.py` - Reporting tool
- Removed complex signal file handlers