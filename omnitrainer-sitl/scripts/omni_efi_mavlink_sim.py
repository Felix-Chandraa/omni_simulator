#!/usr/bin/env python3

import argparse
import time

from pymavlink import mavutil


PWM_MIN = 1000
PWM_MAX = 2000

AMBIENT_C = 36.0
IDLE_CHT_C = 128.0
CRUISE_CHT_C = 146.0
MAX_CHT_C = 170.0

INVALID_EGT_C = -273.15
IDLE_EGT_C = 180.0
CRUISE_EGT_C = 510.0
MAX_EGT_C = 620.0

DEFAULT_SEND_RATE_HZ = 3.0
DEFAULT_PRINT_RATE_HZ = 1.0
DEFAULT_RNG_SEND_RATE_HZ = 10.0
DEFAULT_RNG_INJECT_ABOVE_M = 100000.0
DEFAULT_RNG_MAX_CM = 4500
DEFAULT_RNG_MIN_CM = 30

TPS_TO_RPM = [
    (0.0, 0.0),
    (3.0, 1700.0),
    (5.0, 1900.0),
    (8.0, 2050.0),
    (12.0, 3000.0),
    (17.0, 4000.0),
    (20.0, 4600.0),
    (24.0, 5200.0),
    (29.0, 5620.0),
    (38.0, 6160.0),
    (49.0, 6425.0),
    (60.0, 6800.0),
    (71.0, 7055.0),
    (80.0, 7150.0),
    (97.0, 7120.0),
    (100.0, 7200.0),
]

TPS_TO_INJT_MS = [
    (0.0, 0.0),
    (3.0, 29.6),
    (8.0, 30.7),
    (13.0, 28.3),
    (20.0, 27.1),
    (24.0, 28.4),
    (29.0, 32.3),
    (38.0, 40.4),
    (49.0, 51.4),
    (71.0, 65.9),
    (97.0, 72.7),
    (100.0, 73.0),
]


def clamp(value, low, high):
    return max(low, min(high, value))


def interp_table(x, table):
    if x <= table[0][0]:
        return table[0][1]
    for index in range(1, len(table)):
        x0, y0 = table[index - 1]
        x1, y1 = table[index]
        if x <= x1:
            ratio = (x - x0) / (x1 - x0)
            return y0 + ratio * (y1 - y0)
    return table[-1][1]


def pwm_to_throttle_pct(pwm):
    if pwm is None or pwm <= 0:
        return 0.0
    pct = (float(pwm) - PWM_MIN) * 100.0 / float(PWM_MAX - PWM_MIN)
    return clamp(pct, 0.0, 100.0)


def send_heartbeat(link):
    link.mav.heartbeat_send(
        mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
        mavutil.mavlink.MAV_AUTOPILOT_INVALID,
        0,
        0,
        mavutil.mavlink.MAV_STATE_ACTIVE,
    )


def send_efi_status(
    link,
    rpm,
    fuel_used_cm3,
    fuel_flow_cm3_min,
    engine_load_pct,
    throttle_pct,
    cht_c,
    egt_c,
    injection_time_ms,
    running,
):
    link.mav.efi_status_send(
        1 if running else 0,
        0,
        float(rpm),
        float(fuel_used_cm3),
        float(fuel_flow_cm3_min),
        float(engine_load_pct),
        float(throttle_pct),
        0.0,
        97.0,
        96.0,
        52.0,
        float(cht_c),
        0.0,
        float(injection_time_ms),
        float(egt_c),
        float(throttle_pct),
        0.0,
    )


def get_good_rangefinder_distance_m(state):
    now = time.time()
    terrain_height_m = state.get("terrain_height_m")
    last_terrain_time = state.get("last_terrain_time", 0.0)
    if terrain_height_m is not None and (now - last_terrain_time) < 2.0:
        return max(0.3, float(terrain_height_m))
    return max(0.3, float(state.get("rel_alt_m", 0.0)))


def send_test_rangefinder(link, state, min_cm, max_cm, sensor_id):
    good_dist_m = get_good_rangefinder_distance_m(state)
    dist_cm = int(clamp(good_dist_m * 100.0, min_cm, max_cm))
    link.mav.distance_sensor_send(
        int(time.time() * 1000) & 0xFFFFFFFF,
        int(min_cm),
        int(max_cm),
        int(dist_cm),
        mavutil.mavlink.MAV_DISTANCE_SENSOR_LASER,
        int(sensor_id),
        mavutil.mavlink.MAV_SENSOR_ROTATION_PITCH_270,
        0,
    )
    return "GOOD", dist_cm / 100.0


