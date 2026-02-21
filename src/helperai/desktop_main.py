"""Desktop entry point for AshAI — used by Tauri sidecar / PyInstaller binary."""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path


def find_free_port() -> int:
    """Bind to port 0 and let the OS assign a free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get_app_data_dir() -> Path:
    """Return the platform-specific app data directory."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

    app_dir = base / "com.ashai.app"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def main() -> None:
    import uvicorn

    # Allow gateway to override data dir for per-user instances
    data_dir_override = os.environ.get("HELPERAI_DATA_DIR")
    if data_dir_override:
        app_data = Path(data_dir_override)
        app_data.mkdir(parents=True, exist_ok=True)
    else:
        app_data = get_app_data_dir()

    # Use port from env (set by gateway) or find a free one
    port_env = os.environ.get("HELPERAI_PORT")
    port = int(port_env) if port_env else find_free_port()

    # Set env vars before importing anything that reads config
    os.environ.setdefault("HELPERAI_DATABASE_URL", f"sqlite+aiosqlite:///{app_data / 'ashai.db'}")
    os.environ.setdefault("HELPERAI_PLUGINS_DIR", str(app_data / "plugins"))
    os.environ["HELPERAI_PORT"] = str(port)

    # Load .env from app data dir if it exists
    env_file = app_data / ".env"
    if env_file.exists():
        from dotenv import load_dotenv

        load_dotenv(env_file, override=False)

    # Ensure plugins dir exists
    plugins_dir = app_data / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)

    # Print port for Tauri to read — must be the first stdout line
    print(f"PORT:{port}", flush=True)

    uvicorn.run(
        "helperai.api.app:create_app",
        factory=True,
        host="127.0.0.1",
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
