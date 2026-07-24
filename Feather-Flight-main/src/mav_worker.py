import math
import threading
import time
from typing import Any, Dict, List, Tuple

from PyQt6.QtCore import QObject, pyqtSignal
from pymavlink import mavutil

from config import (
    CONNECTION_CANDIDATES,
    FG_FIELD_ELEV_MSL,
    FG_FIRST_FRAME_TIMEOUT_SEC,
    FG_PUBLISH_HZ,
    FG_STREAM_PORT,
    HEARTBEAT_TIMEOUT_SEC,
    IDLE_LOOP_SLEEP_SEC,
    MISSION_COUNT_RETRIES,
    MISSION_COUNT_WAIT_SEC,
    MISSION_ITEM_POLL_RETRIES,
    MISSION_ITEM_RETRIES,
    MISSION_ITEM_WAIT_SEC,
    TELEMETRY_PAUSE_SLEEP_SEC,
    TELEMETRY_SOURCE,
    TELEMETRY_STREAM_HZ,
)
from src.fg_link.fgnetfdm import FDMFrame
from src.fg_link.altitude import GroundDatum
from src.fg_link.receiver import FGReceiver


# F2: MAV_TYPE (HEARTBEAT.type) -> keluarga profil kendaraan. Nama keluarga
# = nama file di vehicle_profiles/<family>.json. Sumber enum: MAVLink common.
_COPTER_TYPES = {2, 3, 4, 13, 14, 15}          # quad/coax/heli/hexa/octo/tri
_ROVER_TYPES = {10, 11}                         # ground rover / surface boat
_FIXED_WING_TYPES = {1, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28}  # plane + VTOL


