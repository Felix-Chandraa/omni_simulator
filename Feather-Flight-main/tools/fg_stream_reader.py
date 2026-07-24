#!/usr/bin/env python3
"""OMNI-Trainer Tahap A — diagnostik stream native SITL (FGNetFDM v24).

Alat validasi, BUKAN production path. Jalankan dari root repo:

    python3 -m tools.fg_stream_reader [--port 5503]

Fungsi: bind UDP, parse via src.fg_link.fgnetfdm, print pose + airspeed,
ukur rate aktual (Hz per window), validasi silang lat/lon vs lokasi spawn.
"""
import argparse
import socket
import time

from src.fg_link.fgnetfdm import FDMParseError, parse_fdm
from src.fg_link.altitude import GroundDatum

# Spawn default sim_vehicle.py = CMAC, Canberra
DEFAULT_SPAWN_LAT = -35.363261
DEFAULT_SPAWN_LON = 149.165230
SPAWN_TOLERANCE_DEG = 0.05  # ~5.5 km; longgar utk taxi/terbang awal

# Analisis kontinuitas: pada input ~1200 Hz, tumbling ekstrem 400 deg/s pun
# hanya ~0.33 deg/frame. Delta antar-frame di atas ambang ini secara fisika
# mustahil -> indikasi masalah data (korupsi/urutan), bukan aerodinamika.
JUMP_THRESHOLD_DEG_PER_FRAME = 15.0


def wrapped_delta_deg(a, b):
    """Selisih sudut terpendek a-b, hasil di (-180, 180]. Aman utk flip 180."""
    return ((a - b + 180.0) % 360.0) - 180.0


def parse_args():
    p = argparse.ArgumentParser(description="OMNI FGNetFDM v24 stream reader (diagnostik)")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=5503)
    p.add_argument("--print-interval", type=float, default=1.0,
                   help="detik antar print ringkasan (Hz diukur per interval)")
    p.add_argument("--spawn-lat", type=float, default=DEFAULT_SPAWN_LAT)
    p.add_argument("--spawn-lon", type=float, default=DEFAULT_SPAWN_LON)
    p.add_argument("--field-elev", type=float, default=None,
                   help="elevasi datum tanah MSL (default: auto dari frame parkir "
                        "pertama). agl_field = alt_msl - datum.")
    return p.parse_args()


def check_spawn(frame, args, sender):
    dlat = abs(frame.lat_deg - args.spawn_lat)
    dlon = abs(frame.lon_deg - args.spawn_lon)
    ok = dlat < SPAWN_TOLERANCE_DEG and dlon < SPAWN_TOLERANCE_DEG
    status = "OK" if ok else "MISMATCH — cek byte order/offset/lokasi spawn!"
    print(f"[SPAWN CHECK] first fix ({frame.lat_deg:.6f}, {frame.lon_deg:.6f}) "
          f"vs ref ({args.spawn_lat}, {args.spawn_lon}) "
          f"d=({dlat:.5f}, {dlon:.5f}) deg -> {status}", flush=True)
    print(f"[INFO] sender={sender} packet_len={frame.packet_len} bytes", flush=True)


def main():
    args = parse_args()
    ground = GroundDatum(override_msl=args.field_elev)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.host, args.port))
    print(f"listen udp {args.host}:{args.port} | spawn ref "
          f"({args.spawn_lat}, {args.spawn_lon})", flush=True)

    n_window = 0
    n_total = 0
    n_bad = 0
    t_window = time.monotonic()
    spawn_checked = False

    # Analisis kontinuitas per-frame INPUT (bukan per-print)
    prev = None
    d_pitch_max = 0.0
    d_roll_max = 0.0
    jumps = 0

    while True:
        pkt, addr = sock.recvfrom(4096)
        n_total += 1
        try:
            frame = parse_fdm(pkt)
        except FDMParseError as e:
            n_bad += 1
            if n_bad <= 5 or n_bad % 100 == 0:
                print(f"[WARN] paket #{n_total}: {e}", flush=True)
            continue
        n_window += 1

        if prev is not None:
            dp = abs(wrapped_delta_deg(frame.pitch_deg, prev.pitch_deg))
            dr = abs(wrapped_delta_deg(frame.roll_deg, prev.roll_deg))
            d_pitch_max = max(d_pitch_max, dp)
            d_roll_max = max(d_roll_max, dr)
            if dp > JUMP_THRESHOLD_DEG_PER_FRAME or dr > JUMP_THRESHOLD_DEG_PER_FRAME:
                jumps += 1
                print(f"[JUMP] frame#{n_total}: dPitch={dp:.1f} dRoll={dr:.1f} "
                      f"deg/frame — TIDAK FISIS, indikasi masalah data", flush=True)
        prev = frame

        if not spawn_checked:
            spawn_checked = True
            check_spawn(frame, args, addr)

        now = time.monotonic()
        dt = now - t_window
        if dt >= args.print_interval:
            hz = n_window / dt
            agl_field = ground.agl_from(frame.alt_m)
            print(f"{hz:6.1f} Hz | lat={frame.lat_deg:.6f} lon={frame.lon_deg:.6f} "
                  f"alt={frame.alt_m:7.2f}m agl={agl_field:6.2f}m "
                  f"(raw={frame.agl_m:7.2f}m datum={ground.ground_ref_msl:.2f}m) | "
                  f"r/p/y=({frame.roll_deg:6.1f},{frame.pitch_deg:6.1f},{frame.yaw_deg:6.1f})deg | "
                  f"vcas={frame.vcas_kt:5.1f}kt climb={frame.climb_mps:+5.2f}m/s | "
                  f"dMax r/p=({d_roll_max:.2f},{d_pitch_max:.2f})deg/frame jumps={jumps} | "
                  f"total={n_total} bad={n_bad}")
            n_window = 0
            t_window = now
            d_pitch_max = 0.0
            d_roll_max = 0.0


if __name__ == "__main__":
    main()