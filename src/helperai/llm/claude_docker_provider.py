"""Claude Docker Provider - Manages Docker containers running Claude Code Desktop."""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from typing import AsyncIterator, Optional
import aiohttp
import docker
from docker.models.containers import Container

from helperai.llm.message_types import Message

logger = logging.getLogger(__name__)


class ClaudeDockerProvider:
    """Provider that spawns Docker containers running Claude CLI.

    Each agent gets its own container with Claude CLI, using your subscription.
    No API costs - just your $20/month Claude subscription!
    Lightweight containers - only 525MB each!
    """

    def __init__(
        self,
        image_name: str = "ashai-claude-cli",
        container_prefix: str = "claude-agent",
        max_containers: int = 10,
    ):
        self.name = "claude_docker"
        self.model_names = ["claude-code"]
        self.image_name = image_name
        self.container_prefix = container_prefix
        self.max_containers = max_containers
        self.docker_client = None
        self.container_pool: dict[str, Container] = {}
        self.available_containers: list[Container] = []
        self._init_lock = asyncio.Lock()

    async def _ensure_initialized(self):
        """Initialize Docker client and build image if needed."""
        async with self._init_lock:
            if self.docker_client is None:
                try:
                    self.docker_client = docker.from_env()

                    # Check if image exists, build if not
                    try:
                        self.docker_client.images.get(self.image_name)
                        logger.info(f"Docker image {self.image_name} found")
                    except docker.errors.ImageNotFound:
                        logger.info(f"Building Docker image {self.image_name}...")
                        # Build the image
                        result = subprocess.run(
                            ["docker", "build", "-f", "Dockerfile.consolidated-claude-desktop",
                             "--build-arg", "WITH_ELECTRON=true",
                             "-t", self.image_name, "."],
                            capture_output=True,
                            text=True
                        )
                        if result.returncode != 0:
                            raise Exception(f"Failed to build Docker image: {result.stderr}")
                        logger.info(f"Successfully built {self.image_name}")

                    # Check for existing containers and reuse them
                    await self._discover_existing_containers()

                    # Pre-spawn initial containers if needed
                    if not self.available_containers:
                        await self._spawn_initial_containers()

                except (docker.errors.DockerException, subprocess.SubprocessError, OSError) as e:
                    logger.error(f"Failed to initialize Docker: {e}")
                    raise

    async def _discover_existing_containers(self):
        """Discover and reuse existing containers."""
        try:
            containers = self.docker_client.containers.list(all=True)
            for container in containers:
                if container.name.startswith(self.container_prefix):
                    if container.status == 'running':
                        logger.info(f"Found existing running container: {container.name}")
                        self.available_containers.append(container)
                    elif container.status == 'exited':
                        logger.info(f"Restarting stopped container: {container.name}")
                        container.start()
                        await asyncio.sleep(2)
                        self.available_containers.append(container)
            logger.info(f"Discovered {len(self.available_containers)} existing containers")
        except docker.errors.DockerException as e:
            logger.error(f"Failed to discover existing containers: {e}")

    async def _spawn_initial_containers(self):
        """Pre-spawn containers for faster agent creation."""
        logger.info("Pre-spawning Claude Code containers...")
        existing_count = len(self.available_containers)
        for i in range(existing_count, min(3, self.max_containers)):
            container = await self._spawn_container(f"{self.container_prefix}-{i}")
            if container:
                self.available_containers.append(container)
        logger.info(f"Pre-spawned {len(self.available_containers) - existing_count} new containers")

    async def _spawn_container(self, name: str) -> Optional[Container]:
        """Spawn a new Claude Code container."""
        try:
            # Check if container already exists
            try:
                existing = self.docker_client.containers.get(name)
                if existing.status == 'running':
                    logger.info(f"Container {name} already running")
                    return existing
                else:
                    logger.info(f"Starting stopped container {name}")
                    existing.start()
                    await asyncio.sleep(2)
                    return existing
            except docker.errors.NotFound:
                pass  # Container doesn't exist, create new one

            import os
            home_dir = os.path.expanduser("~")
            container = self.docker_client.containers.run(
                self.image_name,
                name=name,
                detach=True,
                remove=False,
                ports={'8000/tcp': None},  # Random port assignment
                environment={
                    'DISPLAY': ':99',
                    'AGENT_NAME': name,
                    'HOME': '/home/claude',
                },
                volumes={
                    f'{home_dir}/.claude-auth.json': {'bind': '/home/claude/.claude-auth.json', 'mode': 'ro'}
                }
            )

            # Wait for container to be ready
            await asyncio.sleep(5)

            logger.info(f"Spawned container {name} with ID {container.short_id}")
            return container

        except docker.errors.DockerException as e:
            logger.error(f"Failed to spawn container {name}: {e}")
            return None

    async def _get_container(self, agent_id: str) -> Container:
        """Get or create a container for an agent."""
        await self._ensure_initialized()

        # Check if agent already has a container
        if agent_id in self.container_pool:
            return self.container_pool[agent_id]

        # Use available container or spawn new one
        if self.available_containers:
            container = self.available_containers.pop(0)
            logger.info(f"Assigning pre-spawned container to agent {agent_id}")
        else:
            if len(self.container_pool) >= self.max_containers:
                raise Exception(f"Maximum containers ({self.max_containers}) reached")
            container = await self._spawn_container(f"{self.container_prefix}-{agent_id}")
            if not container:
                raise Exception(f"Failed to spawn container for agent {agent_id}")

        self.container_pool[agent_id] = container

        # Spawn replacement for pool
        asyncio.create_task(self._replenish_pool())

        return container

    async def _replenish_pool(self):
        """Replenish the pool of available containers."""
        if len(self.available_containers) < 2 and len(self.container_pool) < self.max_containers - 2:
            container = await self._spawn_container(
                f"{self.container_prefix}-pool-{len(self.container_pool)}"
            )
            if container:
                self.available_containers.append(container)

    def _get_container_port(self, container: Container) -> int:
        """Get the mapped port for a container."""
        container.reload()
        ports = container.attrs['NetworkSettings']['Ports']
        if '8000/tcp' in ports and ports['8000/tcp']:
            return int(ports['8000/tcp'][0]['HostPort'])
        raise Exception(f"No port mapping found for container {container.name}")

    async def stream(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
        stream: bool = True,
        **kwargs,
    ) -> AsyncIterator[dict]:
        """Send messages to a Claude Code container."""

        # Extract agent_id from kwargs or use default
        agent_id = kwargs.get('agent_id', 'default')

        # Get container for this agent
        container = await self._get_container(agent_id)
        port = self._get_container_port(container)

        # Format messages for the container's API
        formatted_messages = []
        for msg in messages:
            formatted_msg = {
                "role": msg.role,
                "content": msg.content or ""
            }
            if msg.tool_calls:
                formatted_msg["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                formatted_msg["tool_call_id"] = msg.tool_call_id
            formatted_messages.append(formatted_msg)

        # Send to container's API endpoint
        url = f"http://localhost:{port}/api/chat"
        payload = {
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }

        if tools:
            # Convert ToolDefinition objects to dicts
            tool_dicts = []
            for tool in tools:
                if hasattr(tool, 'to_openai_dict'):
                    tool_dicts.append(tool.to_openai_dict())
                elif isinstance(tool, dict):
                    tool_dicts.append(tool)
                else:
                    # Try to convert to dict
                    tool_dicts.append(dict(tool))
            payload["tools"] = tool_dicts
        if tool_choice:
            payload["tool_choice"] = tool_choice

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=300, connect=10)
        ) as session:
            async with session.post(url, json=payload) as response:
                if not response.ok:
                    error = await response.text()
                    raise Exception(f"Container API error: {error}")

                if stream:
                    async for line in response.content:
                        if line:
                            try:
                                data = json.loads(line.decode('utf-8').strip())
                                yield data
                            except json.JSONDecodeError:
                                continue
                else:
                    data = await response.json()
                    yield data

    async def list_models(self) -> list[dict]:
        """List available models (always Claude CLI via subscription)."""
        return [
            {
                "id": "claude-code",
                "name": "Claude CLI (Lightweight)",
                "description": "Claude via your subscription - NO API COSTS! Only 525MB containers!",
                "context_window": 200000,
                "max_tokens": 4096,
                "cost_per_million": 0,  # FREE with subscription!
            }
        ]

    async def cleanup_agent(self, agent_id: str):
        """Clean up container when agent is done."""
        if agent_id in self.container_pool:
            container = self.container_pool[agent_id]
            try:
                container.stop(timeout=5)
                container.remove()
                logger.info(f"Cleaned up container for agent {agent_id}")
            except docker.errors.DockerException as e:
                logger.error(f"Failed to cleanup container: {e}")
            finally:
                del self.container_pool[agent_id]

    # Alias for backward compatibility
    send_message = stream

    async def cleanup_all(self):
        """Clean up all containers on shutdown."""
        logger.info("Cleaning up all Claude Code containers...")

        # Stop pool containers
        for container in self.available_containers:
            try:
                container.stop(timeout=2)
                container.remove()
            except docker.errors.DockerException:
                pass

        # Stop agent containers
        for agent_id in list(self.container_pool.keys()):
            await self.cleanup_agent(agent_id)

        if self.docker_client:
            self.docker_client.close()

        logger.info("Container cleanup complete")