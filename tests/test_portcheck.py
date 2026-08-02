"""Tests for the launcher's protection against an already-running server."""

from __future__ import annotations

import socket
from pathlib import Path

from app.portcheck import port_is_available


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_port_check_detects_a_listening_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        occupied_port = listener.getsockname()[1]

        assert port_is_available("127.0.0.1", occupied_port) is False


def test_port_check_accepts_a_released_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        released_port = reservation.getsockname()[1]

    assert port_is_available("127.0.0.1", released_port) is True


def test_launchers_check_the_port_before_opening_the_browser():
    for launcher_name in ("run.bat", "run.sh"):
        launcher = (PROJECT_ROOT / launcher_name).read_text(encoding="utf-8")

        assert launcher.index("app.portcheck") < launcher.index("?commit=12")
