"""Gateway service — routes users to per-user AshAI backend instances.

Validates Supabase JWTs, spawns/stops backend processes, reaps idle instances.
Supports both personal instances (per-user) and project instances (shared).
Run: python -m helperai.gateway
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# --- Configuration ---

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
GATEWAY_PORT = int(os.environ.get("GATEWAY_PORT", "9000"))
DATA_ROOT = Path(os.environ.get("GATEWAY_DATA_DIR", "./data"))
PORT_RANGE_START = 10001
PORT_RANGE_END = 10100
PERSONAL_IDLE_TIMEOUT = 30 * 60  # 30 minutes
PROJECT_IDLE_TIMEOUT = 15 * 60  # 15 minutes with no connected users
REAP_INTERVAL = 5 * 60  # check every 5 minutes

# --- Instance tracking ---


class Instance:
    def __init__(self, instance_id: str, port: int, process: subprocess.Popen, instance_type: str):
        self.instance_id = instance_id
        self.port = port
        self.process = process
        self.instance_type = instance_type  # "personal" or "project"
        self.last_active = time.time()
        self.connected_users: set[str] = set()


personal_instances: dict[str, Instance] = {}  # keyed by user_id
project_instances: dict[str, Instance] = {}  # keyed by project_id
_used_ports: set[int] = set()


def _find_free_port() -> int:
    for port in range(PORT_RANGE_START, PORT_RANGE_END + 1):
        if port not in _used_ports:
            return port
    raise RuntimeError("No free ports available")


def _is_alive(inst: Instance) -> bool:
    return inst.process.poll() is None


def spawn_instance(instance_id: str, instance_type: str = "personal") -> Instance:
    """Spawn a new AshAI backend instance."""
    port = _find_free_port()

    if instance_type == "project":
        data_dir = DATA_ROOT / "projects" / instance_id
    else:
        data_dir = DATA_ROOT / "users" / instance_id

    data_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["HELPERAI_DATA_DIR"] = str(data_dir)
    env["HELPERAI_PORT"] = str(port)
    env["HELPERAI_INSTANCE_TYPE"] = instance_type
    if instance_type == "project":
        env["HELPERAI_PROJECT_ID"] = instance_id

    process = subprocess.Popen(
        [sys.executable, "-m", "helperai.desktop_main"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    _used_ports.add(port)
    inst = Instance(instance_id=instance_id, port=port, process=process, instance_type=instance_type)

    logger.info(
        "Spawned %s instance %s on port %d (pid %d)",
        instance_type, instance_id, port, process.pid,
    )
    return inst


def _stop_process(inst: Instance) -> None:
    """Stop an instance's process and free its port."""
    _used_ports.discard(inst.port)
    try:
        inst.process.send_signal(signal.SIGTERM)
        inst.process.wait(timeout=5)
    except Exception:
        inst.process.kill()
    logger.info("Stopped %s instance %s (port %d)", inst.instance_type, inst.instance_id, inst.port)


def stop_personal_instance(user_id: str) -> None:
    inst = personal_instances.pop(user_id, None)
    if inst is None:
        return
    _stop_process(inst)


def stop_project_instance(project_id: str) -> None:
    inst = project_instances.pop(project_id, None)
    if inst is None:
        return
    _stop_process(inst)


async def _wait_for_healthy(inst: Instance, timeout_secs: int = 30) -> None:
    """Poll instance health endpoint until ready."""
    import httpx

    for _ in range(timeout_secs):
        await asyncio.sleep(1)
        if not _is_alive(inst):
            raise HTTPException(status_code=500, detail="Instance failed to start")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"http://127.0.0.1:{inst.port}/api/health", timeout=2
                )
                if resp.status_code == 200:
                    return
        except Exception:
            pass
    raise HTTPException(status_code=500, detail="Instance did not become healthy in time")


# --- Supabase auth ---

_supabase_client = None


def _get_supabase():
    global _supabase_client
    if _supabase_client is None:
        from supabase import create_client

        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _supabase_client


def validate_jwt(token: str) -> dict:
    """Validate a Supabase JWT and return the user object."""
    sb = _get_supabase()
    try:
        user_response = sb.auth.get_user(token)
        return {"id": user_response.user.id, "email": user_response.user.email}
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from e


# --- FastAPI app ---

