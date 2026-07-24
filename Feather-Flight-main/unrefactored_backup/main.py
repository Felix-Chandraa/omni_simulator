import sys
import math
import json
import threading
import http.server
import socketserver
import os
import time

from pymavlink import mavutil

from PyQt6.QtCore import Qt, QObject, pyqtSignal, QUrl, QTimer
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QMessageBox, QFrame, QCheckBox, QDialog
)
from PyQt6.QtWebEngineWidgets import QWebEngineView


PORT = 8000


def start_server():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
        httpd.serve_forever()


class MavWorker(QObject):
    telemetry = pyqtSignal(dict)
    status = pyqtSignal(str)
    mission_received = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.master = None
        self.running = False
        self.thread = None
        self.mission_lock = threading.Lock()
        self.pause_telemetry = False
        self.state = {
            "lat": None,
            "lon": None,
            "alt": None,
            "alt_msl": None,
            "groundspeed": None,
            "airspeed": None,
            "heading": None,
            "roll": 0.0,
            "pitch": 0.0,
            "yaw": 0.0,
            "mode": "UNKNOWN",
            "armed": False,
            "satellites": None,
            "gps_fix_type": None,
            "battery": None,
            "home_lat": None,
            "home_lon": None,
            "home_alt": None,
            "home_source": None,
        }
        self._mode_lookup = {}
        self._vehicle_key = None

    def auto_connect(self):
        candidates = [
            "udp:127.0.0.1:14550",
            "/dev/ttyACM0",
            "/dev/ttyUSB0",
            "COM3",
            "COM4",
        ]

        for conn in candidates:
            try:
                self.status.emit(f"Trying {conn} ...")
                m = mavutil.mavlink_connection(conn, autoreconnect=True)
                hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=5)
                if hb:
                    self.master = m
                    self.status.emit(f"Connected: {conn}")
                    return True
            except Exception:
                continue

        self.status.emit("Auto-connect failed.")
        return False

    def start(self):
        if self.running:
            return
        if not self.master and not self.auto_connect():
            return
        self.running = True
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _record_home_from_current_position(self, source: str):
        lat = self.state.get("lat")
        lon = self.state.get("lon")
        fix_type = self.state.get("gps_fix_type")

        if lat is None or lon is None:
            return False

        if fix_type is not None and fix_type < 3:
            return False

        home_alt = self.state.get("alt_msl")
        if home_alt is None:
            home_alt = self.state.get("alt")

        self.state["home_lat"] = lat
        self.state["home_lon"] = lon
        self.state["home_alt"] = home_alt
        self.state["home_source"] = source
        return True

    def loop(self):
        try:
            self.request_streams()

            while self.running:
                if self.pause_telemetry:
                    time.sleep(0.05)
                    continue

                msg = self.master.recv_match(blocking=False)
                if msg is None:
                    continue

                t = msg.get_type()

                if t == "HEARTBEAT":
                    armed_now = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                    if armed_now and not self.state["armed"]:
                        self._record_home_from_current_position("armed")
                    self.state["armed"] = armed_now
                    self._refresh_mode_lookup(msg)
                    self.state["mode"] = self.mode_name(msg.custom_mode)

                elif t == "GLOBAL_POSITION_INT":
                    self.state["lat"] = msg.lat / 1e7
                    self.state["lon"] = msg.lon / 1e7
                    self.state["alt"] = msg.relative_alt / 1000.0
                    self.state["alt_msl"] = msg.alt / 1000.0
                    self.state["heading"] = msg.hdg / 100.0 if msg.hdg != 65535 else None
                    self.state["groundspeed"] = math.sqrt((msg.vx / 100.0) ** 2 + (msg.vy / 100.0) ** 2)

                elif t == "ATTITUDE":
                    self.state["roll"] = math.degrees(msg.roll)
                    self.state["pitch"] = math.degrees(msg.pitch)
                    self.state["yaw"] = math.degrees(msg.yaw)

                elif t == "VFR_HUD":
                    self.state["groundspeed"] = msg.groundspeed
                    self.state["airspeed"] = msg.airspeed
                    self.state["alt_msl"] = msg.alt
                    self.state["heading"] = msg.heading

                elif t == "GPS_RAW_INT":
                    self.state["lat"] = msg.lat / 1e7
                    self.state["lon"] = msg.lon / 1e7
                    self.state["satellites"] = msg.satellites_visible
                    self.state["gps_fix_type"] = msg.fix_type
                    self.state["alt_msl"] = msg.alt / 1000.0

                    should_seed_home = (
                        self.state["home_lat"] is None
                        or self.state["home_lon"] is None
                        or self.state["home_source"] in (None, "default", "mission")
                    )
                    if msg.fix_type >= 3 and should_seed_home:
                        self._record_home_from_current_position("gps")

                elif t == "SYS_STATUS":
                    if msg.voltage_battery != 65535:
                        self.state["battery"] = msg.voltage_battery / 1000.0

                elif t == "HOME_POSITION":
                    self.state["home_lat"] = msg.latitude / 1e7
                    self.state["home_lon"] = msg.longitude / 1e7
                    altitude = getattr(msg, "altitude", getattr(msg, "alt", None))
                    self.state["home_alt"] = altitude / 1000.0 if altitude is not None else None
                    self.state["home_source"] = "home_position"

                self.telemetry.emit(dict(self.state))

        except Exception as e:
            self.status.emit(f"Telemetry loop error: {e}")
        finally:
            self.running = False

    def request_streams(self):
        try:
            self.master.mav.request_data_stream_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_ALL,
                5,
                1
            )
        except Exception:
            pass

    def _refresh_mode_lookup(self, heartbeat_msg):
        if not self.master:
            self._mode_lookup = {}
            self._vehicle_key = None
            return

        key = (heartbeat_msg.autopilot, heartbeat_msg.type)
        if key == self._vehicle_key and self._mode_lookup:
            return

        mapping = self.master.mode_mapping()
        reverse = {}
        if mapping:
            reverse = {int(mode_id): name for name, mode_id in mapping.items()}
        self._mode_lookup = reverse
        self._vehicle_key = key

    def mode_name(self, custom_mode):
        return self._mode_lookup.get(custom_mode, f"MODE_{custom_mode}")

    def arm(self, arm_state: bool):
        if not self.master:
            return
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1 if arm_state else 0,
            0, 0, 0, 0, 0, 0
        )

    def rtl(self):
        if not self.master:
            return
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
            0,
            0, 0, 0, 0, 0, 0, 0
        )

    def download_mission(self):
        if not self.master:
            return []

        with self.mission_lock:
            self.pause_telemetry = True
            try:
                self.master.mav.mission_request_list_send(
                    self.master.target_system,
                    self.master.target_component
                )

                count_msg = None
                for _ in range(50):
                    msg = self.master.recv_match(
                        type="MISSION_COUNT",
                        blocking=True,
                        timeout=0.2
                    )
                    if msg is not None:
                        count_msg = msg
                        break

                if count_msg is None:
                    raise RuntimeError("No MISSION_COUNT received")

                count = count_msg.count
                if count == 0:
                    self.mission_received.emit([])
                    return []

                items = {}

                for seq in range(count):
                    got_item = False

                    for _ in range(5):
                        self.master.mav.mission_request_send(
                            self.master.target_system,
                            self.master.target_component,
                            seq
                        )

                        for _ in range(20):
                            msg = self.master.recv_match(
                                type=["MISSION_ITEM", "MISSION_ITEM_INT", "MISSION_ACK"],
                                blocking=True,
                                timeout=0.2
                            )

                            if msg is None:
                                continue

                            if msg.get_type() == "MISSION_ACK":
                                continue

                            if msg.get_type() == "MISSION_ITEM_INT":
                                lat = msg.x / 1e7
                                lon = msg.y / 1e7
                                alt = msg.z
                            else:
                                lat = msg.x
                                lon = msg.y
                                alt = msg.z

                            item = {
                                "seq": msg.seq,
                                "command": msg.command,
                                "frame": msg.frame,
                                "lat": lat,
                                "lon": lon,
                                "alt": alt,
                            }

                            items[msg.seq] = item

                            if msg.seq == seq:
                                got_item = True
                                break

                        if got_item:
                            break

                    if not got_item:
                        raise RuntimeError(f"Timeout waiting for mission item {seq}")

                mission = [items[k] for k in sorted(items.keys())]
                self.mission_received.emit(mission)
                return mission

            finally:
                self.pause_telemetry = False

    def auto_mode(self):
        if not self.master:
            return

        try:
            mode_mapping = self.master.mode_mapping()
            if mode_mapping is None or "AUTO" not in mode_mapping:
                raise RuntimeError("AUTO mode not supported by this vehicle")

            mode_id = mode_mapping["AUTO"]
            self.master.set_mode(mode_id)
        except Exception as e:
            self.status.emit(f"Failed to set AUTO: {e}")


