"""
Signal file monitor for AshAI
Watches for .ashai_tool_signal.json files and processes them
"""

import asyncio
import json
import logging
import os
import threading
from pathlib import Path
from typing import Optional, Dict, Any
import aiofiles
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent

logger = logging.getLogger(__name__)


class SignalFileHandler(FileSystemEventHandler):
    """Handles signal file events.

    Matches both the legacy `.ashai_tool_signal.json` filename and
    the new UUID-based `.ashai_signal_*.json` pattern.
    Watches both on_created and on_modified to avoid missed events.
    """

    def __init__(self, callback):
        self.callback = callback
        self.loop = asyncio.get_event_loop()
        self._processed = set()  # Track processed files to avoid double-processing
        self._processed_lock = threading.Lock()  # Thread-safe access to _processed set

    def _is_signal_file(self, path: str) -> bool:
        basename = os.path.basename(path)
        return (
            basename == '.ashai_tool_signal.json'
            or (basename.startswith('.ashai_signal_') and basename.endswith('.json'))
        )

    def _handle_event(self, event):
        if not event.is_directory and self._is_signal_file(event.src_path):
            # Thread-safe check and add to avoid double-processing
            with self._processed_lock:
                if event.src_path in self._processed:
                    return
                self._processed.add(event.src_path)

            logger.info(f"Signal file detected: {event.src_path}")
            asyncio.run_coroutine_threadsafe(
                self._process_and_cleanup(event.src_path),
                self.loop
            )

    async def _process_and_cleanup(self, path: str):
        try:
            await self.callback(path)
        finally:
            # Thread-safe removal from processed set
            with self._processed_lock:
                self._processed.discard(path)

    def on_created(self, event):
        self._handle_event(event)

    def on_modified(self, event):
        self._handle_event(event)


