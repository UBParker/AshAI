"""Claude Code Desktop App Provider - Clean automation of the desktop app."""

import asyncio
import logging
from typing import AsyncIterator, Optional
from playwright.async_api import async_playwright, Page, Browser, Error as PlaywrightError

from helperai.llm.base import BaseLLMProvider
from helperai.llm.message_types import Message, ToolCall

logger = logging.getLogger(__name__)


class ClaudeCodeProvider(BaseLLMProvider):
    """Provider that automates Claude Code desktop app instead of web."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.playwright = None

    async def initialize(self):
        """Launch Claude Code and prepare for automation."""
        self.playwright = await async_playwright().start()

        # Launch Electron app (Claude Code)
        # Much cleaner than browser automation!
        self.browser = await self.playwright.chromium.launch_persistent_context(
            user_data_dir="/home/claude/.config/Claude",
            headless=self.headless,
            args=[
                '--app=/opt/claude-code.AppImage',  # Launch Claude Code directly
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage'
            ]
        )

        # Get the main window
        self.page = self.browser.pages[0] if self.browser.pages else await self.browser.new_page()

        # Wait for Claude Code to fully load
        await self.page.wait_for_load_state('networkidle')
        await asyncio.sleep(2)

        logger.info("Claude Code desktop app launched successfully")

    async def send_message(self, messages: list[Message]) -> AsyncIterator[dict]:
        """Send message through Claude Code's native interface."""
        if not self.page:
            await self.initialize()

        try:
            # Get the last user message
            user_message = messages[-1].content if messages else ""

            # Claude Code has a much cleaner interface than web
            # Find the message input (consistent across versions)
            input_selector = 'textarea[data-testid="message-input"], textarea[placeholder*="Message"], .message-input'

            # Clear and type message
            await self.page.fill(input_selector, user_message)

            # Send message (Enter key or send button)
            await self.page.press(input_selector, 'Enter')

            # Stream the response
            response_selector = '.message-content:last-child, [data-testid="assistant-message"]:last-child'

            last_content = ""
            max_wait_seconds = 300
            elapsed = 0.0
            while elapsed < max_wait_seconds:
                # Get current response text
                element = await self.page.query_selector(response_selector)
                if element:
                    current_content = await element.inner_text()

                    # Yield new content
                    if current_content and current_content != last_content:
                        new_text = current_content[len(last_content):]
                        yield {"type": "content", "text": new_text}
                        last_content = current_content

                # Check if response is complete
                # Claude Code shows a clear indicator when done
                is_complete = await self.page.evaluate("""
                    () => {
                        const typing = document.querySelector('.typing-indicator, .generating');
                        return !typing;
                    }
                """)

                if is_complete and last_content:
                    break

                await asyncio.sleep(0.1)
                elapsed += 0.1
            else:
                yield {"type": "error", "error": "Response timed out after 300 seconds"}

        except PlaywrightError as e:
            logger.error(f"Error sending message: {e}")
            yield {"type": "error", "error": str(e)}

    async def create_conversation(self) -> str:
        """Start a new conversation in Claude Code."""
        if not self.page:
            await self.initialize()

        # Claude Code: Cmd+N or click New Chat
        await self.page.keyboard.press('Meta+N')  # Mac
        # await self.page.keyboard.press('Control+N')  # Linux/Windows

        return "claude-code-session"

    def list_models(self) -> list[str]:
        """Claude Code uses your subscription's available models."""
        return [
            "claude-3-5-sonnet",  # Latest Sonnet
            "claude-3-5-haiku",   # Fast responses
            "claude-3-opus"       # Most capable
        ]

    async def cleanup(self):
        """Clean shutdown of Claude Code."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


class ClaudeCodeAgentProvider(ClaudeCodeProvider):
    """Extended provider for running agents through Claude Code."""

    def __init__(self, agent_name: str, headless: bool = True):
        super().__init__(headless)
        self.agent_name = agent_name
        self.conversation_id = None

    async def initialize_agent(self, system_prompt: str):
        """Set up a dedicated conversation for this agent."""
        await self.initialize()

        # Create new conversation for this agent
        self.conversation_id = await self.create_conversation()

        # Set context with system prompt
        # Claude Code respects markdown formatting
        initial_message = f"""
# Agent: {self.agent_name}

## System Context:
{system_prompt}

---

I understand my role and am ready to begin.
"""

        # Send the initialization
        await self.page.fill('textarea', initial_message)
        await self.page.press('textarea', 'Enter')

        # Wait for acknowledgment
        await asyncio.sleep(2)

        logger.info(f"Agent {self.agent_name} initialized in Claude Code")

    async def execute_task(self, task: str) -> str:
        """Execute a specific task as this agent."""
        messages = [Message(role="user", content=task)]

        response = ""
        async for chunk in self.send_message(messages):
            if chunk["type"] == "content":
                response += chunk["text"]

        return response


# Provider registration
def register_claude_code_provider():
    """Register this provider with AshAI."""
    from helperai.llm.registry import LLMRegistry

    registry = LLMRegistry()
    registry.register("claude_code", ClaudeCodeProvider)
    registry.register("claude_code_agent", ClaudeCodeAgentProvider)

    logger.info("Claude Code provider registered successfully")