app = FastAPI(title="AshAI Gateway", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:8000",
        "https://app.ashai.net",
        "https://ashai.net",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SessionResponse(BaseModel):
    backend_url: str
    status: str


def _extract_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    raise HTTPException(status_code=401, detail="Missing Authorization header")


@app.post("/gateway/session", response_model=SessionResponse)
async def create_session(request: Request):
    """Validate JWT, ensure user has a running personal instance, return its URL."""
    token = _extract_token(request)
    user = validate_jwt(token)
    user_id = str(user["id"])

    # Check for existing instance
    inst = personal_instances.get(user_id)
    if inst and _is_alive(inst):
        inst.last_active = time.time()
        return SessionResponse(
            backend_url=f"http://127.0.0.1:{inst.port}",
            status="running",
        )

    # Clean up dead instance if needed
    if inst:
        stop_personal_instance(user_id)

    # Spawn new personal instance
    inst = spawn_instance(user_id, instance_type="personal")
    personal_instances[user_id] = inst

    await _wait_for_healthy(inst)
    return SessionResponse(
        backend_url=f"http://127.0.0.1:{inst.port}",
        status="started",
    )


@app.post("/gateway/project-session", response_model=SessionResponse)
async def create_project_session(request: Request):
    """Validate JWT + project membership, return shared project instance URL."""
    token = _extract_token(request)
    user = validate_jwt(token)
    body = await request.json()
    project_id = body.get("project_id")

    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")

    # Verify membership via Supabase
    sb = _get_supabase()
    result = sb.table("project_members") \
        .select("role") \
        .eq("project_id", project_id) \
        .eq("user_id", str(user["id"])) \
        .execute()

    if not result.data:
        raise HTTPException(status_code=403, detail="Not a member of this project")

    # Get or spawn project instance
    inst = project_instances.get(project_id)
    if inst and _is_alive(inst):
        inst.last_active = time.time()
        inst.connected_users.add(str(user["id"]))
        return SessionResponse(
            backend_url=f"http://127.0.0.1:{inst.port}",
            status="running",
        )

    # Clean up dead instance if needed
    if inst:
        stop_project_instance(project_id)

    # Spawn new project instance
    inst = spawn_instance(project_id, instance_type="project")
    project_instances[project_id] = inst
    inst.connected_users.add(str(user["id"]))

    await _wait_for_healthy(inst)
    return SessionResponse(
        backend_url=f"http://127.0.0.1:{inst.port}",
        status="started",
    )


@app.post("/gateway/leave-project")
async def leave_project(request: Request):
    """Remove user from a project instance's connected users."""
    token = _extract_token(request)
    user = validate_jwt(token)
    body = await request.json()
    project_id = body.get("project_id")

    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")

    inst = project_instances.get(project_id)
    if inst:
        inst.connected_users.discard(str(user["id"]))
    return {"status": "left"}


@app.post("/gateway/logout")
async def logout(request: Request):
    """Stop the user's personal backend instance."""
    token = _extract_token(request)
    user = validate_jwt(token)
    user_id = str(user["id"])

    stop_personal_instance(user_id)
    return {"status": "stopped"}


@app.get("/gateway/health")
async def gateway_health():
    return {
        "status": "ok",
        "personal_instances": len(personal_instances),
        "project_instances": len(project_instances),
        "used_ports": len(_used_ports),
    }


# --- Idle reaper ---


async def _reap_idle():
    """Background task that stops idle instances."""
    while True:
        await asyncio.sleep(REAP_INTERVAL)
        now = time.time()

        # Reap idle personal instances
        idle_personal = [
            uid
            for uid, inst in personal_instances.items()
            if (now - inst.last_active) > PERSONAL_IDLE_TIMEOUT or not _is_alive(inst)
        ]
        for uid in idle_personal:
            logger.info("Reaping idle personal instance for user %s", uid)
            stop_personal_instance(uid)

        # Reap project instances with no connected users and idle
        idle_projects = [
            pid
            for pid, inst in project_instances.items()
            if (
                (len(inst.connected_users) == 0 and (now - inst.last_active) > PROJECT_IDLE_TIMEOUT)
                or not _is_alive(inst)
            )
        ]
        for pid in idle_projects:
            logger.info("Reaping idle project instance %s", pid)
            stop_project_instance(pid)


@app.on_event("startup")
async def _start_reaper():
    asyncio.create_task(_reap_idle())


@app.on_event("shutdown")
async def _shutdown_instances():
    for uid in list(personal_instances):
        stop_personal_instance(uid)
    for pid in list(project_instances):
        stop_project_instance(pid)


# --- Entrypoint ---

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(
        "helperai.gateway:app",
        host="0.0.0.0",
        port=GATEWAY_PORT,
        log_level="info",
    )
