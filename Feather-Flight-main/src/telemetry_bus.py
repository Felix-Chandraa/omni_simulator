"""F1 — Telemetry Bus WebSocket (broadcaster multi-window).

Peran (SDD Bab 3 / F1): mengganti bridge lama `runJavaScript` ke SATU
QWebEngineView agar telemetri bisa dikonsumsi banyak window/monitor.

Desain:
- Server WebSocket asyncio yang berjalan di THREAD-nya sendiri (daemon), jadi
  event loop GUI PyQt tidak terganggu (regresi nol). BEBAS PyQt -> bisa
  di-unit-test headless & dipakai ulang di luar GUI.
- `broadcast(message)` AMAN dipanggil dari thread Qt (worker/GUI): pekerjaan
  socket dijadwalkan ke loop bus via run_coroutine_threadsafe.
- Pesan ber-ENVELOPE (SDD F1): {"type":"telemetry","data":{...}},
  {"type":"event",...}, dan arah client->server {"type":"cmd",...} yang
  DITERUSKAN ke callback `on_client_message` (validasi keras menyusul di P4
  `instructor_api` — di F1 hanya di-plumb, TIDAK dieksekusi).

Invarian: bus TIDAK menurunkan/menyatukan besaran apa pun (Bab 2.3). Ia hanya
menyiarkan payload yang SUDAH dirakit di satu titik (main_window.update_hud) —
sumber tunggal telemetri UI -> semua window identik by construction.
"""
from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, Callable, Optional, Set

try:
    import websockets
    from websockets.legacy.server import WebSocketServerProtocol  # type: ignore
except Exception:  # pragma: no cover - dependency check happens di startup
    websockets = None  # type: ignore
    WebSocketServerProtocol = Any  # type: ignore


ClientMessageHandler = Callable[[dict, "WebSocketServerProtocol"], None]


class TelemetryBus:
    """WebSocket broadcaster satu-ke-banyak untuk telemetri Omni-Trainer."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        on_client_message: Optional[ClientMessageHandler] = None,
    ) -> None:
        if websockets is None:
            raise RuntimeError(
                "paket 'websockets' belum terpasang. Jalankan: "
                "pip install websockets  (lihat requirements.txt)"
            )
        self._host = host
        self._port = port
        self._on_client_message = on_client_message

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._server = None
        self._clients: Set["WebSocketServerProtocol"] = set()
        self._ready = threading.Event()
        self._running = False

    # ---- lifecycle ---------------------------------------------------- #

    def start(self, timeout: float = 3.0) -> bool:
        """Mulai server di thread sendiri. True bila siap menerima koneksi."""
        if self._running:
            return True
        self._thread = threading.Thread(
            target=self._run, name="TelemetryBus", daemon=True
        )
        self._thread.start()
        ok = self._ready.wait(timeout)
        self._running = ok
        return ok

    def stop(self) -> None:
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._running = False

    @property
    def client_count(self) -> int:
        return len(self._clients)

    # ---- publish (thread-safe) --------------------------------------- #

    def broadcast(self, message: dict) -> None:
        """Kirim satu envelope ke semua client. Aman dari thread mana pun.

        Fire-and-forget: tidak memblokir pemanggil (Qt thread). Payload
        di-serialize sekali; client yang putus dibuang di coroutine bus.
        """
        if not self._running or self._loop is None:
            return
        try:
            text = json.dumps(message, separators=(",", ":"), default=_json_default)
        except (TypeError, ValueError):
            return
        # jadwalkan di loop bus; tidak menunggu hasil
        asyncio.run_coroutine_threadsafe(self._broadcast(text), self._loop)

    def publish_telemetry(self, data: dict) -> None:
        """Convenience: bungkus payload UI sbg envelope telemetry."""
        self.broadcast({"type": "telemetry", "data": data})

    def publish_event(self, name: str, **payload: Any) -> None:
        self.broadcast({"type": "event", "name": name, **payload})

    # ---- internals (jalan di loop bus) ------------------------------- #

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._serve())
            self._ready.set()
            loop.run_forever()
        except OSError as exc:  # port dipakai / bind gagal
            self._bind_error = exc  # type: ignore[attr-defined]
            self._ready.set()  # lepaskan start(); _running akan False krn server None
        finally:
            if self._server is not None:
                self._server.close()
            pending = asyncio.all_tasks(loop) if loop.is_running() else set()
            for task in pending:
                task.cancel()
            loop.run_until_complete(asyncio.sleep(0))
            loop.close()

    async def _serve(self) -> None:
        self._server = await websockets.serve(
            self._handler, self._host, self._port, ping_interval=20
        )

    async def _handler(self, ws: "WebSocketServerProtocol") -> None:
        self._clients.add(ws)
        try:
            async for raw in ws:
                self._on_inbound(raw, ws)
        except Exception:
            pass
        finally:
            self._clients.discard(ws)

    def _on_inbound(self, raw: Any, ws: "WebSocketServerProtocol") -> None:
        if self._on_client_message is None:
            return
        try:
            msg = json.loads(raw)
        except (TypeError, ValueError):
            return
        if isinstance(msg, dict):
            # F1: hanya diteruskan. Validasi (whitelist skenario) = P4.
            self._on_client_message(msg, ws)

    async def _broadcast(self, text: str) -> None:
        if not self._clients:
            return
        dead = []
        for ws in list(self._clients):
            try:
                await ws.send(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)


def _json_default(obj: Any) -> Any:
    # Toleran terhadap tipe non-JSON (mis. numpy floats) tanpa crash broadcast.
    try:
        return float(obj)
    except (TypeError, ValueError):
        return str(obj)