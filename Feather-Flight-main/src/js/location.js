import { CONFIG } from "./config.js";

/**
 * P5 — Location loader (SDD Bab 8 langkah 5).
 *
 * Membaca `locations/active_location.json` (di-generate tools/gen_location_config.py
 * dari SATU file .env) lalu menerapkan ke CONFIG.home dan CONFIG.views.ground.gcs
 * saat runtime — jadi ganti lokasi = regen json + reload, tanpa edit kode.
 *
 * Fallback aman: bila fetch gagal, CONFIG default dipertahankan (tak crash).
 * geoidOffsetM disimpan di CONFIG.location utk dipakai P1 advisory nanti.
 */

export let ACTIVE_LOCATION = null;

export async function loadLocation() {
  try {
    const res = await fetch("./locations/active_location.json", { cache: "no-store" });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    ACTIVE_LOCATION = await res.json();
    applyLocation(ACTIVE_LOCATION);
    console.log(`[location] aktif: ${ACTIVE_LOCATION.name}`);
  } catch (err) {
    // Belum di-generate / setup non-http -> pakai default config (mis. CMAC/SF).
    console.warn("[location] active_location.json tidak dimuat, pakai default:", err.message);
  }
  return ACTIVE_LOCATION;
}

function applyLocation(loc) {
  if (!loc) {
    return;
  }
  if (Number.isFinite(loc.lat) && Number.isFinite(loc.lon)) {
    CONFIG.home.lat = loc.lat;
    CONFIG.home.lon = loc.lon;
    if (Number.isFinite(loc.altMsl)) {
      CONFIG.home.alt = loc.altMsl;
    }
  }
  // Ground view = posisi GCS instruktur (dibaca views.ground.gcs).
  const g = loc.gcs || {};
  if (CONFIG.views && CONFIG.views.ground && Number.isFinite(g.lat) && Number.isFinite(g.lon)) {
    CONFIG.views.ground.gcs.lat = g.lat;
    CONFIG.views.ground.gcs.lon = g.lon;
    CONFIG.views.ground.gcs.altMsl = Number.isFinite(g.altMsl) ? g.altMsl : null;
  }
  // Simpan seluruh lokasi (incl. geoidOffsetM) utk konsumen lain (P1).
  CONFIG.location = loc;
}