"""Application configuration via environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "HELPERAI_", "env_file": ".env", "extra": "ignore"}

    # Server
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "info"

    # Database
    database_url: str = "sqlite+aiosqlite:///./helperai.db"

    # Default LLM provider name (must match a provider_configs entry or builtin name)
    default_provider: str = "ollama"
    default_model: str = "llama3.2"

    # Builtin provider URLs / keys (used to auto-seed provider_configs on first run)
    ollama_base_url: str = "http://localhost:11434"
    openai_api_key: SecretStr = SecretStr("")
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: SecretStr = SecretStr("")
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    gemini_api_key: SecretStr = SecretStr("")
    
    # Claude Code Desktop (uses subscription, NO API COSTS!)
    claude_code_enabled: bool = True
    claude_code_headless: bool = True
    claude_code_container_url: str = "http://claude-agent:8000"

    # Claude Web Automation (legacy, prefer Claude Code)
    claude_web_email: str = ""
    claude_web_password: SecretStr = SecretStr("")
    claude_web_headless: bool = True
    claude_web_timeout: int = 30000

    # Eve
    eve_name: str = "Ash"
    eve_model: str = ""  # empty → use default_model

    # Plugins directory
    plugins_dir: str = Field(default_factory=lambda: str(Path("plugins")))

    # CORS
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:8000",
        "tauri://localhost",
        "https://tauri.localhost",
        "https://app.ashai.net",
        "https://ashai.net",
    ]


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings