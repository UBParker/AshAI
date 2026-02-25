#!/usr/bin/env python3
"""Test script for Claude web automation."""

import asyncio
import logging
import os
from dotenv import load_dotenv

# Add src to path for imports
import sys
sys.path.insert(0, 'src')

from helperai.llm.claude_web_provider import ClaudeWebProvider
from helperai.llm.message_types import Message

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_claude_web():
    """Test the Claude web automation provider."""
    
    # Get credentials from environment (try both naming conventions)
    email = os.getenv("HELPERAI_CLAUDE_WEB_EMAIL") or os.getenv("CLAUDE_WEB_EMAIL")
    password = os.getenv("HELPERAI_CLAUDE_WEB_PASSWORD") or os.getenv("CLAUDE_WEB_PASSWORD")
    
    if not email or not password:
        logger.error("Please set HELPERAI_CLAUDE_WEB_EMAIL and HELPERAI_CLAUDE_WEB_PASSWORD environment variables")
        logger.info("You can also use CLAUDE_WEB_EMAIL and CLAUDE_WEB_PASSWORD for backward compatibility")
        return
    
    logger.info("Starting Claude web automation test...")
    
    # Create provider
    provider = ClaudeWebProvider(
        email=email,
        password=password,
        headless=False,  # Set to False to see the browser in action
        timeout=30000
    )
    
    try:
        # Test message
        messages = [
            Message(role="user", content="Hello! Please respond with a simple greeting.")
        ]
        
        logger.info("Sending test message to Claude...")
        
        # Stream the response
        async for chunk in provider.stream(messages, "claude-3-5-sonnet-20241022"):
            logger.info(f"Received chunk: {chunk.delta_content[:100]}...")
            if chunk.finish_reason:
                logger.info(f"Stream finished with reason: {chunk.finish_reason}")
                
        logger.info("Test completed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        
    finally:
        await provider.close()


if __name__ == "__main__":
    asyncio.run(test_claude_web())