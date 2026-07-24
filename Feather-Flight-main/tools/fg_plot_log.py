#!/usr/bin/env python3
"""OMNI-Trainer diagnostik: rekam stream FGNetFDM lalu plot (permintaan lead).

Output 1 file PNG berisi 3 panel:
  1. Trajektori posisi dalam koordinat lokal XY (meter, ENU relatif fix pertama)
  2. Pitch & roll vs waktu (seluruh rekaman)
  3. Zoom pitch & roll pada window tersibuk — untuk melihat TEKSTUR osilasi:
     noise (acak, lantai konstan) vs dinamika/kontrol (periodik, ber-envelope)

Pakai:
    python3 -m tools.fg_plot_log --duration 60 --out /tmp/fg_diag.png

PENTING: jalankan TANPA aplikasi Feather-Flight (cukup SITL + MAVProxy),
karena tool ini bind langsung ke port 5503 — dua konsumen di port yang sama
akan berebut paket. Terbangkan via MAVProxy (wp load -> mode auto -> arm).

Dependensi: matplotlib (pip install matplotlib --break-system-packages).
"""
import argparse
import math
import socket
import time

from src.fg_link.fgnetfdm import FDMParseError, parse_fdm

M_PER_DEG_LAT = 111_320.0


def parse_args():
    p = argparse.ArgumentParser(description="Rekam & plot stream FGNetFDM")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=5503)
    p.add_argument("--duration", type=float, default=60.0,
                   help="lama rekaman, detik (default 60)")
    p.add_argument("--out", default="/tmp/fg_diag.png", help="path PNG output")
    p.add_argument("--csv", default=None,
                   help="opsional: simpan data mentah ke CSV utk analisis lanjut")
    p.add_argument("--zoom-window", type=float, default=2.0,
                   help="lebar window zoom panel 3, detik")
    return p.parse_args()


def record(args):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.host, args.port))
    sock.settimeout(1.0)

    rows = []  # (t, lat, lon, alt, agl, roll, pitch)
    t_start = None
    print(f"merekam udp:{args.port} selama {args.duration:.0f} dtk... "
          f"(terbangkan pesawat sekarang)", flush=True)

    deadline = time.monotonic() + args.duration
    while time.monotonic() < deadline:
        try:
            pkt, _ = sock.recvfrom(4096)
        except socket.timeout:
            continue
        try:
            f = parse_fdm(pkt)
        except FDMParseError:
            continue
        now = time.monotonic()
        if t_start is None:
            t_start = now
            print("frame pertama diterima, perekaman berjalan.", flush=True)
        rows.append((now - t_start, f.lat_deg, f.lon_deg, f.alt_m, f.agl_m,
                     f.roll_deg, f.pitch_deg))

    sock.close()
    if len(rows) < 100:
        raise SystemExit(f"hanya {len(rows)} frame terekam — stream FG hidup? "
                         f"(cek flag --fg/--enable-fgview & port)")
    print(f"terekam {len(rows)} frame "
          f"(~{len(rows) / rows[-1][0]:.0f} Hz)", flush=True)
    return rows


def to_local_xy(rows):
    """ENU meter relatif fix pertama (aproksimasi equirectangular — sah utk
    radius penerbangan training beberapa km)."""
    lat0, lon0 = rows[0][1], rows[0][2]
    m_per_deg_lon = M_PER_DEG_LAT * math.cos(math.radians(lat0))
    xs = [(r[2] - lon0) * m_per_deg_lon for r in rows]
    ys = [(r[1] - lat0) * M_PER_DEG_LAT for r in rows]
    return xs, ys


def busiest_window(ts, pitch, roll, width_s):
    """Cari window dgn aktivitas attitude terbesar (jumlah |delta|) utk zoom."""
    best_i, best_score, j = 0, -1.0, 0
    score = 0.0
    deltas = [abs(pitch[i] - pitch[i - 1]) + abs(roll[i] - roll[i - 1])
              for i in range(1, len(ts))]
    deltas.insert(0, 0.0)
    for i in range(len(ts)):
        score += deltas[i]
        while ts[i] - ts[j] > width_s:
            score -= deltas[j]
            j += 1
        if score > best_score:
            best_score, best_i = score, j
    t0 = ts[best_i]
    return t0, t0 + width_s


def make_plot(rows, args):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ts = [r[0] for r in rows]
    roll = [r[5] for r in rows]
    pitch = [r[6] for r in rows]
    xs, ys = to_local_xy(rows)

    fig, axes = plt.subplots(3, 1, figsize=(11, 13))
    fig.suptitle(f"FG stream diagnostik — {len(rows)} frame @ "
                 f"~{len(rows) / ts[-1]:.0f} Hz input", fontsize=13)

    ax = axes[0]
    ax.plot(xs, ys, linewidth=0.8)
    ax.plot(xs[0], ys[0], "go", label="start")
    ax.plot(xs[-1], ys[-1], "rs", label="end")
    ax.set_title("Posisi lokal XY (ENU, meter, relatif fix pertama)")
    ax.set_xlabel("X / Timur (m)")
    ax.set_ylabel("Y / Utara (m)")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, alpha=0.3)
    ax.legend()

    ax = axes[1]
    ax.plot(ts, pitch, linewidth=0.6, label="pitch")
    ax.plot(ts, roll, linewidth=0.6, label="roll", alpha=0.8)
    ax.set_title("Attitude vs waktu (seluruh rekaman)")
    ax.set_xlabel("t (s)")
    ax.set_ylabel("deg")
    ax.grid(True, alpha=0.3)
    ax.legend()

    t0, t1 = busiest_window(ts, pitch, roll, args.zoom_window)
    sel = [i for i, t in enumerate(ts) if t0 <= t <= t1]
    ax = axes[2]
    ax.plot([ts[i] for i in sel], [pitch[i] for i in sel],
            linewidth=0.9, marker=".", markersize=2, label="pitch")
    ax.plot([ts[i] for i in sel], [roll[i] for i in sel],
            linewidth=0.9, marker=".", markersize=2, label="roll", alpha=0.8)
    ax.set_title(f"Zoom window tersibuk ({t0:.1f}–{t1:.1f} s) — tekstur osilasi: "
                 f"periodik=dinamika/kontrol, acak=noise")
    ax.set_xlabel("t (s)")
    ax.set_ylabel("deg")
    ax.grid(True, alpha=0.3)
    ax.legend()

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(args.out, dpi=130)
    print(f"plot tersimpan: {args.out}", flush=True)


def maybe_csv(rows, path):
    if not path:
        return
    with open(path, "w") as fh:
        fh.write("t,lat,lon,alt_m,agl_m,roll_deg,pitch_deg\n")
        for r in rows:
            fh.write(",".join(f"{v:.7f}" for v in r) + "\n")
    print(f"csv tersimpan: {path}", flush=True)


def main():
    args = parse_args()
    rows = record(args)
    maybe_csv(rows, args.csv)
    make_plot(rows, args)


if __name__ == "__main__":
    main()