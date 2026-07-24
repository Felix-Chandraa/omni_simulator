"""Receiver stream FGNetFDM: thread UDP -> callback frame terdecimasi.

Peran dalam arsitektur dual-channel Ver 0:
  FG stream (modul ini)  -> pose visual high-rate (lat/lon/alt/attitude)
  MAVLink (MavWorker)    -> state & command (mode, armed, battery, arm, RTL)

Perilaku penting:
- DRAIN-TO-LATEST: SITL non-throttled bisa mengirim >1000 paket/detik.
  Semua paket pending dibaca habis, hanya yang TERBARU yang diproses,
  supaya tidak ada backlog di socket buffer (= latency visual).
- DECIMASI: callback dipanggil maksimal `publish_hz` kali/detik. Browser
  render 60 fps; mendorong 1200 msg/s lewat sinyal Qt + WebSocket sia-sia.
- Modul ini sengaja BEBAS PyQt: callback polos, gampang di-unit-test.
  Pemanggilan pyqtSignal.emit dari thread ini aman (queued connection).
"""
from __future__ import annotations

import socket
import threading
import time
from typing import Callable, Optional

from src.fg_link.fgnetfdm import FDMFrame, FDMParseError, parse_fdm

_SOCKET_TIMEOUT_SEC = 0.5
_RATE_WINDOW_SEC = 1.0


class FGReceiver:
    """Konsumsi stream FGNetFDM v24 di UDP, publish frame terbaru @ publish_hz."""

    def __init__(
        self,
        port: int,
        on_frame: Callable[[FDMFrame], None],
        publish_hz: float = 30.0,
        host: str = "0.0.0.0",
        on_status: Optional[Callable[[str], None]] = None,
    ):
        self._port = port
        self._host = host
        self._on_frame = on_frame
        self._min_publish_interval = 1.0 / publish_hz
        self._on_status = on_status or (lambda msg: None)

        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._first_frame = threading.Event()

        # Statistik diagnostik (dibaca dari thread lain: nilai float atomik)
        self.rx_hz = 0.0        # rate paket masuk terukur
        self.rx_total = 0
        self.bad_total = 0

    def start(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self._host, self._port))
        sock.settimeout(_SOCKET_TIMEOUT_SEC)
        self._sock = sock
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="FGReceiver", daemon=True)
        self._thread.start()

    def wait_first_frame(self, timeout: float) -> bool:
        """Blokir sampai frame v24 valid pertama diterima. Dipakai auto_connect
        sebagai probe: True = stream FG memang aktif."""
        return self._first_frame.wait(timeout)

    def stop(self) -> None:
        self._running = False
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        if self._thread and self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout=1.0)

    # ------------------------------------------------------------------ #

    def _drain_to_latest(self, first_pkt: bytes) -> bytes:
        """Baca habis paket pending, kembalikan yang paling baru."""
        latest = first_pkt
        self._sock.setblocking(False)
        try:
            while True:
                try:
                    latest, _ = self._sock.recvfrom(4096)
                    self.rx_total += 1
                except BlockingIOError:
                    break
        finally:
            self._sock.settimeout(_SOCKET_TIMEOUT_SEC)
        return latest

    def _loop(self) -> None:
        last_publish = 0.0
        window_start = time.monotonic()
        rx_at_window_start = 0

        while self._running:
            try:
                pkt, _ = self._sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:  # socket ditutup oleh stop()
                break

            self.rx_total += 1
            pkt = self._drain_to_latest(pkt)

            try:
                frame = parse_fdm(pkt)
            except FDMParseError as e:
                self.bad_total += 1
                if self.bad_total <= 3:
                    self._on_status(f"FG stream: paket invalid ({e})")
                continue

            self._first_frame.set()

            now = time.monotonic()
            if now - window_start >= _RATE_WINDOW_SEC:
                self.rx_hz = (self.rx_total - rx_at_window_start) / (now - window_start)
                rx_at_window_start = self.rx_total
                window_start = now

            if now - last_publish >= self._min_publish_interval:
                last_publish = now
                self._on_frame(frame)