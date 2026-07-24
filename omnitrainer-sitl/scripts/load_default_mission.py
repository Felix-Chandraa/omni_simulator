#!/usr/bin/env python3
"""Loader misi default Omni-Trainer (idempoten).

Menunggu heartbeat SITL, lalu meng-upload misi default HANYA bila autopilot
belum punya misi (count <= 1, yaitu cuma home). Dipanggil otomatis oleh
run_demo.sh di latar belakang; aman dipanggil manual kapan pun.

Pakai port 14551 (output kedua MAVProxy) agar tidak bentrok dengan
Feather Flight yang memakai 14550.
"""
import argparse, sys, time
from pymavlink import mavutil, mavwp

def log(msg):
    print(f"[mission-loader] {msg}", flush=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mission", required=True)
    ap.add_argument("--conn", default="")
    ap.add_argument("--timeout", type=int, default=120)
    a = ap.parse_args()

    # Kandidat koneksi, dicoba berurutan. TCP 5762 = port serial langsung SITL
    # (paling andal, tidak bergantung MAVProxy); UDP 14551 = output MAVProxy.
    candidates = [a.conn] if a.conn else ["tcp:127.0.0.1:5762", "udp:127.0.0.1:14551"]
    m = None
    deadline_conn = time.time() + a.timeout
    while m is None and time.time() < deadline_conn:
        for c in candidates:
            log(f"coba {c}...")
            try:
                cand = mavutil.mavlink_connection(c)
                if cand.wait_heartbeat(timeout=15) is not None:
                    m = cand
                    log(f"heartbeat OK via {c}")
                    break
                cand.close()
            except Exception as e:
                log(f"  gagal: {e}")
        if m is None:
            time.sleep(3)
    if m is None:
        log("GAGAL: tidak ada heartbeat di semua kandidat"); return 1

    # Cek misi yang sudah ada — jangan timpa misi pengguna
    m.mav.mission_request_list_send(m.target_system, m.target_component)
    msg = m.recv_match(type="MISSION_COUNT", blocking=True, timeout=10)
    if msg is not None and msg.count > 1:
        log(f"misi sudah ada ({msg.count} item) — tidak menimpa. Selesai.")
        return 0

    wp = mavwp.MAVWPLoader()
    n = wp.load(a.mission)
    log(f"upload {n} item dari {a.mission}...")
    m.mav.mission_clear_all_send(m.target_system, m.target_component)
    m.recv_match(type="MISSION_ACK", blocking=True, timeout=5)
    m.mav.mission_count_send(m.target_system, m.target_component, n)

    deadline = time.time() + 60
    sent = set()
    while time.time() < deadline:
        msg = m.recv_match(type=["MISSION_REQUEST", "MISSION_REQUEST_INT", "MISSION_ACK"],
                           blocking=True, timeout=10)
        if msg is None:
            log("GAGAL: timeout menunggu request item"); return 1
        t = msg.get_type()
        if t == "MISSION_ACK":
            if msg.type == 0:
                log("SUKSES: misi terpasang. Cek dgn 'wp list' / fetch di Feather Flight.")
                return 0
            log(f"GAGAL: MISSION_ACK type={msg.type}"); return 1
        seq = msg.seq
        item = wp.wp(seq)
        # mavwp memuat item dgn target 0/0; set eksplisit agar autopilot
        # tidak mengabaikannya pada beberapa versi firmware.
        item.target_system = m.target_system
        item.target_component = m.target_component
        m.mav.send(item)
        if seq not in sent:
            sent.add(seq); log(f"  item {seq}/{n-1} terkirim")
    log("GAGAL: batas waktu upload"); return 1

if __name__ == "__main__":
    sys.exit(main())
