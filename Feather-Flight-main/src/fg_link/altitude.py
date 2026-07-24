"""Derivasi AGL "murni" (height-above-field) dari MSL stream FG.

LATAR (G0 / hutang validasi "float + tail-cam pegas"):
  Pada mode JSBSim (frame `jsbsim:*`), paket FGNetFDM v24 diproduksi oleh
  PROSES JSBSim (lihat SDD A.3 / 6.1), bukan SITL_State. Kolom `agl` diisi
  JSBSim dari GetDistanceAGL() = AltitudeASL - TerrainElevation. Di bawah
  ArduPilot SITL, JSBSim TIDAK punya model terrain -> ground = 0 m MSL
  (bumi datar setinggi laut). Akibatnya `agl == AltitudeASL == alt_msl`.
  Data lapangan M1 (parkir CMAC): alt=584.09 m, agl=584.09 m (identik).

  Frontend `core/aircraft.js` SUDAH benar menurut Invarian 2.3:
      visualHeight = terrainH(Cesium) + AGL(FG) + clearance
  sehingga agl=584 + terrain~584 -> pesawat melayang ~584 m -> "pegas".
  Perbaikan yang benar: buat AGL(FG) benar-benar AGL sebelum dikonsumsi.

DEFINISI (Invarian 2.3 — tetap satu sumber, tanpa MAVLink saat pose_source=fg):
      agl_field = max(alt_msl(FG) - ground_ref_msl, 0)
  `ground_ref_msl` = elevasi tanah lokasi spawn (m MSL). Ini DIAMBIL MURNI
  dari kanal FG (frame parkir pertama) atau dari konstanta lokasi di config.
  TIDAK memakai HOME_POSITION MAVLink -> tidak melanggar guard
  "MAVLink DILARANG menulis pose saat pose_source=fg" dan tidak menyatukan
  "altitude UI" (relative-to-home P1) dengan "tinggi render" (kosmetik kontak
  tanah). Derivasi dari alt_msl (bukan dari kolom agl mentah) sengaja: kebal
  terhadap isi kolom agl yang mode-dependent.
"""
from __future__ import annotations


def field_agl(alt_msl_m: float, ground_ref_msl_m: float) -> float:
    """AGL di atas datum tanah lokasi. Clamp >= 0 (idempoten dgn aircraft.js)."""
    return max(float(alt_msl_m) - float(ground_ref_msl_m), 0.0)


class GroundDatum:
    """Datum tanah (ground_ref_msl) per-sesi stream FG.

    Prioritas sumber:
      1. `override_msl` dari config (FG_FIELD_ELEV_MSL) bila di-set eksplisit.
      2. auto-capture: alt_msl frame FG PERTAMA (SITL selalu spawn parkir,
         jadi frame pertama = pesawat di tanah = elevasi lapangan).

    WAJIB `reset()` setiap kali stream FG (re)connect (spawn/restart SITL bisa
    ganti lokasi -L). Instance dipakai bersama oleh mav_worker (path produksi)
    DAN tools/fg_stream_reader (gerbang M1) supaya angkanya identik = satu
    sumber kebenaran untuk transformasi.
    """

    __slots__ = ("_override", "_ref")

    def __init__(self, override_msl: float | None = None) -> None:
        self._override = None if override_msl is None else float(override_msl)
        self._ref: float | None = self._override

    def reset(self) -> None:
        """Panggil saat (re)connect FG. Override tetap; auto-capture dibuang."""
        self._ref = self._override

    @property
    def ground_ref_msl(self) -> float | None:
        return self._ref

    def agl_from(self, alt_msl_m: float) -> float:
        """Tangkap datum dari frame pertama bila perlu, lalu kembalikan AGL."""
        if self._ref is None:
            self._ref = float(alt_msl_m)  # frame parkir pertama = elevasi lapangan
        return field_agl(alt_msl_m, self._ref)