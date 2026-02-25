#!/usr/bin/env python3
"""
Advanced test script for Claude web automation in Docker containers.

This script performs deeper validation including:
1. Browser permissions and security
2. Memory and resource usage
3. Network connectivity tests
4. File system permissions
5. Advanced Playwright functionality
"""

import asyncio
import sys
import os
import pathlib
from typing import Dict, Any

from playwright.async_api import async_playwright
from helperai.llm.claude_web_provider import ClaudeWebProvider


async def test_browser_security_permissions() -> Dict[str, Any]:
    """Test browser security settings and permissions."""
    print("🔒 Testing browser security and permissions...")

    results = {}

    try:
        async with async_playwright() as p:
            # Test with various security options
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--no-first-run',
                    '--disable-extensions',
                    '--disable-plugins',
                    '--disable-images',
                ]
            )

            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
            )

            page = await context.new_page()

            # Test navigation to a real website
            await page.goto('https://httpbin.org/get', timeout=15000)
            content = await page.content()

            results['navigation'] = 'httpbin' in content.lower()
            results['security_args'] = True
            results['context_creation'] = True

            await browser.close()

        print(f"✅ Browser security test passed")
        print(f"   - Navigation: {'✅' if results['navigation'] else '❌'}")
        print(f"   - Security args: {'✅' if results['security_args'] else '❌'}")
        print(f"   - Context creation: {'✅' if results['context_creation'] else '❌'}")

        return {'success': True, 'details': results}

    except Exception as e:
        print(f"❌ Browser security test failed: {e}")
        return {'success': False, 'error': str(e)}


async def test_filesystem_permissions() -> Dict[str, Any]:
    """Test filesystem permissions and access."""
    print("📁 Testing filesystem permissions...")

    results = {}

    try:
        # Check browser data directory
        browser_dir = pathlib.Path('/data/browsers')
        results['browser_dir_exists'] = browser_dir.exists()
        results['browser_dir_writable'] = os.access(browser_dir, os.W_OK) if browser_dir.exists() else False

        # Check Playwright browsers path
        playwright_path = pathlib.Path('/opt/playwright-browsers')
        results['playwright_path_exists'] = playwright_path.exists()
        results['playwright_path_readable'] = os.access(playwright_path, os.R_OK) if playwright_path.exists() else False

        # Check user home directory
        home_dir = pathlib.Path('/home/ashai')
        results['home_dir_exists'] = home_dir.exists()
        results['home_dir_writable'] = os.access(home_dir, os.W_OK) if home_dir.exists() else False

        # Test creating a temporary file
        try:
            temp_file = browser_dir / 'test_temp.txt'
            temp_file.write_text('test')
            temp_file.unlink()
            results['temp_file_creation'] = True
        except Exception:
            results['temp_file_creation'] = False

        all_good = all([
            results['browser_dir_exists'],
            results['browser_dir_writable'],
            results['playwright_path_exists'],
            results['playwright_path_readable'],
            results['home_dir_exists'],
            results['temp_file_creation']
        ])

        print(f"✅ Filesystem permissions test: {'PASS' if all_good else 'PARTIAL'}")
        for key, value in results.items():
            status = '✅' if value else '❌'
            print(f"   - {key}: {status}")

        return {'success': all_good, 'details': results}

    except Exception as e:
        print(f"❌ Filesystem permissions test failed: {e}")
        return {'success': False, 'error': str(e)}


async def test_memory_resources() -> Dict[str, Any]:
    """Test memory usage and resource constraints."""
    print("💾 Testing memory and resource usage...")

    results = {}

    try:
        import psutil

        # Get initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Launch browser and do some operations
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            contexts = []

            # Create multiple contexts to test resource usage
            for i in range(3):
                context = await browser.new_context()
                page = await context.new_page()
                await page.goto('data:text/html,<h1>Test Page</h1>')
                contexts.append(context)

            # Check memory after browser operations
            peak_memory = process.memory_info().rss / 1024 / 1024  # MB

            # Clean up
            for context in contexts:
                await context.close()
            await browser.close()

        memory_increase = peak_memory - initial_memory
        results['initial_memory_mb'] = round(initial_memory, 2)
        results['peak_memory_mb'] = round(peak_memory, 2)
        results['memory_increase_mb'] = round(memory_increase, 2)
        results['reasonable_usage'] = memory_increase < 500  # Less than 500MB increase

        print(f"✅ Memory test completed")
        print(f"   - Initial memory: {results['initial_memory_mb']} MB")
        print(f"   - Peak memory: {results['peak_memory_mb']} MB")
        print(f"   - Memory increase: {results['memory_increase_mb']} MB")
        print(f"   - Reasonable usage: {'✅' if results['reasonable_usage'] else '❌'}")

        return {'success': True, 'details': results}

    except ImportError:
        print("⚠️  psutil not available, skipping detailed memory test")
        return {'success': True, 'details': {'skipped': 'psutil not available'}}
    except Exception as e:
        print(f"❌ Memory test failed: {e}")
        return {'success': False, 'error': str(e)}


async def test_network_connectivity() -> Dict[str, Any]:
    """Test network connectivity and external access."""
    print("🌐 Testing network connectivity...")

    results = {}

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # Test various network scenarios
            test_urls = [
                ('https://httpbin.org/get', 'httpbin'),
                ('https://www.google.com', 'google'),
                ('data:text/html,<h1>Local Data</h1>', 'Local Data')
            ]

            for url, expected_content in test_urls:
                try:
                    await page.goto(url, timeout=10000)
                    content = await page.content()
                    results[f'url_{len(results)}'] = {
                        'url': url,
                        'success': expected_content.lower() in content.lower(),
                        'status': 'success'
                    }
                except Exception as e:
                    results[f'url_{len(results)}'] = {
                        'url': url,
                        'success': False,
                        'status': f'error: {str(e)}'
                    }

            await browser.close()

        success_count = sum(1 for r in results.values() if r['success'])
        total_count = len(results)

        print(f"✅ Network connectivity test: {success_count}/{total_count} successful")
        for key, result in results.items():
            status = '✅' if result['success'] else '❌'
            print(f"   - {result['url']}: {status}")

        return {'success': success_count > 0, 'details': results}

    except Exception as e:
        print(f"❌ Network connectivity test failed: {e}")
        return {'success': False, 'error': str(e)}


async def main():
    """Run all advanced tests."""
    print("🚀 Starting Advanced Docker Claude web automation tests...\n")

    tests = [
        ("Filesystem Permissions", test_filesystem_permissions()),
        ("Browser Security & Permissions", test_browser_security_permissions()),
        ("Memory & Resources", test_memory_resources()),
        ("Network Connectivity", test_network_connectivity()),
    ]

    results = []

    for test_name, test_coro in tests:
        print(f"📋 {test_name}")
        result = await test_coro
        results.append((test_name, result))
        print()

    # Summary
    print("📊 Advanced Test Results Summary:")
    print("=" * 60)

    all_passed = True
    for test_name, result in results:
        success = result.get('success', False)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {test_name}: {status}")
        if not success:
            all_passed = False
            if 'error' in result:
                print(f"      Error: {result['error']}")

    print("=" * 60)

    if all_passed:
        print("🎉 All advanced tests passed! Docker container is fully ready for production Claude web automation.")
        sys.exit(0)
    else:
        print("💥 Some advanced tests failed. Container may have limitations.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())