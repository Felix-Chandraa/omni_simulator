#!/usr/bin/env python3

import argparse
import time

from pymavlink import mavutil


def clamp(value, low, high):
    return max(low, min(high, value))


def read_state_messages(mav, state):
    while True:
        msg = mav.recv_match(blocking=False)
        if msg is None:
            return

        msg_type = msg.get_type()
        if msg_type == "BAD_DATA":
            continue
        if msg_type == "GLOBAL_POSITION_INT":
            rel_alt_mm = getattr(msg, "relative_alt", None)
            if rel_alt_mm is not None:
                state["rel_alt_m"] = max(0.0, float(rel_alt_mm) / 1000.0)
                state["last_alt_time"] = time.time()
                state["alt_source"] = "GLOBAL_POSITION_INT"
        elif msg_type == "TERRAIN_REPORT":
            current_height = getattr(msg, "current_height", None)
            if current_height is not None:
                state["terrain_height_m"] = max(0.0, float(current_height))
                state["last_terrain_time"] = time.time()
                state["alt_source"] = "TERRAIN_REPORT"
        elif msg_type == "VFR_HUD":
            alt = getattr(msg, "alt", None)
            if alt is not None and (time.time() - state.get("last_alt_time", 0.0)) > 2.0:
                state["rel_alt_m"] = max(0.0, float(alt))
                state["last_alt_time"] = time.time()
                state["alt_source"] = "VFR_HUD"


def terrain_distance_m(state):
    now = time.time()
    if state.get("terrain_height_m") is not None and (now - state.get("last_terrain_time", 0.0)) < 2.0:
        return max(0.3, float(state["terrain_height_m"]))
    return max(0.3, float(state.get("rel_alt_m", 0.0)))


def send_heartbeat(link):
    link.mav.heartbeat_send(
        mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
        mavutil.mavlink.MAV_AUTOPILOT_INVALID,
        0,
        0,
        mavutil.mavlink.MAV_STATE_ACTIVE,
    )


def send_distance_sensor(link, distance_m, min_cm, max_cm, sensor_id):
    dist_cm = int(clamp(distance_m * 100.0, min_cm, max_cm))
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


def send_to_links(links, send_fn, *args):
    for link in links:
        try:
            send_fn(link, *args)
        except Exception as exc:
            print("MAVLink send failed on %s: %s" % (getattr(link, "address", "link"), exc), flush=True)


def build_parser():
    parser = argparse.ArgumentParser(description="Omni-Trainer MAVLink rangefinder terrain-distance injector")
    parser.add_argument("--connect", default="tcp:127.0.0.1:5762", help="MAVLink connection string to SITL")
    parser.add_argument("--rate", type=float, default=10.0, help="DISTANCE_SENSOR send rate in Hz")
    parser.add_argument("--print-rate", type=float, default=2.0, help="Console print rate in Hz")
    parser.add_argument("--min-cm", type=int, default=30, help="Rangefinder minimum distance in cm")
    parser.add_argument("--max-cm", type=int, default=4500, help="Rangefinder maximum distance in cm")
    parser.add_argument("--sensor-id", type=int, default=0, help="DISTANCE_SENSOR sensor id")
    parser.add_argument(
        "--gcs-out",
        default="udpout:127.0.0.1:14550",
        help="Optional direct MAVLink mirror to QGroundControl. Use empty string to disable.",
    )
    parser.add_argument("--source-system", type=int, default=1, help="MAVLink source system id")
    parser.add_argument("--source-component", type=int, default=192, help="MAVLink source component id")
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

    print("Connected rangefinder injector on %s" % args.connect, flush=True)
    if args.gcs_out:
        print("Mirroring DISTANCE_SENSOR to %s for QGC visibility" % args.gcs_out, flush=True)

    state = {
        "rel_alt_m": 0.0,
        "terrain_height_m": None,
        "last_alt_time": 0.0,
        "last_terrain_time": 0.0,
        "alt_source": "NONE",
    }
    send_period = 1.0 / max(args.rate, 1.0)
    print_period = 1.0 / max(args.print_rate, 0.2)
    last_send = 0.0
    last_print = 0.0
    last_heartbeat = 0.0

    while True:
        now = time.time()
        read_state_messages(mav, state)

        if now - last_heartbeat >= 1.0:
            send_to_links(output_links, send_heartbeat)
            last_heartbeat = now

        if now - last_send >= send_period:
            distance_m = terrain_distance_m(state)
            send_to_links(output_links, send_distance_sensor, distance_m, args.min_cm, args.max_cm, args.sensor_id)
            last_send = now

        if now - last_print >= print_period:
            terrain_txt = "NA"
            if state.get("terrain_height_m") is not None:
                terrain_txt = "%.1f" % state["terrain_height_m"]
            print(
                "RNG dist=%6.2fm relalt=%7.1f terrain=%s source=%s"
                % (terrain_distance_m(state), state.get("rel_alt_m", 0.0), terrain_txt, state.get("alt_source", "NONE")),
                flush=True,
            )
            last_print = now

        time.sleep(0.01)


if __name__ == "__main__":
    main()
