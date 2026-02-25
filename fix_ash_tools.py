#!/usr/bin/env python3
"""Fix Ash's tools in the database"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select, update
from helperai.db.engine import get_session_factory, init_db
from helperai.db.models import Agent as AgentModel
from helperai.agents.eve import EVE_TOOL_NAMES

async def fix_ash_tools():
    await init_db()
    session_factory = get_session_factory()

    async with session_factory() as session:
        # Find Ash
        result = await session.execute(
            select(AgentModel).where(AgentModel.name == "Ash")
        )
        ash = result.scalar_one_or_none()

        if not ash:
            print("Ash not found!")
            return

        print(f"Found Ash (ID: {ash.id})")
        print(f"Current tools: {ash.tool_names}")

        # Update tools
        ash.tool_names = EVE_TOOL_NAMES
        await session.commit()

        print(f"Updated tools to: {ash.tool_names}")

        # Verify
        await session.refresh(ash)
        print(f"Verified tools: {ash.tool_names}")

if __name__ == "__main__":
    asyncio.run(fix_ash_tools())