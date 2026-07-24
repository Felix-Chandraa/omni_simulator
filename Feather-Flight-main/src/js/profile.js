import { CONFIG } from "./config.js";
import { state } from "./state.js";

/**
 * F2 + P7 — Profil kendaraan + visibilitas widget PER-MODE LAYOUT.
 *
 * Tiga mode (state.ui.layoutMode, diatur widgets/layoutMode.js):
 *   full   : baseline profil + override pengguna (default: baseline ON)
 *   visual : override pengguna dengan DEFAULT SEMUA OFF (3D murni;
 *            widget bisa dinyalakan satu-satu dari drawer)
 *   gcs    : baseline profil PENUH — override DIABAIKAN (dashboard tetap)
 *
 * Override disimpan per profil per mode:
 *   localStorage "ff.widgets.<profil>.<mode>"  (mode: full|visual)
 *
 * AUTO-HIDE HOLDER: bila SEMUA [data-widget] di dalam sebuah panel
 * tersembunyi, panel (holder)-nya ikut disembunyikan total — tidak ada
 * kartu kosong. Berlaku di semua mode.
 */

export let PROFILE = null;

const overridesByMode = { full: null, visual: null };

function currentMode() {
  const m = state.ui && state.ui.layoutMode;
  return m === "visual" || m === "gcs" ? m : "full";
}

function storageKey(mode) {
  const name = (PROFILE && PROFILE.name) || "default";
  return `ff.widgets.${name}.${mode}`;
}

function overrides(mode) {
  if (overridesByMode[mode] === null) {
    try {
      overridesByMode[mode] =
        JSON.parse(localStorage.getItem(storageKey(mode)) || "{}") || {};
    } catch (_e) {
      overridesByMode[mode] = {};
    }
  }
  return overridesByMode[mode];
}

function saveOverrides(mode) {
  try {
    localStorage.setItem(storageKey(mode), JSON.stringify(overrides(mode)));
  } catch (_e) { /* abaikan */ }
}

function baselineActive() {
  return PROFILE && Array.isArray(PROFILE.dashboard)
    ? new Set(PROFILE.dashboard)
    : null; // null => semua ON
}

export function isWidgetVisible(key) {
  const mode = currentMode();
  const base = baselineActive();
  const inBaseline = base === null || base.has(key);

  if (mode === "gcs") {
    return inBaseline; // dashboard tetap, override diabaikan
  }

  const o = overrides(mode);
  if (Object.prototype.hasOwnProperty.call(o, key)) {
    return Boolean(o[key]);
  }

  return mode === "visual" ? false : inBaseline; // 3D: default OFF
}

/** Toggle hanya bermakna di full & visual (gcs mengabaikannya). */
export function setWidgetOverride(key, visible) {
  const mode = currentMode();
  if (mode === "gcs") {
    return;
  }
  overrides(mode)[key] = Boolean(visible);
  saveOverrides(mode);
  applyProfileToUI();
}

export function resetOverrides() {
  const mode = currentMode();
  if (mode === "gcs") {
    return;
  }
  overridesByMode[mode] = {};
  try {
    localStorage.removeItem(storageKey(mode));
  } catch (_e) { /* abaikan */ }
  applyProfileToUI();
}

function resolveProfileName() {
  if (CONFIG.vehicleProfile) {
    return CONFIG.vehicleProfile;
  }
  const vt = state.telemetry && state.telemetry.vehicle_type;
  return vt || "fixed_wing";
}

export async function loadProfile() {
  const name = resolveProfileName();
  try {
    const res = await fetch(`./vehicle_profiles/${name}.json`, { cache: "no-store" });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    PROFILE = await res.json();
    console.log(`[profile] aktif: ${PROFILE.label || PROFILE.name}`);
  } catch (err) {
    console.error(`[profile] gagal muat '${name}':`, err);
    PROFILE = { name, label: name, dashboard: null };
  }
  overridesByMode.full = null;
  overridesByMode.visual = null;
  applyProfileToUI();
  return PROFILE;
}

/** Terapkan visibilitas widget + AUTO-HIDE holder panel. */
export function applyProfileToUI() {
  if (!PROFILE) {
    return;
  }

  document.querySelectorAll("[data-widget]").forEach((el) => {
    el.style.display = isWidgetVisible(el.getAttribute("data-widget"))
      ? ""
      : "none";
  });

  for (const sel of [".left-panel", ".right-panel"]) {
    const panel = document.querySelector(sel);
    if (!panel) {
      continue;
    }
    let any = false;
    panel.querySelectorAll("[data-widget]").forEach((el) => {
      if (el.style.display !== "none") {
        any = true;
      }
    });
    panel.style.display = any ? "" : "none";
  }

  const badge = document.getElementById("profileLabel");
  if (badge) {
    badge.textContent = PROFILE.label || PROFILE.name || "";
  }
}
