#!/usr/bin/env python3
"""
Automated Claude Code CLI authentication using Playwright
Handles the auth flow programmatically without terminal blocking
"""

import asyncio
import subprocess
import time
import logging
from playwright.async_api import async_playwright
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ClaudeAuthAutomation:
    def __init__(self):
        self.auth_code = None
        self.auth_process = None

    async def start_auth_process(self):
        """Start claude auth in subprocess and capture output"""
        logger.info("Starting claude auth process...")

        # Start claude auth in a subprocess with stdin/stdout pipes
        self.auth_process = subprocess.Popen(
            ['claude', 'auth'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Give it a moment to start
        await asyncio.sleep(2)

        # Read the initial output to get the auth URL
        output = []
        while True:
            line = self.auth_process.stdout.readline()
            if not line:
                break
            output.append(line)
            logger.info(f"Auth output: {line.strip()}")
            if 'https://claude.ai/auth/callback' in line or 'Enter the code' in line:
                break

        return ''.join(output)

    async def extract_auth_code_from_browser(self):
        """Use Playwright to extract the auth code from Firefox"""
        logger.info("Launching Playwright to extract auth code...")

        async with async_playwright() as p:
            # Connect to existing Firefox instance with remote debugging
            browser = await p.firefox.connect_over_cdp("http://localhost:9222")

            # Get all pages
            pages = await browser.contexts[0].pages()

            # Find the Claude auth page
            auth_page = None
            for page in pages:
                url = page.url
                if 'claude.ai/auth/callback' in url:
                    auth_page = page
                    break

            if not auth_page:
                logger.error("Could not find Claude auth page")
                return None

            logger.info(f"Found auth page: {auth_page.url}")

            # Wait for the auth code to appear on the page
            await auth_page.wait_for_selector('text=Copy code', timeout=30000)

            # Extract the auth code - it's usually in a code element or pre tag
            auth_code = await auth_page.evaluate('''() => {
                // Try various selectors to find the auth code
                let code = document.querySelector('code')?.textContent;
                if (!code) {
                    // Look for any element containing the pattern of an auth code
                    const elements = document.querySelectorAll('*');
                    for (const el of elements) {
                        const text = el.textContent;
                        // Auth codes are typically long alphanumeric strings
                        if (text && /^[A-Za-z0-9]{20,}$/.test(text.trim())) {
                            code = text.trim();
                            break;
                        }
                    }
                }
                return code;
            }''')

            if auth_code:
                logger.info(f"Extracted auth code: {auth_code[:10]}...")
                self.auth_code = auth_code
            else:
                logger.error("Could not extract auth code")

            await browser.close()
            return auth_code

    async def complete_auth(self):
        """Send the auth code to the waiting claude auth process"""
        if not self.auth_code or not self.auth_process:
            logger.error("Missing auth code or process")
            return False

        logger.info("Sending auth code to claude auth process...")

        try:
            # Send the auth code to the process stdin
            self.auth_process.stdin.write(self.auth_code + '\n')
            self.auth_process.stdin.flush()

            # Wait for completion
            self.auth_process.wait(timeout=10)

            # Check if successful
            if self.auth_process.returncode == 0:
                logger.info("Authentication successful!")
                return True
            else:
                logger.error(f"Authentication failed with code: {self.auth_process.returncode}")
                return False

        except Exception as e:
            logger.error(f"Error completing auth: {e}")
            return False

    async def run_full_auth_flow(self):
        """Run the complete automated auth flow"""
        try:
            # Start the auth process
            output = await self.start_auth_process()
            logger.info(f"Auth process started, output: {output}")

            # Give user time to complete auth in browser
            logger.info("Please complete authentication in Firefox browser...")
            logger.info("Waiting for auth code to appear...")

            # Poll for auth code
            max_attempts = 30
            for i in range(max_attempts):
                await asyncio.sleep(2)
                auth_code = await self.extract_auth_code_from_browser()
                if auth_code:
                    break
                logger.info(f"Waiting for auth code... ({i+1}/{max_attempts})")

            if not auth_code:
                logger.error("Timeout waiting for auth code")
                return False

            # Complete the auth
            success = await self.complete_auth()
            return success

        except Exception as e:
            logger.error(f"Auth flow error: {e}")
            return False
        finally:
            if self.auth_process:
                self.auth_process.terminate()

async def main():
    automation = ClaudeAuthAutomation()
    success = await automation.run_full_auth_flow()

    if success:
        print("\n✅ Claude Code CLI authentication completed successfully!")
        print("You can now use 'claude' command in the terminal")
    else:
        print("\n❌ Authentication failed. Please try manual auth: claude auth")

if __name__ == "__main__":
    print("Claude Code CLI Authentication Automation")
    print("-" * 40)
    print("This will automate the auth code transfer process")
    print("Make sure Firefox is running with remote debugging enabled")
    print("")
    asyncio.run(main())