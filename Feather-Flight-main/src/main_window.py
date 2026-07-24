import json
from typing import Any, Dict, List

from PyQt6.QtCore import QTimer, QUrl
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView

from config import DRAWABLE_MISSION_COMMANDS, MAP_URL, TELEMETRY_BUS_HOST, TELEMETRY_BUS_PORT
from .mav_worker import MavWorker
from .preflight_dialog import PreflightDialog
from .telemetry_bus import TelemetryBus

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Feather Flight")
        self.resize(1600, 950)

        self.worker = MavWorker()
        
        # F1: bus WebSocket utk window/monitor tambahan. GUI PyQt TETAP disuapi
        # lewat runJavaScript (regresi nol); bus adalah jalur PARALEL, bukan
        # pengganti (transisi). Gagal start bus tidak boleh menjatuhkan GUI.
        self.bus = TelemetryBus(
            host=TELEMETRY_BUS_HOST,
            port=TELEMETRY_BUS_PORT,
            on_client_message=self._on_bus_message,
        )
        try:
            if not self.bus.start(timeout=3.0):
                print("[F1] Telemetry bus gagal start (port dipakai?) — GUI tetap jalan.")
        except Exception as exc:  # websockets belum terpasang, dll.
            print(f"[F1] Telemetry bus nonaktif: {exc}")
            
        self.current_telemetry: Dict[str, Any] = {}
        self.mission_items: List[Dict[str, Any]] = []
        self.preflight_complete = False
        self.preflight_missing: List[str] = []
        self._preflight_disarm_issued = False
        self._map_loaded = False

        self._build_ui()
        self._wire_signals()

        self.preflight_dialog.evaluate_state()
        QTimer.singleShot(100, self.worker.start)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.web = QWebEngineView()
        self.web.loadFinished.connect(self._on_map_load_finished)
        self.web.load(QUrl(MAP_URL))
        layout.addWidget(self.web, stretch=1)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(10, 10, 10, 10)
        bottom.setSpacing(10)

        self.btn_preflight = QPushButton("Preflight Checklist")
        self.btn_fetch = QPushButton("Fetch Waypoints")
        self.btn_arm = QPushButton("Arm")
        self.btn_disarm = QPushButton("Disarm")
        self.btn_rtl = QPushButton("Return to Home")
        self.btn_auto = QPushButton("AUTO")

        self.preflight_state_label = QLabel("Preflight incomplete")
        self.preflight_state_label.setStyleSheet("color: #ffb020; font-weight: 600;")
        self.preflight_state_label.setMinimumWidth(160)

        self.status = QLabel("Connecting...")
        self.status.setMinimumWidth(300)

        bottom.addWidget(self.btn_preflight)
        bottom.addWidget(self.btn_fetch)
        bottom.addWidget(self.btn_arm)
        bottom.addWidget(self.btn_disarm)
        bottom.addWidget(self.btn_rtl)
        bottom.addWidget(self.btn_auto)
        bottom.addWidget(self.preflight_state_label)
        bottom.addStretch(1)
        bottom.addWidget(self.status)

        bottom_frame = QFrame()
        bottom_frame.setLayout(bottom)
        layout.addWidget(bottom_frame, stretch=0)

        self.preflight_dialog = PreflightDialog(self)

    def _wire_signals(self):
        self.btn_preflight.clicked.connect(self.open_preflight_dialog)
        self.btn_fetch.clicked.connect(self.on_fetch_waypoints)
        self.btn_arm.clicked.connect(self.on_arm_clicked)
        self.btn_disarm.clicked.connect(self.on_disarm_clicked)
        self.btn_rtl.clicked.connect(self.on_rtl_clicked)
        self.btn_auto.clicked.connect(self.on_auto_clicked)

        self.preflight_dialog.status_changed.connect(self.on_preflight_status_update)

        self.worker.status.connect(self.status.setText)
        self.worker.telemetry.connect(self.on_telemetry)
        self.worker.mission_received.connect(self.on_mission_received)

    def _on_map_load_finished(self, ok: bool):
        self._map_loaded = ok
        if not ok:
            self.status.setText("Failed to load map.html")
            return

        self.sync_preflight_status_js()
        
        # Tandai halaman ini sbg host PyQt: bus.js di dalamnya TIDAK ikut konek
        # ke bus (sudah disuapi runJavaScript) -> cegah double-feed telemetri.
        self.run_js("window.__OMNI_PYQT_HOST__ = true;")
        
        self.update_hud()
        self.render_mission_on_map()

    def _on_bus_message(self, msg: dict, _ws) -> None:
        """Pesan client->server dari bus (F1: hanya di-log). Validasi = P4."""
        # DILARANG mengeksekusi cmd arbitrer di sini; instructor_api (P4) yang
        # memvalidasi whitelist skenario. F1 sekadar membuktikan jalur hidup.
        if msg.get("type") == "cmd":
            print(f"[F1] cmd diterima dari bus (belum dieksekusi): {msg}")

    def run_js(self, script: str):
        if self._map_loaded and self.web and self.web.page():
            self.web.page().runJavaScript(script)

    def _call_js_function(self, function_name: str, payload: Any):
        script = f"""
            if (window.{function_name}) {{
                window.{function_name}({json.dumps(payload)});
            }}
        """
        self.run_js(script)

    def sync_preflight_status_js(self):
        payload = {
            "complete": self.preflight_complete,
            "missing": self.preflight_missing,
        }
        self._call_js_function("setPreflightStatus", payload)

    def on_preflight_status_update(self, complete: bool, missing: List[str]):
        self.preflight_complete = complete
        self.preflight_missing = missing

        if complete:
            self.preflight_state_label.setText("Preflight complete ✓")
            self.preflight_state_label.setStyleSheet("color: #33d17a; font-weight: 600;")
        else:
            self.preflight_state_label.setText("Preflight incomplete")
            self.preflight_state_label.setStyleSheet("color: #ffb020; font-weight: 600;")

        self.sync_preflight_status_js()
        self.update_hud()

    def open_preflight_dialog(self):
        self.preflight_dialog.show()
        self.preflight_dialog.raise_()
        self.preflight_dialog.activateWindow()

    def update_hud(self):
        t = self.current_telemetry
        payload = {
            "roll": t.get("roll", 0.0),
            "pitch": t.get("pitch", 0.0),
            "yaw": t.get("yaw", 0.0),
            "hdg": t.get("heading"),
            "as": t.get("airspeed"),
            "alt": t.get("alt"),
            "alt_msl": t.get("alt_msl"),
            "agl": t.get("agl"),
            "pose_source": t.get("pose_source"),
            "vehicle_type": t.get("vehicle_type"),
            "gs": t.get("groundspeed"),
            "lat": t.get("lat"),
            "lon": t.get("lon"),
            "armed": t.get("armed"),
            "mode": t.get("mode", "UNKNOWN"),
            "bat": t.get("battery"),
            "bat_pct": t.get("battery_pct"),
            "fuel_pct": t.get("fuel_pct"),
            "throttle": t.get("throttle"),
            "srv1": t.get("srv1"),
            "srv2": t.get("srv2"),
            "srv4": t.get("srv4"),
            "throttle": t.get("throttle"),
            "srv1": t.get("srv1"),
            "srv2": t.get("srv2"),
            "srv4": t.get("srv4"),
            "sat": t.get("satellites"),
            "gps_fix_type": t.get("gps_fix_type"),
            "home_lat": t.get("home_lat"),
            "home_lon": t.get("home_lon"),
            "home_alt": t.get("home_alt"),
            "home_source": t.get("home_source"),
            "preflight_complete": self.preflight_complete,
            "preflight_missing": self.preflight_missing,
        }

        self._call_js_function("updateHUD", payload)
        
        # F1: siarkan payload YANG SAMA ke bus -> window browser identik dgn
        # window PyQt by construction (satu titik rakit telemetri UI).
        self.bus.publish_telemetry(payload)

    def _record_home_from_current_telemetry(self, source: str) -> bool:
        recorded, snapshot = self.worker.record_home_from_telemetry(self.current_telemetry, source)
        if recorded:
            self.current_telemetry.update(snapshot)
        return recorded

    def on_arm_clicked(self):
        if not self.preflight_complete:
            QMessageBox.warning(
                self,
                "Preflight Incomplete",
                "You must complete the preflight checklist before arming the aircraft.",
            )
            return

        if self.worker.arm(True):
            self._record_home_from_current_telemetry("armed")
            self.update_hud()

    def on_disarm_clicked(self):
        self.worker.arm(False)

    def on_rtl_clicked(self):
        self.worker.rtl()

    def on_auto_clicked(self):
        self.worker.auto_mode()

    def on_telemetry(self, telemetry: Dict[str, Any]):
        previous_armed = self.current_telemetry.get("armed", False)
        self.current_telemetry = dict(telemetry)

        if self.current_telemetry.get("armed") and not previous_armed:
            self._record_home_from_current_telemetry("armed")

        if self.current_telemetry.get("armed") and not self.preflight_complete:
            if not self._preflight_disarm_issued:
                self._preflight_disarm_issued = True
                if self.worker.arm(False):
                    self.status.setText("Disarmed: Preflight checklist incomplete")
        else:
            self._preflight_disarm_issued = False

        self.update_hud()

    def on_fetch_waypoints(self):
        try:
            self.status.setText("Downloading mission...")
            items = self.worker.download_mission()
            self.mission_items = items
            self.render_mission_on_map()
            self.status.setText(f"Downloaded {len(items)} waypoints")
            QMessageBox.information(
                self,
                "Waypoints",
                f"Downloaded {len(items)} waypoints from aircraft.",
            )
        except Exception as e:
            self.status.setText(str(e))
            QMessageBox.critical(self, "Mission Download Error", str(e))

    def on_mission_received(self, items):
        self.mission_items = items
        self.render_mission_on_map()

    def render_mission_on_map(self):
        points = [
            [w["lat"], w["lon"], w["alt"], w["seq"]]
            for w in self.mission_items
            if w["command"] in DRAWABLE_MISSION_COMMANDS
        ]
        self._call_js_function("setMissionPath", points)

    def closeEvent(self, event):
        self.worker.stop()
        self.bus.stop()
        super().closeEvent(event)