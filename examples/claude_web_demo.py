#!/usr/bin/env python3
"""
Claude Web Automation Demo

This script demonstrates how to use the Claude web automation provider
to interact with Claude.ai through browser automation.

Requirements:
1. Install playwright: pip install 'helperai[web-automation]'
2. Install browser: playwright install chromium
3. Set environment variables: CLAUDE_WEB_EMAIL and CLAUDE_WEB_PASSWORD
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

from helperai.llm.claude_web_provider import ClaudeWebProvider
from helperai.llm.message_types import Message

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def demo_basic_conversation():
    """Demonstrate basic conversation with Claude via web automation."""
    
    logger.info("=== Basic Conversation Demo ===")
    
    email = os.getenv("CLAUDE_WEB_EMAIL") or os.getenv("HELPERAI_CLAUDE_WEB_EMAIL")
    password = os.getenv("CLAUDE_WEB_PASSWORD") or os.getenv("HELPERAI_CLAUDE_WEB_PASSWORD")
    
    if not email or not password:
        logger.error("Please set CLAUDE_WEB_EMAIL and CLAUDE_WEB_PASSWORD environment variables")
        return
    
    # Create provider with visible browser for demonstration
    provider = ClaudeWebProvider(
        email=email,
        password=password,
        headless=False,  # Set to True for production use
        timeout=30000
    )
    
    try:
        # Test messages
        test_messages = [
            "Hello! Can you introduce yourself briefly?",
            "What's the capital of France?",
            "Write a simple Python function to calculate fibonacci numbers."
        ]
        
        for i, message_content in enumerate(test_messages, 1):
            logger.info(f"\\n--- Message {i} ---")
            logger.info(f"Sending: {message_content}")
            
            messages = [Message(role="user", content=message_content)]
            
            response_parts = []
            async for chunk in provider.stream(messages, "claude-3-5-sonnet-20241022"):
                if chunk.delta_content:
                    response_parts.append(chunk.delta_content)
                    print(chunk.delta_content, end='', flush=True)
                    
                if chunk.finish_reason:
                    logger.info(f"\\nStream finished: {chunk.finish_reason}")
                    break
            
            full_response = ''.join(response_parts)
            logger.info(f"Full response length: {len(full_response)} characters")
            
            # Wait a bit between messages
            if i < len(test_messages):
                logger.info("Waiting before next message...")
                await asyncio.sleep(3)
        
        logger.info("\\n=== Demo completed successfully! ===")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise
        
    finally:
        await provider.close()


async def demo_code_generation():
    """Demonstrate code generation capabilities."""
    
    logger.info("\\n=== Code Generation Demo ===")
    
    email = os.getenv("CLAUDE_WEB_EMAIL") or os.getenv("HELPERAI_CLAUDE_WEB_EMAIL")
    password = os.getenv("CLAUDE_WEB_PASSWORD") or os.getenv("HELPERAI_CLAUDE_WEB_PASSWORD")
    
    if not email or not password:
        logger.error("Please set CLAUDE_WEB_EMAIL and CLAUDE_WEB_PASSWORD environment variables")
        return
    
    provider = ClaudeWebProvider(
        email=email,
        password=password,
        headless=True,  # Run headless for this demo
        timeout=30000
    )
    
    try:
        code_prompt = '''
        Create a Python class for a simple task queue that can:
        1. Add tasks to the queue
        2. Process tasks one by one
        3. Track completed tasks
        4. Handle errors gracefully
        
        Include proper type hints and docstrings.
        '''
        
        messages = [Message(role="user", content=code_prompt)]
        
        logger.info("Requesting code generation...")
        
        response_parts = []
        async for chunk in provider.stream(messages, "claude-3-5-sonnet-20241022"):
            if chunk.delta_content:
                response_parts.append(chunk.delta_content)
                
            if chunk.finish_reason:
                break
        
        full_response = ''.join(response_parts)
        logger.info(f"Generated code ({len(full_response)} characters):")
        print("\\n" + "="*50)
        print(full_response)
        print("="*50)
        
    except Exception as e:
        logger.error(f"Code generation demo failed: {e}")
        
    finally:
        await provider.close()


async def demo_provider_integration():
    """Demonstrate integration with the LLM registry system."""
    
    logger.info("\\n=== Provider Integration Demo ===")
    
    from helperai.llm.registry import LLMRegistry
    
    email = os.getenv("CLAUDE_WEB_EMAIL") or os.getenv("HELPERAI_CLAUDE_WEB_EMAIL")
    password = os.getenv("CLAUDE_WEB_PASSWORD") or os.getenv("HELPERAI_CLAUDE_WEB_PASSWORD")
    
    if not email or not password:
        logger.error("Please set CLAUDE_WEB_EMAIL and CLAUDE_WEB_PASSWORD environment variables")
        return
    
    # Create registry and register Claude web provider
    registry = LLMRegistry()
    
    claude_web = ClaudeWebProvider(
        email=email,
        password=password,
        headless=True,
        timeout=30000
    )
    
    registry.register(claude_web, is_default=True)
    
    try:
        # Use provider through registry
        provider = registry.default
        logger.info(f"Using provider: {provider.name}")
        
        # List available models
        models = await provider.list_models()
        logger.info(f"Available models: {models}")
        
        # Send a message
        messages = [Message(role="user", content="Explain what you are in one sentence.")]
        
        async for chunk in provider.stream(messages, models[0]):
            if chunk.delta_content:
                print(chunk.delta_content, end='', flush=True)
            if chunk.finish_reason:
                print(f"\\nFinished: {chunk.finish_reason}")
                break
        
    except Exception as e:
        logger.error(f"Integration demo failed: {e}")
        
    finally:
        await claude_web.close()


async def main():
    """Run all demos."""
    
    logger.info("Starting Claude Web Automation Demos")
    logger.info("====================================")
    
    try:
        # Check if playwright is available
        try:
            import playwright
            logger.info(f"Playwright version: {playwright.__version__}")
        except ImportError:
            logger.error("Playwright not installed. Install with: pip install 'helperai[web-automation]'")
            return
        
        # Run demos
        await demo_basic_conversation()
        await demo_code_generation()
        await demo_provider_integration()
        
        logger.info("\\n🎉 All demos completed successfully!")
        
    except KeyboardInterrupt:
        logger.info("\\nDemo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())