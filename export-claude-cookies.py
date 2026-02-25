#!/usr/bin/env python3
"""
Export cookies from Chrome/Safari for Claude.ai authentication
Run this on your Mac to get the cookies, then use them in the container
"""

import json
import sqlite3
import os
from pathlib import Path
import tempfile
import shutil

def get_chrome_cookies():
    """Extract Claude.ai cookies from Chrome"""
    # Chrome cookie database path
    chrome_cookie_path = Path.home() / "Library/Application Support/Google/Chrome/Default/Cookies"

    if not chrome_cookie_path.exists():
        print("Chrome cookie database not found")
        return None

    # Copy the database to temp location (Chrome locks it)
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        shutil.copy2(chrome_cookie_path, tmp.name)
        tmp_path = tmp.name

    try:
        # Connect to the database
        conn = sqlite3.connect(tmp_path)
        cursor = conn.cursor()

        # Get cookies for claude.ai
        cursor.execute("""
            SELECT name, value, host_key, path, expires_utc, is_secure, is_httponly, samesite
            FROM cookies
            WHERE host_key LIKE '%claude.ai%'
        """)

        cookies = []
        for row in cursor.fetchall():
            cookie = {
                "name": row[0],
                "value": row[1],
                "domain": row[2],
                "path": row[3],
                "expires": row[4],
                "httpOnly": bool(row[6]),
                "secure": bool(row[5]),
                "sameSite": "None" if row[7] == 0 else "Lax" if row[7] == 1 else "Strict"
            }
            cookies.append(cookie)

        conn.close()
        return cookies

    finally:
        # Clean up temp file
        os.unlink(tmp_path)

def export_playwright_format(cookies):
    """Convert cookies to Playwright storage state format"""
    if not cookies:
        return None

    # Playwright storage state format
    storage_state = {
        "cookies": cookies,
        "origins": []
    }

    return storage_state

def main():
    print("Extracting Claude.ai cookies from Chrome...")

    cookies = get_chrome_cookies()

    if not cookies:
        print("No Claude.ai cookies found. Please log in to claude.ai in Chrome first.")
        return

    print(f"Found {len(cookies)} cookies")

    # Convert to Playwright format
    storage_state = export_playwright_format(cookies)

    # Save to file
    output_file = "claude-cookies.json"
    with open(output_file, 'w') as f:
        json.dump(storage_state, f, indent=2)

    print(f"Cookies exported to {output_file}")
    print("\nTo use these cookies:")
    print("1. Copy claude-cookies.json to the Docker build directory")
    print("2. Build the VNC container: docker build -f Dockerfile.vnc-claude -t vnc-claude .")
    print("3. Run the container: docker run -p 5900:5900 -p 8080:8080 vnc-claude")
    print("4. Connect with VNC viewer to localhost:5900 (password: changeme)")
    print("5. Use the API at http://localhost:8080/api/chat")

if __name__ == "__main__":
    main()