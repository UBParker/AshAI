#!/usr/bin/env python3
"""Test if Ash has tools properly loaded"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_ash():
    # Initialize helperai components
    from helperai.config import get_settings
    from helperai.db.engine import init_db, get_session_factory
    from helperai.core.events import EventBus
    from helperai.llm.registry import LLMRegistry
    from helperai.llm.openai_compat import OpenAICompatProvider
    from helperai.tools.registry import ToolRegistry
    from helperai.agents.manager import AgentManager
    from sqlalchemy import select
    from helperai.db.models import Agent as AgentModel

    settings = get_settings()
    await init_db()

    # Setup components
    event_bus = EventBus()
    llm_registry = LLMRegistry()

    # Register Claude terminal provider
    from helperai.llm.claude_terminal_provider import ClaudeTerminalProvider
    claude_terminal = ClaudeTerminalProvider()
    llm_registry.register(claude_terminal, is_default=True)

    # Setup tool registry
    tool_registry = ToolRegistry()

    # Register tools
    from helperai.tools.builtin.spawn_agent import SpawnAgentTool
    from helperai.tools.builtin.list_agents import ListAgentsTool
    from helperai.tools.builtin.message_agent import MessageAgentTool

    tool_registry.register("spawn_agent", SpawnAgentTool())
    tool_registry.register("list_agents", ListAgentsTool())
    tool_registry.register("message_agent", MessageAgentTool())

    print("Registered tools:", list(tool_registry._tools.keys()))

    # Create agent manager
    agent_manager = AgentManager(
        settings=settings,
        llm_registry=llm_registry,
        tool_registry=tool_registry,
        event_bus=event_bus,
    )

    # Initialize Eve
    eve = await agent_manager.init_eve()
    print(f"\nEve initialized: {eve.id}")
    print(f"Eve name: {eve.name}")
    print(f"Eve tools in DB: {eve.tool_names}")

    # Check in-memory agent
    if eve.id in agent_manager._agents:
        agent = agent_manager._agents[eve.id]
        print(f"Eve tools in memory: {list(agent.tools.keys())}")

        # Test if spawn_agent tool is actually there
        if 'spawn_agent' in agent.tools:
            print("✓ spawn_agent tool is loaded!")
            spawn_tool = agent.tools['spawn_agent']
            print(f"  Tool definition: {spawn_tool.definition.name}")
        else:
            print("✗ spawn_agent tool is NOT loaded!")
    else:
        print("✗ Eve not in agent manager's memory!")

if __name__ == "__main__":
    asyncio.run(test_ash())