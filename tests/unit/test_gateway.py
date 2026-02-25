"""Tests for gateway module — instance management and helpers."""

from __future__ import annotations

import signal
import subprocess
import sys
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

# Mock uvicorn before importing gateway (it may not be installed in test env)
if "uvicorn" not in sys.modules:
    sys.modules["uvicorn"] = MagicMock()

from helperai import gateway
from helperai.gateway import (
    Instance,
    _find_free_port,
    _is_alive,
    _stop_process,
    _extract_token,
    _get_instance_for_user,
    spawn_instance,
    stop_personal_instance,
    stop_project_instance,
    personal_instances,
    project_instances,
    _used_ports,
    PORT_RANGE_START,
    PORT_RANGE_END,
)


# -- fixtures -----------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_state():
    """Reset module-level state between tests."""
    personal_instances.clear()
    project_instances.clear()
    _used_ports.clear()
    yield
    personal_instances.clear()
    project_instances.clear()
    _used_ports.clear()


def _make_instance(instance_id="user-1", port=10001, alive=True, instance_type="personal"):
    proc = MagicMock(spec=subprocess.Popen)
    proc.poll.return_value = None if alive else 1
    proc.pid = 12345
    inst = Instance(instance_id=instance_id, port=port, process=proc, instance_type=instance_type)
    return inst


# -- _find_free_port ----------------------------------------------------------


class TestFindFreePort:
    def test_first_port(self):
        port = _find_free_port()
        assert port == PORT_RANGE_START

    def test_skips_used_ports(self):
        _used_ports.add(PORT_RANGE_START)
        _used_ports.add(PORT_RANGE_START + 1)
        port = _find_free_port()
        assert port == PORT_RANGE_START + 2

    def test_all_ports_used_raises(self):
        for p in range(PORT_RANGE_START, PORT_RANGE_END + 1):
            _used_ports.add(p)
        with pytest.raises(RuntimeError, match="No free ports"):
            _find_free_port()


# -- _is_alive ----------------------------------------------------------------


class TestIsAlive:
    def test_alive(self):
        inst = _make_instance(alive=True)
        assert _is_alive(inst) is True

    def test_dead(self):
        inst = _make_instance(alive=False)
        assert _is_alive(inst) is False


# -- _stop_process ------------------------------------------------------------


class TestStopProcess:
    def test_graceful_stop(self):
        inst = _make_instance(port=10005)
        _used_ports.add(10005)

        _stop_process(inst)

        inst.process.send_signal.assert_called_once_with(signal.SIGTERM)
        inst.process.wait.assert_called_once_with(timeout=5)
        assert 10005 not in _used_ports

    def test_force_kill_on_failure(self):
        inst = _make_instance(port=10006)
        _used_ports.add(10006)
        inst.process.wait.side_effect = subprocess.TimeoutExpired("cmd", 5)

        _stop_process(inst)

        inst.process.kill.assert_called_once()
        assert 10006 not in _used_ports


# -- _extract_token -----------------------------------------------------------


class TestExtractToken:
    def test_valid_bearer(self):
        request = MagicMock()
        request.headers = {"Authorization": "Bearer my-token-123"}
        assert _extract_token(request) == "my-token-123"

    def test_missing_header(self):
        request = MagicMock()
        request.headers = {}
        with pytest.raises(HTTPException) as exc_info:
            _extract_token(request)
        assert exc_info.value.status_code == 401

    def test_no_bearer_prefix(self):
        request = MagicMock()
        request.headers = {"Authorization": "Basic abc"}
        with pytest.raises(HTTPException) as exc_info:
            _extract_token(request)
        assert exc_info.value.status_code == 401


# -- _get_instance_for_user ---------------------------------------------------


class TestGetInstanceForUser:
    def test_returns_personal_instance(self):
        inst = _make_instance()
        personal_instances["user-1"] = inst
        result = _get_instance_for_user("user-1")
        assert result is inst

    def test_returns_project_instance(self):
        inst = _make_instance(instance_type="project")
        project_instances["proj-1"] = inst
        result = _get_instance_for_user("user-1", project_id="proj-1")
        assert result is inst

    def test_no_instance_raises_503(self):
        with pytest.raises(HTTPException) as exc_info:
            _get_instance_for_user("user-1")
        assert exc_info.value.status_code == 503

    def test_dead_instance_raises_503(self):
        inst = _make_instance(alive=False)
        personal_instances["user-1"] = inst
        with pytest.raises(HTTPException) as exc_info:
            _get_instance_for_user("user-1")
        assert exc_info.value.status_code == 503

    def test_updates_last_active(self):
        inst = _make_instance()
        inst.last_active = 0
        personal_instances["user-1"] = inst
        _get_instance_for_user("user-1")
        assert inst.last_active > 0


# -- spawn_instance -----------------------------------------------------------


class TestSpawnInstance:
    @patch("helperai.gateway.subprocess.Popen")
    def test_spawns_personal(self, mock_popen, tmp_path):
        mock_popen.return_value = MagicMock(pid=99)
        with patch.object(gateway, "DATA_ROOT", tmp_path):
            inst = spawn_instance("user-1", instance_type="personal")

        assert inst.instance_id == "user-1"
        assert inst.port == PORT_RANGE_START
        assert inst.instance_type == "personal"
        assert PORT_RANGE_START in _used_ports
        mock_popen.assert_called_once()

    @patch("helperai.gateway.subprocess.Popen")
    def test_spawns_project(self, mock_popen, tmp_path):
        mock_popen.return_value = MagicMock(pid=100)
        with patch.object(gateway, "DATA_ROOT", tmp_path):
            inst = spawn_instance("proj-1", instance_type="project")

        assert inst.instance_type == "project"
        assert (tmp_path / "projects" / "proj-1").exists()


# -- stop_personal_instance / stop_project_instance ---------------------------


class TestStopInstances:
    def test_stop_personal(self):
        inst = _make_instance()
        _used_ports.add(inst.port)
        personal_instances["user-1"] = inst

        stop_personal_instance("user-1")

        assert "user-1" not in personal_instances
        inst.process.send_signal.assert_called()

    def test_stop_personal_missing_noop(self):
        stop_personal_instance("nonexistent")  # no error

    def test_stop_project(self):
        inst = _make_instance(instance_type="project")
        _used_ports.add(inst.port)
        project_instances["proj-1"] = inst

        stop_project_instance("proj-1")

        assert "proj-1" not in project_instances

    def test_stop_project_missing_noop(self):
        stop_project_instance("nonexistent")  # no error


# -- Instance class -----------------------------------------------------------


class TestInstanceClass:
    def test_attributes(self):
        proc = MagicMock()
        inst = Instance(instance_id="u1", port=10001, process=proc, instance_type="personal")
        assert inst.instance_id == "u1"
        assert inst.port == 10001
        assert inst.instance_type == "personal"
        assert isinstance(inst.connected_users, set)
        assert len(inst.connected_users) == 0
        assert inst.last_active > 0


# -- Gateway health endpoint --------------------------------------------------


class TestGatewayHealth:
    def test_health_check(self):
        from fastapi.testclient import TestClient

        client = TestClient(gateway.app)
        resp = client.get("/gateway/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "personal_instances" in data
        assert "project_instances" in data
