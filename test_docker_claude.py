#!/usr/bin/env python3
"""
Test script for Claude web automation in Docker containers.

This script validates that:
1. Playwright is properly installed and configured
2. Chromium browser can launch in headless mode
3. Claude web provider can be instantiated
4. All dependencies are working correctly

Usage:
    # Test locally
    python test_docker_claude.py

    # Test in Docker container
    docker run --rm ashai-playwright:test python test_docker_claude.py
"""

import asyncio
import sys
from typing import List

from playwright.async_api import async_playwright
from helperai.llm.claude_web_provider import ClaudeWebProvider


async def test_playwright_installation() -> bool:
    """Test that Playwright is properly installed and can launch browsers."""
    print("🧪 Testing Playwright installation...")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # Navigate to a simple data URL
            await page.goto('data:text/html,<h1>Playwright Test</h1>')
            title = await page.title()
            content = await page.content()

            await browser.close()

            print(f"✅ Browser launched successfully")
            print(f"   - Title: '{title}'")
            print(f"   - Content loaded: {'Playwright Test' in content}")
            return True

    except Exception as e:
        print(f"❌ Playwright test failed: {e}")
        return False


async def test_claude_web_provider() -> bool:
    """Test that Claude web provider can be instantiated."""
    print("🧪 Testing Claude web provider...")

    try:
        provider = ClaudeWebProvider(
            email="test@example.com",
            password="dummy_password",
            headless=True,
            timeout=10000
        )

        models = await provider.list_models()

        print(f"✅ Claude web provider created successfully")
        print(f"   - Provider name: {provider.name}")
        print(f"   - Available models: {', '.join(models)}")
        return True

    except Exception as e:
        print(f"❌ Claude web provider test failed: {e}")
        return False


async def test_browser_environment() -> bool:
    """Test browser environment variables and configuration."""
    print("🧪 Testing browser environment...")

    import os

    try:
        playwright_path = os.getenv('PLAYWRIGHT_BROWSERS_PATH', '/opt/playwright-browsers')
        headless = os.getenv('HELPERAI_CLAUDE_WEB_HEADLESS', 'true')
        timeout = os.getenv('HELPERAI_CLAUDE_WEB_TIMEOUT', '30000')

        print(f"✅ Environment configuration:")
        print(f"   - Browser path: {playwright_path}")
        print(f"   - Headless mode: {headless}")
        print(f"   - Default timeout: {timeout}ms")

        # Check if browser path exists
        import pathlib
        if pathlib.Path(playwright_path).exists():
            print(f"   - Browser path exists: ✅")
        else:
            print(f"   - Browser path missing: ❌")
            return False

        return True

    except Exception as e:
        print(f"❌ Environment test failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("🚀 Starting Docker Claude web automation tests...\n")

    tests = [
        ("Browser Environment", test_browser_environment()),
        ("Playwright Installation", test_playwright_installation()),
        ("Claude Web Provider", test_claude_web_provider()),
    ]

    results = []

    for test_name, test_coro in tests:
        print(f"📋 {test_name}")
        result = await test_coro
        results.append((test_name, result))
        print()

    # Summary
    print("📊 Test Results Summary:")
    print("=" * 50)

    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {test_name}: {status}")
        if not passed:
            all_passed = False

    print("=" * 50)

    if all_passed:
        print("🎉 All tests passed! Docker container is ready for Claude web automation.")
        sys.exit(0)
    else:
        print("💥 Some tests failed. Please check the configuration.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())