class PreflightDialog(QDialog):
    status_changed = pyqtSignal(bool, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preflight Checklist")
        self.setModal(False)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("""
            QDialog {
                background: rgba(10, 15, 24, 0.95);
                border: 1px solid #1f2740;
                border-radius: 16px;
            }
            QLabel {
                color: #e5eefc;
            }
            QCheckBox {
                color: #cfd7eb;
            }
            QPushButton {
                color: #d3d9ff;
                background: transparent;
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 8px;
            }
            QPushButton:hover {
                border-color: rgba(255, 255, 255, 0.6);
            }
        """)
        self.setMinimumWidth(340)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("Preflight Checklist")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(title)

        self.status_label = QLabel("Preflight incomplete")
        self.status_label.setStyleSheet("color: #ffb020; font-weight: 600;")
        layout.addWidget(self.status_label)

        self.checkboxes = []
        checklist_items = [
            "Battery voltage verified",
            "GPS fix (≥ 3)",
            "Home position recorded",
            "Mission reviewed"
        ]
        for item_text in checklist_items:
            cb = QCheckBox(item_text)
            cb.stateChanged.connect(self.evaluate_state)
            layout.addWidget(cb)
            self.checkboxes.append(cb)

        layout.addStretch(1)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        close_btn.setFixedSize(80, 30)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

        self.evaluate_state()

    def evaluate_state(self):
        missing = [cb.text() for cb in self.checkboxes if not cb.isChecked()]
        complete = len(missing) == 0
        if complete:
            self.status_label.setText("Preflight complete ✓")
            self.status_label.setStyleSheet("color: #33d17a; font-weight: 600;")
        else:
            self.status_label.setText("Preflight incomplete")
            self.status_label.setStyleSheet("color: #ffb020; font-weight: 600;")
        self.status_changed.emit(complete, missing)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Beta Flight")
        self.resize(1600, 950)

        self.worker = MavWorker()
        self.current_telemetry = {}
        self.mission_items = []
        self.preflight_complete = False
        self.preflight_missing = []
        self._preflight_disarm_issued = False

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.web = QWebEngineView()
        self.web.load(QUrl(f"http://127.0.0.1:{PORT}/map.html"))
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
        self.status = QLabel("Connecting...")
        self.status.setMinimumWidth(300)

        self.preflight_state_label = QLabel("Preflight incomplete")
        self.preflight_state_label.setStyleSheet("color: #ffb020; font-weight: 600;")
        self.preflight_state_label.setMinimumWidth(160)

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
        self.preflight_dialog.status_changed.connect(self.on_preflight_status_update)

        self.btn_preflight.clicked.connect(self.open_preflight_dialog)
        self.btn_fetch.clicked.connect(self.on_fetch_waypoints)
        self.btn_arm.clicked.connect(self.on_arm_clicked)
        self.btn_disarm.clicked.connect(lambda: self.worker.arm(False))
        self.btn_rtl.clicked.connect(self.worker.rtl)
        self.btn_auto.clicked.connect(self.worker.auto_mode)

        self.worker.status.connect(self.status.setText)
        self.worker.telemetry.connect(self.on_telemetry)
        self.worker.mission_received.connect(self.on_mission_received)

        QTimer.singleShot(100, self.worker.start)
        self.preflight_dialog.evaluate_state()

    def run_js(self, script):
        if self.web and self.web.page():
            self.web.page().runJavaScript(script)

    def sync_preflight_status_js(self):
        payload = {
            "complete": self.preflight_complete,
            "missing": self.preflight_missing
        }
        script = f"""
            if (window.setPreflightStatus) {{
                window.setPreflightStatus({json.dumps(payload)});
            }}
        """
        self.run_js(script)

    def on_preflight_status_update(self, complete, missing):
        self.preflight_complete = complete
        self.preflight_missing = missing
        if complete:
            self.preflight_state_label.setText("Preflight complete ✓")
            self.preflight_state_label.setStyleSheet("color: #33d17a; font-weight: 600;")
        else:
            self.preflight_state_label.setText("Preflight incomplete")
            self.preflight_state_label.setStyleSheet("color: #ffb020; font-weight: 600;")
        self.sync_preflight_status_js()

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
            "gs": t.get("groundspeed"),
            "lat": t.get("lat"),
            "lon": t.get("lon"),
            "armed": t.get("armed"),
            "mode": t.get("mode", "UNKNOWN"),
            "bat": t.get("battery"),
            "sat": t.get("satellites"),
            "gps_fix_type": t.get("gps_fix_type"),
            "home_lat": t.get("home_lat"),
            "home_lon": t.get("home_lon"),
            "home_alt": t.get("home_alt"),
            "home_source": t.get("home_source"),
            "preflight_complete": self.preflight_complete,
            "preflight_missing": self.preflight_missing
        }

        js = f"""
            if (window.updateHUD) {{
                window.updateHUD({json.dumps(payload)});
            }}
        """
        self.run_js(js)

    def on_arm_clicked(self):
        if not self.preflight_complete:
            QMessageBox.warning(
                self,
                "Preflight Incomplete",
                "You must complete the preflight checklist before arming the aircraft."
            )
            return

        self.worker.arm(True)
        self.record_home_from_current_position("armed")
        self.update_hud()

    def record_home_from_current_position(self, source="armed"):
        lat = self.current_telemetry.get("lat")
        lon = self.current_telemetry.get("lon")
        fix_type = self.current_telemetry.get("gps_fix_type")

        if lat is None or lon is None:
            return False

        if fix_type is not None and fix_type < 3:
            return False

        home_alt = self.current_telemetry.get("alt_msl")
        if home_alt is None:
            home_alt = self.current_telemetry.get("alt")

        self.worker.state["home_lat"] = lat
        self.worker.state["home_lon"] = lon
        self.worker.state["home_alt"] = home_alt
        self.worker.state["home_source"] = source

        self.current_telemetry["home_lat"] = lat
        self.current_telemetry["home_lon"] = lon
        self.current_telemetry["home_alt"] = home_alt
        self.current_telemetry["home_source"] = source

        return True

    def on_telemetry(self, t):
        previous_armed = self.current_telemetry.get("armed", False)
        self.current_telemetry = dict(t)

        if self.current_telemetry.get("armed") and not previous_armed:
            self.record_home_from_current_position("armed")

        if self.current_telemetry.get("armed") and not self.preflight_complete:
            if not self._preflight_disarm_issued:
                self._preflight_disarm_issued = True
                self.worker.arm(False)
                self.status.setText("Disarmed: Preflight checklist incomplete")
        else:
            self._preflight_disarm_issued = False

        self.update_hud()

    def on_fetch_waypoints(self):
        try:
            items = self.worker.download_mission()
            self.mission_items = items
            self.render_mission_on_map()
            QMessageBox.information(self, "Waypoints", f"Downloaded {len(items)} waypoints from aircraft.")
        except Exception as e:
            QMessageBox.critical(self, "Mission Download Error", str(e))

    def on_mission_received(self, items):
        self.mission_items = items
        self.render_mission_on_map()

    def render_mission_on_map(self):
        if not self.mission_items:
            return

        drawable_commands = {16, 22}

        points = [
            [w["lat"], w["lon"], w["alt"], w["seq"]]
            for w in self.mission_items
            if w["command"] in drawable_commands
        ]

        js = f"""
            if (window.setMissionPath) {{
                window.setMissionPath({json.dumps(points)});
            }}
        """
        self.run_js(js)


def main():
    threading.Thread(target=start_server, daemon=True).start()

    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()