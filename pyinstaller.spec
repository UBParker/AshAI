# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for AshAI sidecar binary."""

import os
from pathlib import Path

block_cipher = None

# Collect plugins directory as data
plugins_dir = Path("plugins")
plugins_data = []
if plugins_dir.exists():
    for f in plugins_dir.rglob("*"):
        if f.is_file():
            plugins_data.append((str(f), str(f.parent)))

a = Analysis(
    ["src/helperai/desktop_main.py"],
    pathex=["src"],
    binaries=[],
    datas=plugins_data,
    hiddenimports=[
        "helperai",
        "helperai.api.app",
        "helperai.api.routes.chat",
        "helperai.api.routes.agents",
        "helperai.api.routes.providers",
        "helperai.api.routes.ws",
        "helperai.api.routes.approvals",
        "helperai.api.routes.tools",
        "helperai.api.routes.settings",
        "helperai.config",
        "helperai.db.engine",
        "helperai.db.models",
        "helperai.llm.registry",
        "helperai.llm.openai_compat",
        "helperai.llm.anthropic_provider",
        "helperai.agents.manager",
        "helperai.agents.agent",
        "helperai.agents.eve",
        "helperai.tools.registry",
        "helperai.plugins.loader",
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "fastapi",
        "starlette",
        "pydantic",
        "pydantic_settings",
        "sqlalchemy",
        "sqlalchemy.ext.asyncio",
        "aiosqlite",
        "anthropic",
        "httpx",
        "sse_starlette",
        "dotenv",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ashai-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
