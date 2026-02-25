"""Configuration for Claude web automation provider."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ClaudeWebConfig:
    """Configuration for Claude.ai web automation."""
    
    email: str
    password: str
    headless: bool = True
    timeout: int = 30000  # 30 seconds
    browser_args: list[str] = None
    
    def __post_init__(self):
        if self.browser_args is None:
            self.browser_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security", 
                "--disable-features=VizDisplayCompositor",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-dev-shm-usage",
                "--disable-gpu"
            ]

    @classmethod
    def from_env(cls) -> ClaudeWebConfig:
        """Create config from environment variables."""
        email = os.getenv("CLAUDE_WEB_EMAIL")
        password = os.getenv("CLAUDE_WEB_PASSWORD")
        
        if not email or not password:
            raise ValueError(
                "CLAUDE_WEB_EMAIL and CLAUDE_WEB_PASSWORD environment variables are required"
            )
        
        return cls(
            email=email,
            password=password,
            headless=os.getenv("CLAUDE_WEB_HEADLESS", "true").lower() == "true",
            timeout=int(os.getenv("CLAUDE_WEB_TIMEOUT", "30000")),
        )