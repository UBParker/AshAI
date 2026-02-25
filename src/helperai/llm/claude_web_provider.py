"""Claude.ai web automation provider using Playwright."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import AsyncIterator

from playwright.async_api import Error as PlaywrightError, Page, async_playwright

from helperai.core.exceptions import LLMError
from helperai.llm.message_types import Message, StreamChunk, ToolDefinition

logger = logging.getLogger(__name__)


class ClaudeWebProvider:
    """Claude.ai web automation provider using Playwright."""

    def __init__(
        self,
        email: str,
        password: str,
        headless: bool = True,
        timeout: int = 30000,
    ) -> None:
        self._name = "claude_web"
        self.email = email
        self.password = password
        self.headless = headless
        self.timeout = timeout
        self._browser = None
        self._context = None
        self._page: Page | None = None
        self._logged_in = False
        
    @property
    def name(self) -> str:
        return self._name

    async def _ensure_browser(self) -> None:
        """Ensure browser and page are initialized."""
        if self._browser is None:
            playwright = await async_playwright().start()
            self._browser = await playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security",
                    "--disable-features=VizDisplayCompositor",
                ]
            )
            self._context = await self._browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            self._page = await self._context.new_page()
            await self._page.set_default_timeout(self.timeout)

    async def _login(self) -> None:
        """Handle Claude.ai login flow."""
        if self._logged_in or not self._page:
            return
            
        logger.info("Navigating to Claude.ai login")
        await self._page.goto("https://claude.ai/login")
        
        try:
            # Wait for email input and fill it
            await self._page.wait_for_selector('input[type="email"]', timeout=10000)
            await self._page.fill('input[type="email"]', self.email)
            
            # Click continue/next button
            continue_btn = self._page.locator('button:has-text("Continue")')
            if await continue_btn.count() > 0:
                await continue_btn.click()
            else:
                # Try alternative selectors
                await self._page.click('button[type="submit"]')
            
            # Wait for password field and fill it
            await self._page.wait_for_selector('input[type="password"]', timeout=10000)
            await self._page.fill('input[type="password"]', self.password)
            
            # Click sign in button
            sign_in_btn = self._page.locator('button:has-text("Sign In")')
            if await sign_in_btn.count() > 0:
                await sign_in_btn.click()
            else:
                await self._page.click('button[type="submit"]')
            
            # Wait for successful login - look for chat interface
            await self._page.wait_for_selector('[data-testid="chat-input"], textarea[placeholder*="message"], .chat-input', timeout=15000)
            
            self._logged_in = True
            logger.info("Successfully logged into Claude.ai")
            
        except PlaywrightError as e:
            logger.error(f"Login failed: {e}")
            raise LLMError(f"Failed to login to Claude.ai: {e}")

    async def _start_new_conversation(self) -> None:
        """Start a new conversation in Claude.ai."""
        if not self._page:
            return
            
        try:
            # Look for new chat button
            new_chat_selectors = [
                'button:has-text("New Chat")',
                '[data-testid="new-chat"]',
                'button[aria-label*="new"]',
                '.new-chat-button',
                'a[href*="new"]'
            ]
            
            for selector in new_chat_selectors:
                try:
                    element = self._page.locator(selector)
                    if await element.count() > 0:
                        await element.first.click()
                        await asyncio.sleep(1)  # Give time for new chat to load
                        return
                except PlaywrightError:
                    continue

            # If no new chat button found, we might already be in a new chat
            logger.info("No new chat button found, assuming we're in a new conversation")

        except PlaywrightError as e:
            logger.warning(f"Could not start new conversation: {e}")

    async def _send_message(self, content: str) -> None:
        """Send a message to Claude."""
        if not self._page:
            raise LLMError("Browser not initialized")
            
        try:
            # Find the message input field
            input_selectors = [
                '[data-testid="chat-input"]',
                'textarea[placeholder*="message"]',
                'textarea[placeholder*="Message"]',
                '.chat-input textarea',
                'div[contenteditable="true"]',
                'textarea'
            ]
            
            input_element = None
            for selector in input_selectors:
                try:
                    element = self._page.locator(selector)
                    if await element.count() > 0:
                        input_element = element.first
                        break
                except PlaywrightError:
                    continue

            if not input_element:
                raise LLMError("Could not find message input field")
                
            # Clear and type the message
            await input_element.click()
            await input_element.fill(content)
            
            # Send the message
            send_selectors = [
                'button[data-testid="send-button"]',
                'button:has-text("Send")',
                'button[aria-label*="send"]',
                'button[type="submit"]'
            ]
            
            for selector in send_selectors:
                try:
                    send_btn = self._page.locator(selector)
                    if await send_btn.count() > 0:
                        await send_btn.click()
                        return
                except PlaywrightError:
                    continue

            # Fallback: try Enter key
            await input_element.press("Enter")
            
        except PlaywrightError as e:
            logger.error(f"Failed to send message: {e}")
            raise LLMError(f"Failed to send message: {e}")

    async def _wait_for_response(self) -> str:
        """Wait for Claude's response and extract it."""
        if not self._page:
            raise LLMError("Browser not initialized")
            
        try:
            # Wait for response to start appearing
            await asyncio.sleep(2)
            
            # Look for the response container
            response_selectors = [
                '.message:last-child .content',
                '.assistant-message:last-child',
                '[data-testid="message-content"]:last-child',
                '.chat-message:last-child .message-content',
                '.response-text:last-child'
            ]
            
            # Wait for response to be complete (no typing indicator)
            typing_indicators = [
                '.typing-indicator',
                '.loading',
                '.generating',
                '[data-testid="typing"]'
            ]
            
            # Wait a bit for response to start
            await asyncio.sleep(3)
            
            # Check if typing indicators are gone
            max_wait = 60  # Maximum wait time in seconds
            wait_time = 0
            while wait_time < max_wait:
                typing_active = False
                for indicator in typing_indicators:
                    try:
                        if await self._page.locator(indicator).count() > 0:
                            typing_active = True
                            break
                    except PlaywrightError:
                        continue

                if not typing_active:
                    break
                    
                await asyncio.sleep(1)
                wait_time += 1
                
            # Extract the response text
            for selector in response_selectors:
                try:
                    element = self._page.locator(selector)
                    if await element.count() > 0:
                        text = await element.inner_text()
                        if text.strip():
                            return text.strip()
                except PlaywrightError:
                    continue

            # Fallback: get all message content and return the last one
            try:
                messages = await self._page.locator('.message, .chat-message').all()
                if messages:
                    last_message = messages[-1]
                    text = await last_message.inner_text()
                    return text.strip()
            except PlaywrightError as e:
                logger.debug(f"Fallback message extraction failed: {e}")

            raise LLMError("Could not extract response from Claude.ai")
            
        except PlaywrightError as e:
            logger.error(f"Failed to get response: {e}")
            raise LLMError(f"Failed to get response: {e}")

    async def stream(
        self,
        messages: list[Message],
        model: str,
        *,
        temperature: float = 0.7,
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion from Claude.ai web interface."""
        
        try:
            await self._ensure_browser()
            await self._login()
            await self._start_new_conversation()
            
            # For now, we'll just use the last user message
            # In the future, we could implement conversation context
            user_message = None
            for msg in reversed(messages):
                if msg.role == "user":
                    user_message = msg.content
                    break
                    
            if not user_message:
                raise LLMError("No user message found")
                
            # Send the message
            await self._send_message(user_message)
            
            # Wait for and get the response
            response = await self._wait_for_response()
            
            # For now, yield the complete response as a single chunk
            # In the future, we could implement real streaming by monitoring the DOM
            yield StreamChunk(delta_content=response, finish_reason="stop")
            
        except LLMError:
            raise
        except PlaywrightError as e:
            logger.error(f"Claude web automation error: {e}")
            raise LLMError(f"Claude web automation failed: {e}")

    async def list_models(self) -> list[str]:
        """Return available model names."""
        # Claude.ai web interface doesn't expose model selection in the same way
        # Return the models we know are available
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022", 
            "claude-3-opus-20240229"
        ]

    async def close(self) -> None:
        """Clean up browser resources."""
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
        except PlaywrightError as e:
            logger.error(f"Error closing browser: {e}")
        finally:
            self._browser = None
            self._context = None
            self._page = None
            self._logged_in = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()