def send_to_links(links, send_fn, *args):
    for link in links:
        try:
            send_fn(link, *args)
        except Exception as exc:
            print("MAVLink send failed on %s: %s" % (getattr(link, "address", "link"), exc), flush=True)


def read_mavlink_messages(mav, state):
    while True:
        msg = mav.recv_match(blocking=False)
        if msg is None:
            return

        msg_type = msg.get_type()
        if msg_type == "BAD_DATA":
            continue
        if msg_type == "HEARTBEAT":
            base_mode = getattr(msg, "base_mode", 0)
            state["armed"] = bool(base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
        elif msg_type == "SERVO_OUTPUT_RAW":
            pwm = getattr(msg, "servo3_raw", 0)
            if pwm and pwm > 0:
                state["servo3_pwm"] = int(pwm)
                state["last_servo_time"] = time.time()
        elif msg_type in ("RC_CHANNELS", "RC_CHANNELS_RAW"):
            pwm = getattr(msg, "chan3_raw", 0)
            if pwm and pwm > 0:
                state["rc3_pwm"] = int(pwm)
                state["last_rc_time"] = time.time()
        elif msg_type == "GLOBAL_POSITION_INT":
            rel_alt_mm = getattr(msg, "relative_alt", None)
            if rel_alt_mm is not None:
                state["rel_alt_m"] = float(rel_alt_mm) / 1000.0
                state["last_alt_time"] = time.time()
                state["alt_source"] = "GPI"
        elif msg_type == "TERRAIN_REPORT":
            current_height = getattr(msg, "current_height", None)
            if current_height is not None:
                state["terrain_height_m"] = float(current_height)
                state["last_terrain_time"] = time.time()
        elif msg_type == "VFR_HUD":
            alt = getattr(msg, "alt", None)
            if alt is not None and (time.time() - state.get("last_alt_time", 0.0)) > 2.0:
                state["rel_alt_m"] = float(alt)
                state["last_alt_time"] = time.time()
                state["alt_source"] = "VFR"
        elif msg_type == "STATUSTEXT":
            text = getattr(msg, "text", "") or ""
            if "Engine running" in text:
                state["engine_running_text"] = True
            elif "Engine stopped" in text:
                state["engine_running_text"] = False


def choose_throttle_pwm(state):
    now = time.time()
    servo_age = now - state["last_servo_time"]
    rc_age = now - state["last_rc_time"]
    if servo_age < 2.0 and state["servo3_pwm"] > 0:
        return state["servo3_pwm"], "SERVO3"
    if rc_age < 2.0 and state["rc3_pwm"] > 0:
        return state["rc3_pwm"], "RC3"
    if state["servo3_pwm"] > 0:
        return state["servo3_pwm"], "SERVO3_OLD"
    if state["rc3_pwm"] > 0:
        return state["rc3_pwm"], "RC3_OLD"
    return 1000, "DEFAULT"


def build_parser():
    parser = argparse.ArgumentParser(
        description="Omni-Trainer DLE30 EFI telemetry sender with rangefinder SITL test injector"
    )
    parser.add_argument("--connect", default="tcp:127.0.0.1:5762", help="MAVLink connection string")
    parser.add_argument("--rate", type=float, default=DEFAULT_SEND_RATE_HZ, help="EFI_STATUS send rate in Hz")
    parser.add_argument("--print-rate", type=float, default=DEFAULT_PRINT_RATE_HZ, help="Console print rate in Hz")
    parser.add_argument("--idle-throttle", type=float, default=5.0, help="Minimum simulated throttle percent when running")
    parser.add_argument("--force-running", action="store_true", help="Force simulated EFI engine running")
    parser.add_argument("--simulate-egt", action="store_true", help="Send synthetic EGT")
    parser.add_argument("--simulate-fuel-flow", action="store_true", help="Send synthetic fuel flow")
    parser.add_argument("--rng-inject", action="store_true", help="Enable DISTANCE_SENSOR rangefinder injection")
    parser.add_argument("--rng-rate", type=float, default=DEFAULT_RNG_SEND_RATE_HZ, help="Rangefinder send rate in Hz")
    parser.add_argument("--rng-above", type=float, default=DEFAULT_RNG_INJECT_ABOVE_M, help="Compatibility option")
    parser.add_argument("--rng-min-cm", type=int, default=DEFAULT_RNG_MIN_CM, help="DISTANCE_SENSOR min distance in cm")
    parser.add_argument("--rng-max-cm", type=int, default=DEFAULT_RNG_MAX_CM, help="DISTANCE_SENSOR max distance in cm")
    parser.add_argument("--rng-id", type=int, default=0, help="DISTANCE_SENSOR sensor id")
    parser.add_argument(
        "--gcs-out",
        default="udpout:127.0.0.1:14550",
        help="Optional direct MAVLink mirror to QGroundControl, for example udpout:127.0.0.1:14550. Use empty string to disable.",
    )
    parser.add_argument("--source-system", type=int, default=1, help="MAVLink source system id")
    parser.add_argument("--source-component", type=int, default=191, help="MAVLink source component id")
    return parser


def main():
    args = build_parser().parse_args()
    mav = mavutil.mavlink_connection(
        args.connect,
        source_system=args.source_system,
        source_component=args.source_component,
        autoreconnect=True,
    )
    output_links = [mav]
    if args.gcs_out:
        output_links.append(
            mavutil.mavlink_connection(
                args.gcs_out,
                source_system=args.source_system,
                source_component=args.source_component,
                autoreconnect=True,
            )
        )
    print("Connected EFI simulator on %s" % args.connect, flush=True)
    if args.gcs_out:
        print("Mirroring EFI telemetry to %s for QGC visibility" % args.gcs_out, flush=True)
    if args.rng_inject:
        print(
            "Rangefinder injection ENABLED: healthy readings, rate %.1f Hz, min %d cm, max %d cm"
            % (args.rng_rate, args.rng_min_cm, args.rng_max_cm),
            flush=True,
        )
    else:
        print("Rangefinder injection DISABLED. Use --rng-inject to enable it.", flush=True)

    state = {
        "armed": False,
        "engine_running_text": False,
        "servo3_pwm": 1000,
        "rc3_pwm": 1000,
        "last_servo_time": 0.0,
        "last_rc_time": 0.0,
        "rel_alt_m": 0.0,
        "terrain_height_m": None,
        "last_alt_time": 0.0,
        "last_terrain_time": 0.0,
        "alt_source": "NONE",
    }

    rpm = 0.0
    cht_c = AMBIENT_C
    egt_c = INVALID_EGT_C
    fuel_used_cm3 = 0.0
    injection_time_ms = 0.0
    send_period = 1.0 / max(args.rate, 0.5)
    print_period = 1.0 / max(args.print_rate, 0.2)
    rng_send_period = 1.0 / max(args.rng_rate, 1.0)
    last_loop = time.time()
    last_send = 0.0
    last_print = 0.0
    last_heartbeat = 0.0
    last_rng_send = 0.0
    last_rng_mode = "OFF"
    last_rng_value_m = None

    while True:
        now = time.time()
        dt = now - last_loop
        last_loop = now
        if dt <= 0.0 or dt > 1.0:
            dt = send_period

        read_mavlink_messages(mav, state)
        if now - last_heartbeat >= 1.0:
            send_to_links(output_links, send_heartbeat)
            last_heartbeat = now
        if args.rng_inject and (now - last_rng_send >= rng_send_period):
            last_rng_send = now
            last_rng_mode, last_rng_value_m = "GOOD", get_good_rangefinder_distance_m(state)
            send_to_links(output_links, send_test_rangefinder, state, args.rng_min_cm, args.rng_max_cm, args.rng_id)
        if now - last_send < send_period:
            time.sleep(0.01)
            continue
        last_send = now

        throttle_pwm, throttle_source = choose_throttle_pwm(state)
        throttle_pct = pwm_to_throttle_pct(throttle_pwm)
        running = (
            args.force_running
            or state["armed"]
            or state["engine_running_text"]
            or throttle_pct > args.idle_throttle
        )
        if running and throttle_pct < args.idle_throttle:
            throttle_pct = args.idle_throttle
        throttle_norm = clamp(throttle_pct / 100.0, 0.0, 1.0)

        if running:
            target_rpm = interp_table(throttle_pct, TPS_TO_RPM)
            if state["armed"]:
                target_rpm = max(target_rpm, 1800.0)
            target_injt = interp_table(throttle_pct, TPS_TO_INJT_MS)
            rpm += (target_rpm - rpm) * clamp(dt * (12.0 if target_rpm >= rpm else 7.0), 0.0, 1.0)
            if rpm < 900.0 and throttle_pct > 3.0:
                rpm = 1200.0
            injection_time_ms += (target_injt - injection_time_ms) * clamp(dt * 8.0, 0.0, 1.0)
            if throttle_pct < 12.0:
                cht_target = IDLE_CHT_C
            elif throttle_pct < 35.0:
                cht_target = CRUISE_CHT_C
            else:
                cht_target = CRUISE_CHT_C + (MAX_CHT_C - CRUISE_CHT_C) * clamp((throttle_pct - 35.0) / 65.0, 0.0, 1.0)
            cht_c += (cht_target - cht_c) * clamp(dt * 0.045, 0.0, 1.0)
            if args.simulate_egt:
                if throttle_pct < 10.0:
                    egt_target = IDLE_EGT_C
                elif throttle_pct < 35.0:
                    egt_target = CRUISE_EGT_C
                else:
                    egt_target = CRUISE_EGT_C + (MAX_EGT_C - CRUISE_EGT_C) * clamp((throttle_pct - 35.0) / 65.0, 0.0, 1.0)
                if egt_c < -100.0:
                    egt_c = AMBIENT_C
                egt_c += (egt_target - egt_c) * clamp(dt * 0.12, 0.0, 1.0)
            else:
                egt_c = INVALID_EGT_C
            engine_load_pct = clamp(8.0 + throttle_pct * 0.92, 0.0, 100.0)
            if args.simulate_fuel_flow:
                fuel_flow_cm3_min = 20.0 + throttle_norm * 330.0
                fuel_used_cm3 += fuel_flow_cm3_min * dt / 60.0
            else:
                fuel_flow_cm3_min = 0.0
                fuel_used_cm3 = 0.0
        else:
            rpm += (0.0 - rpm) * clamp(dt * 2.5, 0.0, 1.0)
            if rpm < 30.0:
                rpm = 0.0
            injection_time_ms += (0.0 - injection_time_ms) * clamp(dt * 4.0, 0.0, 1.0)
            cht_c += (AMBIENT_C - cht_c) * clamp(dt * 0.025, 0.0, 1.0)
            egt_c = AMBIENT_C if args.simulate_egt else INVALID_EGT_C
            engine_load_pct = 0.0
            fuel_flow_cm3_min = 0.0

        send_to_links(
            output_links,
            send_efi_status,
            rpm,
            fuel_used_cm3,
            fuel_flow_cm3_min,
            engine_load_pct,
            throttle_pct,
            cht_c,
            egt_c,
            injection_time_ms,
            running,
        )

        if now - last_print >= print_period:
            last_print = now
            if not args.rng_inject:
                rng_txt = "DISABLED"
            elif last_rng_value_m is None:
                rng_txt = "WAIT"
            else:
                rng_txt = "%s %.1fm" % (last_rng_mode, last_rng_value_m)
            terrain_txt = "NA"
            if state.get("terrain_height_m") is not None:
                terrain_txt = "%.1f" % state["terrain_height_m"]
            print(
                "EFI armed=%d running=%d src=%s pwm=%4d thr=%5.1f rpm=%6.0f inj=%5.1f cht=%6.1f egt=%7.1f fuel=%7.1f flow=%6.1f relalt=%7.1f terrain=%s altSrc=%s rng=%s"
                % (
                    1 if state["armed"] else 0,
                    1 if running else 0,
                    throttle_source,
                    throttle_pwm,
                    throttle_pct,
                    rpm,
                    injection_time_ms,
                    cht_c,
                    egt_c,
                    fuel_used_cm3,
                    fuel_flow_cm3_min,
                    state.get("rel_alt_m", 0.0),
                    terrain_txt,
                    state.get("alt_source", "NONE"),
                    rng_txt,
                ),
                flush=True,
            )


if __name__ == "__main__":
    main()