class SignalFileMonitor:
    """Monitors for AshAI tool signal files"""

    def __init__(self, watch_dir: str = ".", agent_manager=None):
        self.watch_dir = Path(watch_dir).resolve()
        self.agent_manager = agent_manager
        self.observer = None
        logger.info(f"Signal monitor initialized for directory: {self.watch_dir}")

    async def process_signal_file(self, file_path: str):
        """Process a signal file and execute the corresponding action"""
        try:
            async with aiofiles.open(file_path, 'r') as f:
                content = await f.read()
                signal_data = json.loads(content)

            logger.info(f"Processing signal: {signal_data}")

            # Handle different signal types
            tool = signal_data.get('tool')
            arguments = signal_data.get('arguments', {})

            if tool == 'spawn_agent' and self.agent_manager:
                # Spawn a new agent
                await self._spawn_agent(arguments)
            elif tool == 'message_agent' and self.agent_manager:
                # Send message to existing agent
                await self._message_agent(arguments)
            elif tool == 'report_to_ash' and self.agent_manager:
                # Handle report to Ash
                await self._report_to_ash(arguments)
            else:
                logger.warning(f"Unknown signal tool: {tool}")

            # Delete the signal file after processing
            try:
                os.unlink(file_path)
                logger.info(f"Signal file deleted: {file_path}")
            except Exception as e:
                logger.error(f"Failed to delete signal file: {e}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in signal file {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error processing signal file {file_path}: {e}")

    async def _spawn_agent(self, arguments: Dict[str, Any]):
        """Spawn a new agent based on signal file arguments"""
        try:
            if not self.agent_manager:
                logger.error("Agent manager not available")
                return

            name = arguments.get('name', 'SignalAgent')
            role = arguments.get('role', 'assistant')
            model = arguments.get('model', 'claude-terminal')
            persona = arguments.get('persona', 'A helpful AI assistant')
            tools = arguments.get('tools', [])  # Get tools from arguments
            initial_message = arguments.get('initial_message', None)

            # Map model to provider
            provider_map = {
                'claude-terminal': 'claude_terminal',
                'claude-docker': 'claude_docker',
                'claude-api': 'anthropic'
            }
            provider = provider_map.get(model, 'claude_terminal')

            logger.info(f"Spawning agent: {name} with provider: {provider}")

            # If no tools specified, give the agent some basic tools
            if not tools:
                # Give spawned agents the ability to report back to Eve
                tools = ['report_to_eve']
                logger.info(f"No tools specified, adding default tools: {tools}")

            # Find Ash's ID to set as parent
            agents = await self.agent_manager.list_agents()
            ash = next((a for a in agents if a.parent_id is None and a.name == "Ash"), None)
            parent_id = ash.id if ash else None

            # Create the agent using the create_agent method with tools
            agent = await self.agent_manager.create_agent(
                name=name,
                role=f"{role}\n\n{persona}",
                goal="Help with tasks",
                parent_id=parent_id,  # Set Ash as the parent
                provider_name=provider,
                model_name="",  # Use default model for the provider
                tool_names=tools  # Pass the tools to the agent
            )
            # Agent is automatically added to the database by create_agent
            logger.info(f"Agent {name} spawned successfully with id: {agent.id}, tools: {tools}")

            # Start the agent to initialize it in memory
            await self.agent_manager.start_agent(agent.id)
            logger.info(f"Agent {name} started and ready to receive messages")

            # If initial_message provided, send it to the agent
            if initial_message:
                logger.info(f"Sending initial message to agent {name}: {initial_message[:100]}...")
                try:
                    async for event in self.agent_manager.send_message_stream(agent.id, initial_message):
                        # Just consume the stream, responses go through event bus
                        if event.get("type") == "error":
                            logger.error(f"Error sending initial message: {event.get('error')}")
                    logger.info(f"Initial message sent to agent {name}")
                except Exception as msg_error:
                    logger.error(f"Failed to send initial message to agent: {msg_error}")

        except Exception as e:
            logger.error(f"Failed to spawn agent: {e}")

    async def _message_agent(self, arguments: Dict[str, Any]):
        """Send a message to an existing agent based on signal file arguments"""
        try:
            if not self.agent_manager:
                logger.error("Agent manager not available")
                return

            agent_id = arguments.get('agent_id')
            message = arguments.get('message', '')

            if not agent_id:
                logger.error("No agent_id provided in message_agent signal")
                return

            if not message:
                logger.error("No message provided in message_agent signal")
                return

            # If agent_id is shortened, try to find the full ID
            if len(agent_id) < 12:
                agents = await self.agent_manager.list_agents()
                for agent in agents:
                    if agent.id.startswith(agent_id):
                        agent_id = agent.id
                        logger.info(f"Resolved short agent ID to: {agent_id}")
                        break

            logger.info(f"Sending message to agent {agent_id}: {message[:100]}...")

            # Ensure agent is started before sending message
            if not self.agent_manager.is_agent_started(agent_id):
                logger.info(f"Starting agent {agent_id} before sending message")
                await self.agent_manager.start_agent(agent_id)

            # Send message to the agent
            async for event in self.agent_manager.send_message_stream(agent_id, message):
                # Just consume the stream, the responses go through the event bus
                if event.get("type") == "error":
                    logger.error(f"Error sending message to agent: {event.get('error')}")

            logger.info(f"Message sent to agent {agent_id}")

        except Exception as e:
            logger.error(f"Failed to send message to agent: {e}")

    async def _report_to_ash(self, arguments: Dict[str, Any]):
        """Handle report sent to Ash"""
        try:
            if not self.agent_manager:
                logger.error("Agent manager not available")
                return

            message = arguments.get('message', '')
            sender = arguments.get('sender', 'Unknown')
            timestamp = arguments.get('timestamp', '')

            if not message:
                logger.error("No message provided in report_to_ash signal")
                return

            # Find Ash's agent ID
            agents = await self.agent_manager.list_agents()
            ash = next((a for a in agents if a.name == "Ash"), None)

            if not ash:
                logger.error("Ash agent not found")
                return

            report_message = f"Report from {sender}:\n\n{message}"
            logger.info(f"Sending report to Ash from {sender}: {message[:100]}...")

            # Send the report to Ash
            async for event in self.agent_manager.send_message_stream(ash.id, report_message):
                if event.get("type") == "error":
                    logger.error(f"Error sending report to Ash: {event.get('error')}")

            logger.info(f"Report sent to Ash from {sender}")

        except Exception as e:
            logger.error(f"Failed to send report to Ash: {e}")

    def start(self):
        """Start monitoring for signal files"""
        if self.observer:
            logger.warning("Monitor already running")
            return

        # Check for existing signal files (both legacy and UUID-based)
        import glob as glob_module
        existing_signals = (
            list(self.watch_dir.glob(".ashai_tool_signal.json"))
            + list(self.watch_dir.glob(".ashai_signal_*.json"))
        )
        for signal_file in existing_signals:
            logger.info(f"Found existing signal file: {signal_file}")
            asyncio.create_task(self.process_signal_file(str(signal_file)))

        # Start watching for new files
        self.observer = Observer()
        handler = SignalFileHandler(self.process_signal_file)
        self.observer.schedule(handler, str(self.watch_dir), recursive=False)
        self.observer.start()
        logger.info(f"Signal file monitor started for: {self.watch_dir}")

    def stop(self):
        """Stop monitoring"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            logger.info("Signal file monitor stopped")