from __future__ import annotations

import re
import shutil
import socket
import sys
from dataclasses import dataclass


@dataclass
class TcpEndpoint:
    host: str
    port: int


def python_executable() -> str:
    return sys.executable or shutil.which("python3") or "python3"


def parse_tcp_endpoint(connect: str) -> TcpEndpoint | None:
    match = re.match(r"^tcp:([^:]+):(\d+)$", connect.strip())
    if not match:
        return None
    return TcpEndpoint(match.group(1), int(match.group(2)))


def is_tcp_port_open(endpoint: TcpEndpoint, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((endpoint.host, endpoint.port), timeout=timeout):
            return True
    except OSError:
        return False
