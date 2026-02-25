#!/usr/bin/env python3
"""
Setup script for Claude Web Automation

This script helps set up the Claude web automation provider by:
1. Installing required dependencies
2. Installing browser
3. Testing the setup
4. Configuring environment variables
"""

import os
import subprocess
import sys
from pathlib import Path


def run_command(command: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    print(f"Running: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    
    if check and result.returncode != 0:
        print(f"Error running command: {command}")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        sys.exit(1)
    
    return result


def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 11):
        print("Error: Python 3.11 or higher is required")
        sys.exit(1)
    print(f"✓ Python version: {sys.version}")


def install_dependencies():
    """Install required dependencies."""
    print("\\n=== Installing Dependencies ===")
    
    # Check if we're in a virtual environment
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )
    
    if not in_venv:
        print("Warning: Not in a virtual environment. Consider creating one:")
        print("  python -m venv .venv")
        print("  source .venv/bin/activate  # On Windows: .venv\\\\Scripts\\\\activate")
        print("")
    
    # Install playwright
    try:
        import playwright
        print("✓ Playwright already installed")
    except ImportError:
        print("Installing Playwright...")
        run_command(f"{sys.executable} -m pip install playwright>=1.48.0")
        print("✓ Playwright installed")


def install_browser():
    """Install Chromium browser for Playwright."""
    print("\\n=== Installing Browser ===")
    
    try:
        # Check if browser is already installed
        result = run_command("playwright install --dry-run chromium", check=False)
        if "is already installed" in result.stdout:
            print("✓ Chromium browser already installed")
        else:
            print("Installing Chromium browser...")
            run_command("playwright install chromium")
            print("✓ Chromium browser installed")
    except Exception as e:
        print(f"Error installing browser: {e}")
        print("Try running manually: playwright install chromium")


def setup_environment():
    """Help set up environment variables."""
    print("\\n=== Environment Setup ===")
    
    env_file = Path(".env")
    
    if env_file.exists():
        print("✓ .env file exists")
        
        # Check if Claude web vars are already set
        content = env_file.read_text()
        if "HELPERAI_CLAUDE_WEB_EMAIL" in content:
            print("✓ Claude web automation variables already configured")
            return
    else:
        print("Creating .env file from template...")
        env_example = Path(".env.example")
        if env_example.exists():
            content = env_example.read_text()
            env_file.write_text(content)
            print("✓ .env file created")
        else:
            print("Warning: .env.example not found")
    
    print("\\nTo complete setup, edit your .env file and add:")
    print("HELPERAI_CLAUDE_WEB_EMAIL=your-email@example.com")
    print("HELPERAI_CLAUDE_WEB_PASSWORD=your-password")
    print("HELPERAI_CLAUDE_WEB_HEADLESS=true")
    print("")
    print("Optional: Set Claude web as default provider:")
    print("HELPERAI_DEFAULT_PROVIDER=claude_web")


def test_setup():
    """Test the setup by importing the provider."""
    print("\\n=== Testing Setup ===")
    
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from helperai.llm.claude_web_provider import ClaudeWebProvider
        print("✓ Claude web provider can be imported")
        
        # Test browser availability
        import asyncio
        from playwright.async_api import async_playwright
        
        async def test_browser():
            playwright = await async_playwright().start()
            try:
                browser = await playwright.chromium.launch(headless=True)
                await browser.close()
                return True
            except Exception as e:
                print(f"Browser test failed: {e}")
                return False
            finally:
                await playwright.stop()
        
        if asyncio.run(test_browser()):
            print("✓ Browser test passed")
        else:
            print("✗ Browser test failed")
            
    except ImportError as e:
        print(f"✗ Import test failed: {e}")
        print("Make sure you're running from the AshAI root directory")
    except Exception as e:
        print(f"✗ Setup test failed: {e}")


def main():
    """Main setup function."""
    print("Claude Web Automation Setup")
    print("===========================")
    
    check_python_version()
    install_dependencies()
    install_browser()
    setup_environment()
    test_setup()
    
    print("\\n=== Setup Complete ===")
    print("Next steps:")
    print("1. Edit .env file with your Claude.ai credentials")
    print("2. Test with: python examples/claude_web_demo.py")
    print("3. Start AshAI: python -m helperai")
    print("")
    print("For more information, see docs/CLAUDE_WEB_AUTOMATION.md")


if __name__ == "__main__":
    main()