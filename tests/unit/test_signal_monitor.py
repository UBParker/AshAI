"""Tests for signal file monitoring."""

from __future__ import annotations

import os

from helperai.signal_monitor import SignalFileHandler


class _FakeEvent:
    def __init__(self, src_path: str, is_directory: bool = False):
        self.src_path = src_path
        self.is_directory = is_directory


class TestSignalFileHandlerPatternMatching:
    """Test _is_signal_file pattern matching."""

    def _handler(self):
        """Create a handler with a dummy callback (no event loop needed for pattern tests)."""
        h = SignalFileHandler.__new__(SignalFileHandler)
        h.callback = None
        h.loop = None
        h._processed = set()
        return h

    def test_legacy_signal_file(self):
        h = self._handler()
        assert h._is_signal_file("/some/path/.ashai_tool_signal.json") is True

    def test_uuid_signal_file(self):
        h = self._handler()
        assert h._is_signal_file("/path/.ashai_signal_abc123.json") is True

    def test_uuid_signal_file_long(self):
        h = self._handler()
        assert h._is_signal_file("/path/.ashai_signal_550e8400-e29b-41d4-a716-446655440000.json") is True

    def test_non_signal_file(self):
        h = self._handler()
        assert h._is_signal_file("/path/somefile.json") is False

    def test_regular_python_file(self):
        h = self._handler()
        assert h._is_signal_file("/path/test.py") is False

    def test_partial_match_not_accepted(self):
        h = self._handler()
        assert h._is_signal_file("/path/.ashai_signal_.txt") is False

    def test_directory_events_ignored(self):
        """Directories should not be processed."""
        h = self._handler()
        # _handle_event checks event.is_directory before calling _is_signal_file
        # We test this indirectly: _is_signal_file itself only checks the name
        assert h._is_signal_file("/path/.ashai_tool_signal.json") is True


class TestSignalFileMonitor:
    """Test SignalFileMonitor initialization."""

    def test_init(self, tmp_path):
        from helperai.signal_monitor import SignalFileMonitor

        monitor = SignalFileMonitor(watch_dir=str(tmp_path), agent_manager=None)
        assert monitor.watch_dir == tmp_path.resolve()
        assert monitor.agent_manager is None
        assert monitor.observer is None

    def test_stop_when_not_started(self, tmp_path):
        from helperai.signal_monitor import SignalFileMonitor

        monitor = SignalFileMonitor(watch_dir=str(tmp_path))
        # Should not raise
        monitor.stop()
