from functools import partial
import http.server
import socketserver
from pathlib import Path

from config import BASE_DIR, PORT


class ReusableTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def start_server(directory: Path = BASE_DIR, port: int = PORT) -> None:
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    with ReusableTCPServer(("127.0.0.1", port), handler) as httpd:
        httpd.serve_forever()