def _mav_type_family(mav_type: int) -> str:
    """Petakan MAV_TYPE ke nama profil. Default aman: fixed_wing."""
    if mav_type in _COPTER_TYPES:
        return "copter"
    if mav_type in _ROVER_TYPES:
        return "rover"
    if mav_type in _FIXED_WING_TYPES:
        return "fixed_wing"
    return "fixed_wing"


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
        self.state_lock = threading.Lock()
        self.pause_telemetry = False

        # Kanal pose high-rate (FG stream). "mavlink" = perilaku lama.
        self.fg: FGReceiver | None = None
        self.pose_source = "mavlink"  # "mavlink" | "fg"
        self.fg_ground = GroundDatum(override_msl=FG_FIELD_ELEV_MSL)

        self.state: Dict[str, Any] = {
            "lat": None,
            "lon": None,
            "alt": None,
            "alt_msl": None,
            "agl": None,
            "agl_raw": None,
            "vehicle_type": None,
            "pose_source": "mavlink",
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
            "battery_pct": None,
            "fuel_pct": None,
            "throttle": None,
            "srv1": None,
            "srv2": None,
            "srv3": None,
            "srv4": None,
            "throttle": None,
            "srv1": None,
            "srv2": None,
            "srv3": None,
            "srv4": None,
            "home_lat": None,
            "home_lon": None,
            "home_alt": None,
            "home_source": None,
        }

        self._mode_lookup = {}
        self._vehicle_key = None

    def _state_snapshot(self) -> Dict[str, Any]:
        with self.state_lock:
            return dict(self.state)

    def _emit_state(self) -> None:
        self.telemetry.emit(self._state_snapshot())

    def auto_connect(self, source: str = TELEMETRY_SOURCE) -> bool:
        """Pilih sumber telemetri (instruksi lead, Ver 0 langkah 2).

        source:
          "mavlink" -> perilaku lama: MAVLink saja.
          "auto"    -> MAVLink wajib; FG stream di-probe, dipakai utk pose
                       jika terdeteksi, fallback mulus ke MAVLink jika tidak.
          "fg"      -> FG stream wajib (gagal = False); MAVLink tetap dicoba
                       sebagai kanal command (arm/mode) tapi tidak memblokir.
        """
        mav_ok = self._connect_mavlink()
        fg_ok = self._connect_fg_stream() if source in ("auto", "fg") else False

        self.pose_source = "fg" if fg_ok else "mavlink"
        with self.state_lock:
            self.state["pose_source"] = self.pose_source

        if source == "fg":
            if fg_ok and not mav_ok:
                self.status.emit("FG pose aktif TANPA MAVLink: visual jalan, command mati.")
            return fg_ok
        return mav_ok

    def _connect_fg_stream(self) -> bool:
        try:
            self.fg_ground.reset()
            self.fg = FGReceiver(
                port=FG_STREAM_PORT,
                on_frame=self._on_fg_frame,
                publish_hz=FG_PUBLISH_HZ,
                on_status=self.status.emit,
            )
            self.fg.start()
            if self.fg.wait_first_frame(FG_FIRST_FRAME_TIMEOUT_SEC):
                self.status.emit(
                    f"FG stream aktif @ udp:{FG_STREAM_PORT} (pose {FG_PUBLISH_HZ} Hz)"
                )
                return True
            self.fg.stop()
            self.fg = None
            self.status.emit("FG stream tidak terdeteksi; pose memakai MAVLink.")
            return False
        except Exception as e:
            self.status.emit(f"FG stream gagal: {e}")
            if self.fg is not None:
                self.fg.stop()
                self.fg = None
            return False

    def _on_fg_frame(self, frame: FDMFrame) -> None:
        """Dipanggil dari thread FGReceiver @ FG_PUBLISH_HZ. Hanya field POSE."""
        with self.state_lock:
            self.state["lat"] = frame.lat_deg
            self.state["lon"] = frame.lon_deg
            self.state["alt_msl"] = frame.alt_m
            self.state["agl"] = self.fg_ground.agl_from(frame.alt_m)
            self.state["agl_raw"] = frame.agl_m
            self.state["roll"] = frame.roll_deg
            self.state["pitch"] = frame.pitch_deg
            self.state["yaw"] = frame.yaw_deg
            self.state["heading"] = frame.yaw_deg % 360.0
        self._emit_state()

    def _connect_mavlink(self) -> bool:
        for conn in CONNECTION_CANDIDATES:
            candidate = None
            try:
                self.status.emit(f"Trying {conn} ...")
                candidate = mavutil.mavlink_connection(conn, autoreconnect=True)
                hb = candidate.recv_match(
                    type="HEARTBEAT",
                    blocking=True,
                    timeout=HEARTBEAT_TIMEOUT_SEC,
                )
                if hb:
                    self.master = candidate
                    self.status.emit(f"Connected: {conn}")
                    return True
            except Exception:
                pass
            finally:
                if candidate is not None and self.master is not candidate:
                    try:
                        candidate.close()
                    except Exception:
                        pass

        self.status.emit("MAVLink auto-connect failed.")
        return False

    def start(self) -> bool:
        if self.running:
            return True

        if not self.master and not self.fg and not self.auto_connect():
            return False

        self.running = True
        self.thread = threading.Thread(target=self.loop, name="MavWorker", daemon=True)
        self.thread.start()
        return True

    def stop(self) -> None:
        self.running = False
        if self.fg is not None:
            self.fg.stop()
            self.fg = None
        if self.thread and self.thread.is_alive() and threading.current_thread() is not self.thread:
            self.thread.join(timeout=1.0)

    def record_home_from_telemetry(self, telemetry: Dict[str, Any], source: str) -> Tuple[bool, Dict[str, Any]]:
        lat = telemetry.get("lat")
        lon = telemetry.get("lon")
        fix_type = telemetry.get("gps_fix_type")

        if lat is None or lon is None:
            return False, self._state_snapshot()

        if fix_type is not None and fix_type < 3:
            return False, self._state_snapshot()

        home_alt = telemetry.get("alt_msl")
        if home_alt is None:
            home_alt = telemetry.get("alt")

        with self.state_lock:
            self.state["home_lat"] = lat
            self.state["home_lon"] = lon
            self.state["home_alt"] = home_alt
            self.state["home_source"] = source
            snapshot = dict(self.state)

        return True, snapshot

    def loop(self) -> None:
        try:
            self.request_streams()

            while self.running:
                if self.pause_telemetry:
                    time.sleep(TELEMETRY_PAUSE_SLEEP_SEC)
                    continue

                if self.master is None:
                    time.sleep(IDLE_LOOP_SLEEP_SEC)
                    continue

                msg = self.master.recv_match(blocking=False)
                if msg is None:
                    time.sleep(IDLE_LOOP_SLEEP_SEC)
                    continue

                t = msg.get_type()

                if t == "HEARTBEAT":
                    armed_now = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                    with self.state_lock:
                        was_armed = self.state["armed"]
                        self.state["armed"] = armed_now
                        self._refresh_mode_lookup(msg)
                        self.state["mode"] = self.mode_name(msg.custom_mode)
                        # F2: tipe kendaraan dari MAV_TYPE -> dipublikasikan utk
                        # pemilihan profil di frontend (auto-select penuh = P2).
                        self.state["vehicle_type"] = _mav_type_family(msg.type)
                        snapshot = dict(self.state)

                    if armed_now and not was_armed:
                        self.record_home_from_telemetry(snapshot, "armed")

                elif t == "GLOBAL_POSITION_INT":
                    with self.state_lock:
                        # Saat pose_source == "fg", field pose milik FG stream
                        # (30 Hz); jangan ditimpa data 5 Hz yg lebih tua.
                        if self.pose_source != "fg":
                            self.state["lat"] = msg.lat / 1e7
                            self.state["lon"] = msg.lon / 1e7
                            self.state["alt_msl"] = msg.alt / 1000.0
                            self.state["heading"] = msg.hdg / 100.0 if msg.hdg != 65535 else None
                        self.state["alt"] = msg.relative_alt / 1000.0
                        self.state["groundspeed"] = math.sqrt((msg.vx / 100.0) ** 2 + (msg.vy / 100.0) ** 2)

                elif t == "ATTITUDE":
                    if self.pose_source != "fg":
                        with self.state_lock:
                            self.state["roll"] = math.degrees(msg.roll)
                            self.state["pitch"] = math.degrees(msg.pitch)
                            self.state["yaw"] = math.degrees(msg.yaw)

                elif t == "VFR_HUD":
                    with self.state_lock:
                        self.state["groundspeed"] = msg.groundspeed
                        self.state["airspeed"] = msg.airspeed
                        self.state["throttle"] = msg.throttle
                        if self.pose_source != "fg":
                            self.state["alt_msl"] = msg.alt
                            self.state["heading"] = msg.heading

                elif t == "SERVO_OUTPUT_RAW":
                    # Animasi control surface (PWM keluaran autopilot).
                    with self.state_lock:
                        self.state["srv1"] = msg.servo1_raw
                        self.state["srv2"] = msg.servo2_raw
                        self.state["srv3"] = msg.servo3_raw
                        self.state["srv4"] = msg.servo4_raw

                elif t == "SERVO_OUTPUT_RAW":
                    # Animasi control surface (PWM keluaran autopilot).
                    with self.state_lock:
                        self.state["srv1"] = msg.servo1_raw
                        self.state["srv2"] = msg.servo2_raw
                        self.state["srv3"] = msg.servo3_raw
                        self.state["srv4"] = msg.servo4_raw

                elif t == "GPS_RAW_INT":
                    with self.state_lock:
                        if self.pose_source != "fg":
                            self.state["lat"] = msg.lat / 1e7
                            self.state["lon"] = msg.lon / 1e7
                            self.state["alt_msl"] = msg.alt / 1000.0
                        self.state["satellites"] = msg.satellites_visible
                        self.state["gps_fix_type"] = msg.fix_type

                        should_seed_home = (
                            self.state["home_lat"] is None
                            or self.state["home_lon"] is None
                            or self.state["home_source"] in (None, "default", "mission")
                        )
                        snapshot = dict(self.state)

                    if msg.fix_type >= 3 and should_seed_home:
                        self.record_home_from_telemetry(snapshot, "gps")

                elif t == "SYS_STATUS":
                    with self.state_lock:
                        if msg.voltage_battery != 65535:
                            self.state["battery"] = msg.voltage_battery / 1000.0
                        # battery_remaining: 0-100, -1 = tidak tersedia.
                        rem = getattr(msg, "battery_remaining", -1)
                        if rem is not None and rem >= 0:
                            self.state["battery_pct"] = float(rem)

                elif t == "BATTERY_STATUS":
                    # Monitor ke-2 (id=1) = level BENSIN (ArduPilot fuel
                    # monitor via BATT2_*). id=0 = baterai avionik.
                    rem = getattr(msg, "battery_remaining", -1)
                    if rem is not None and rem >= 0:
                        with self.state_lock:
                            if getattr(msg, "id", 0) == 1:
                                self.state["fuel_pct"] = float(rem)
                            else:
                                self.state["battery_pct"] = float(rem)

                elif t == "HOME_POSITION":
                    altitude = getattr(msg, "altitude", getattr(msg, "alt", None))
                    with self.state_lock:
                        self.state["home_lat"] = msg.latitude / 1e7
                        self.state["home_lon"] = msg.longitude / 1e7
                        self.state["home_alt"] = altitude / 1000.0 if altitude is not None else None
                        self.state["home_source"] = "home_position"

                self._emit_state()

        except Exception as e:
            self.status.emit(f"Telemetry loop error: {e}")
        finally:
            self.running = False

    def request_streams(self) -> None:
        try:
            if not self.master:
                return

            self.master.mav.request_data_stream_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_ALL,
                TELEMETRY_STREAM_HZ,
                1,
            )
        except Exception:
            pass

    def _refresh_mode_lookup(self, heartbeat_msg) -> None:
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

    def mode_name(self, custom_mode) -> str:
        return self._mode_lookup.get(custom_mode, f"MODE_{custom_mode}")

    def arm(self, arm_state: bool) -> bool:
        if not self.master:
            self.status.emit("Not connected to a vehicle.")
            return False

        try:
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0,
                1 if arm_state else 0,
                0, 0, 0, 0, 0, 0,
            )
            self.status.emit("Arm command sent." if arm_state else "Disarm command sent.")
            return True
        except Exception as e:
            self.status.emit(f"Arm command failed: {e}")
            return False

    def rtl(self) -> bool:
        if not self.master:
            self.status.emit("Not connected to a vehicle.")
            return False

        try:
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
                0,
                0, 0, 0, 0, 0, 0, 0,
            )
            self.status.emit("RTL command sent.")
            return True
        except Exception as e:
            self.status.emit(f"RTL command failed: {e}")
            return False

    def download_mission(self) -> List[Dict[str, Any]]:
        if not self.master:
            self.status.emit("Not connected to a vehicle.")
            raise RuntimeError("Not connected to a vehicle")

        with self.mission_lock:
            self.pause_telemetry = True
            try:
                self.master.mav.mission_request_list_send(
                    self.master.target_system,
                    self.master.target_component,
                )

                count_msg = None
                for _ in range(MISSION_COUNT_RETRIES):
                    msg = self.master.recv_match(
                        type="MISSION_COUNT",
                        blocking=True,
                        timeout=MISSION_COUNT_WAIT_SEC,
                    )
                    if msg is not None:
                        count_msg = msg
                        break

                if count_msg is None:
                    raise RuntimeError("No MISSION_COUNT received")

                count = count_msg.count
                if count == 0:
                    mission = []
                    self.mission_received.emit(mission)
                    return mission

                items = {}

                for seq in range(count):
                    got_item = False

                    for _ in range(MISSION_ITEM_RETRIES):
                        self.master.mav.mission_request_send(
                            self.master.target_system,
                            self.master.target_component,
                            seq,
                        )

                        for _ in range(MISSION_ITEM_POLL_RETRIES):
                            msg = self.master.recv_match(
                                type=["MISSION_ITEM", "MISSION_ITEM_INT", "MISSION_ACK"],
                                blocking=True,
                                timeout=MISSION_ITEM_WAIT_SEC,
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

    def auto_mode(self) -> bool:
        if not self.master:
            self.status.emit("Not connected to a vehicle.")
            return False

        try:
            mode_mapping = self.master.mode_mapping()
            if mode_mapping is None or "AUTO" not in mode_mapping:
                raise RuntimeError("AUTO mode not supported by this vehicle")

            mode_id = mode_mapping["AUTO"]
            self.master.set_mode(mode_id)
            self.status.emit("AUTO mode requested.")
            return True
        except Exception as e:
            self.status.emit(f"Failed to set AUTO: {e}")
            return False