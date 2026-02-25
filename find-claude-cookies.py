#!/usr/bin/env python3
"""
Find which Chrome profile has Claude.ai cookies
"""

import json
import sqlite3
import os
from pathlib import Path
import tempfile
import shutil

def check_profile_for_claude_cookies(profile_path):
    """Check if a Chrome profile has Claude.ai cookies"""
    cookie_path = profile_path / "Cookies"

    if not cookie_path.exists():
        return 0

    # Copy the database to temp location (Chrome locks it)
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        shutil.copy2(cookie_path, tmp.name)
        tmp_path = tmp.name

    try:
        # Connect to the database
        conn = sqlite3.connect(tmp_path)
        cursor = conn.cursor()

        # Count cookies for claude.ai
        cursor.execute("""
            SELECT COUNT(*)
            FROM cookies
            WHERE host_key LIKE '%claude.ai%'
        """)

        count = cursor.fetchone()[0]
        conn.close()
        return count

    finally:
        # Clean up temp file
        os.unlink(tmp_path)

def find_chrome_profiles():
    """Find all Chrome profiles and check for Claude cookies"""
    chrome_dir = Path.home() / "Library/Application Support/Google/Chrome"

    if not chrome_dir.exists():
        print("Chrome directory not found")
        return

    profiles = []

    # Check Default profile
    default_path = chrome_dir / "Default"
    if default_path.exists():
        count = check_profile_for_claude_cookies(default_path)
        if count > 0:
            profiles.append(("Default", default_path, count))

    # Check numbered profiles (Profile 1, Profile 2, etc.)
    for i in range(1, 20):  # Check up to Profile 19
        profile_path = chrome_dir / f"Profile {i}"
        if profile_path.exists():
            count = check_profile_for_claude_cookies(profile_path)
            if count > 0:
                profiles.append((f"Profile {i}", profile_path, count))

    return profiles

def main():
    print("Searching for Chrome profiles with Claude.ai cookies...\n")

    profiles = find_chrome_profiles()

    if not profiles:
        print("No Chrome profiles found with Claude.ai cookies.")
        print("Please log in to claude.ai in Chrome first.")
        return

    print("Found Claude.ai cookies in the following profiles:")
    for name, path, count in profiles:
        print(f"  {name}: {count} cookies - Path: {path}")

    # Use the profile with the most cookies
    best_profile = max(profiles, key=lambda x: x[2])
    print(f"\nBest profile: {best_profile[0]} with {best_profile[2]} cookies")
    print(f"Profile path: {best_profile[1]}")

    # Export cookies from the best profile
    print(f"\nExporting cookies from {best_profile[0]}...")

    cookie_db_path = best_profile[1] / "Cookies"

    # Copy the database to temp location
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        shutil.copy2(cookie_db_path, tmp.name)
        tmp_path = tmp.name

    try:
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

        # Save cookies
        storage_state = {
            "cookies": cookies,
            "origins": []
        }

        output_file = "claude-cookies.json"
        with open(output_file, 'w') as f:
            json.dump(storage_state, f, indent=2)

        print(f"Exported {len(cookies)} cookies to {output_file}")

    finally:
        os.unlink(tmp_path)

if __name__ == "__main__":
    main()