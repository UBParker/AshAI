"""Settings API — read/write app configuration and check external tools."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from fastapi import APIRouter

from helperai.config import get_settings
from helperai.desktop_main import get_app_data_dir

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _env_file_path() -> Path:
    return get_app_data_dir() / ".env"


def _read_env_dict() -> dict[str, str]:
    """Read .env file into a dict (key=value lines)."""
    env_file = _env_file_path()
    result: dict[str, str] = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                result[key.strip()] = value.strip()
    return result


def _write_env_dict(data: dict[str, str]) -> None:
    """Write a dict as key=value lines to .env file."""
    env_file = _env_file_path()
    lines = [f"{k}={v}" for k, v in sorted(data.items())]
    env_file.write_text("\n".join(lines) + "\n")


@router.get("")
async def get_settings_endpoint():
    """Return current config with sensitive keys masked."""
    settings = get_settings()
    env_data = _read_env_dict()

    return {
        "default_provider": settings.default_provider,
        "default_model": settings.default_model,
        "has_anthropic_key": bool(settings.anthropic_api_key),
        "has_openai_key": bool(settings.openai_api_key),
        "has_gemini_key": bool(settings.gemini_api_key),
        "ollama_base_url": settings.ollama_base_url,
        "eve_name": settings.eve_name,
        "has_any_key": bool(
            settings.anthropic_api_key
            or settings.openai_api_key
            or settings.gemini_api_key
        ),
        "env_file": str(_env_file_path()),
    }


@router.put("")
async def put_settings_endpoint(payload: dict):
    """Write key/value pairs to .env in app data dir, update running env."""
    env_data = _read_env_dict()

    for key, value in payload.items():
        env_key = key.upper()
        if not env_key.startswith("HELPERAI_"):
            env_key = f"HELPERAI_{env_key}"
        env_data[env_key] = str(value)
        os.environ[env_key] = str(value)

    _write_env_dict(env_data)

    return {"status": "ok", "message": "Settings saved. Restart for full effect."}


@router.get("/claude-cli")
async def claude_cli_check():
    """Check if the Claude CLI is available on PATH."""
    path = shutil.which("claude")
    return {
        "available": path is not None,
        "path": path,
        "install_url": "https://docs.anthropic.com/en/docs/claude-code/overview",
    }
