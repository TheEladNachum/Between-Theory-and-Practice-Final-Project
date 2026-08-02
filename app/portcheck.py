"""Small launcher preflight that prevents opening an older server by mistake."""

from __future__ import annotations

import argparse
import socket


def port_is_available(host: str, port: int) -> bool:
    """Return whether a TCP listener can bind exclusively to ``host:port``."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether a local TCP port is free.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if port_is_available(args.host, args.port):
        return 0

    print()
    print(f"  [X] Port {args.port} is already in use.")
    print("      Another IncidentIQ or Python server is probably still running.")
    print("      Close the old server (Ctrl+C), then run this launcher again.")
    print("      The browser was not opened, so it cannot show the older project.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
