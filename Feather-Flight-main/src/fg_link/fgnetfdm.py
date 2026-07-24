"""Parser murni FGNetFDM v24 (stream native SITL/JSBSim -> FlightGear).

Modul ini TIDAK menyentuh socket, thread, atau print — hanya bytes -> frame.
Konsumen: tools/fg_stream_reader.py (diagnostik) dan src/fg_link/receiver.py
(Tahap B, feed ke mav_worker), serta interpolator Ver 2.

Layout offset mengikuti net_fdm.hxx v24, byte order BIG-ENDIAN (network),
konsisten dengan prior art scripts/fg_altitude_bridge.py di repo omnitrainer:

  offset  type  field
  0       >I    version        (harus 24)
  8       >d    longitude      (radian)
  16      >d    latitude       (radian)
  24      >d    altitude       (m, MSL)
  32      >f    agl            (m)
  36      >f    phi   / roll   (radian)
  40      >f    theta / pitch  (radian)
  44      >f    psi   / yaw    (radian)
  68      >f    vcas           (calibrated airspeed, knots)
  72      >f    climb_rate     (ft/s)
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass

FG_NET_FDM_VERSION = 24
MIN_PACKET_LEN = 76  # cukup sampai climb_rate

_FT_PER_S_TO_M_PER_S = 0.3048


class FDMParseError(ValueError):
    """Paket bukan FGNetFDM v24 yang valid."""


@dataclass(frozen=True)
class FDMFrame:
    """Satu frame pose/kecepatan, unit sudah dinormalisasi (derajat, meter, m/s)."""
    lat_deg: float
    lon_deg: float
    alt_m: float
    agl_m: float
    roll_deg: float
    pitch_deg: float
    yaw_deg: float
    vcas_kt: float
    climb_mps: float
    packet_len: int


def parse_fdm(pkt: bytes) -> FDMFrame:
    """Unpack paket FGNetFDM v24. Raise FDMParseError jika tidak valid.

    Deteksi byte order salah dilaporkan eksplisit di pesan error, karena itu
    mode gagal paling umum (lat/lon jadi angka absurd).
    """
    if len(pkt) < MIN_PACKET_LEN:
        raise FDMParseError(f"paket terlalu pendek: {len(pkt)} < {MIN_PACKET_LEN} bytes")

    (version,) = struct.unpack_from(">I", pkt, 0)
    if version != FG_NET_FDM_VERSION:
        (version_le,) = struct.unpack_from("<I", pkt, 0)
        hint = (" (valid sebagai LITTLE-endian — pengirim tidak memakai "
                "network order, cek konfigurasi sender)"
                if version_le == FG_NET_FDM_VERSION else "")
        raise FDMParseError(f"version={version}, bukan v24{hint}")

    lon_rad, lat_rad, alt_m = struct.unpack_from(">ddd", pkt, 8)
    agl_m, phi, theta, psi = struct.unpack_from(">ffff", pkt, 32)
    vcas_kt, climb_fps = struct.unpack_from(">ff", pkt, 68)

    return FDMFrame(
        lat_deg=math.degrees(lat_rad),
        lon_deg=math.degrees(lon_rad),
        alt_m=alt_m,
        agl_m=agl_m,
        roll_deg=math.degrees(phi),
        pitch_deg=math.degrees(theta),
        yaw_deg=math.degrees(psi),
        vcas_kt=vcas_kt,
        climb_mps=climb_fps * _FT_PER_S_TO_M_PER_S,
        packet_len=len(pkt),
    )