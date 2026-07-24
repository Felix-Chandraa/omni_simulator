from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

PORT = 8000
MAP_FILENAME = "map.html"
MAP_URL = f"http://127.0.0.1:{PORT}/{MAP_FILENAME}"

CONNECTION_CANDIDATES = [
    "udp:127.0.0.1:14550",
    "/dev/ttyACM0",
    "/dev/ttyUSB0",
    "COM3",
    "COM4",
]

HEARTBEAT_TIMEOUT_SEC = 5

TELEMETRY_STREAM_HZ = 5
IDLE_LOOP_SLEEP_SEC = 0.01
TELEMETRY_PAUSE_SLEEP_SEC = 0.05

MISSION_COUNT_RETRIES = 50
MISSION_COUNT_WAIT_SEC = 0.2
MISSION_ITEM_RETRIES = 5
MISSION_ITEM_POLL_RETRIES = 20
MISSION_ITEM_WAIT_SEC = 0.2

DRAWABLE_MISSION_COMMANDS = {16, 22}

# --- OMNI-Trainer: FlightGear native stream (Ver 0) ---
FG_STREAM_PORT = 5503
FG_PUBLISH_HZ = 30                 # rate publish pose ke frontend (input bisa >1000 Hz)
FG_FIRST_FRAME_TIMEOUT_SEC = 2.0   # probe: tunggu frame v24 valid pertama
TELEMETRY_SOURCE = "auto"          # "auto" | "mavlink" | "fg"
FG_FIELD_ELEV_MSL = None
TELEMETRY_BUS_HOST = "127.0.0.1"
TELEMETRY_BUS_PORT = 8765