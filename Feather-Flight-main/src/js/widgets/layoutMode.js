import { state } from "../state.js";
import { applyProfileToUI } from "../profile.js";

/**
 * P7 — Tiga mode layout (toggle-nya hidup di DRAWER settings, bukan topbar):
 *   full   : GCS + 3D
 *   gcs    : dashboard instrumen fullscreen (peta mati + render pause;
 *            widget = baseline penuh, checklist tidak berlaku)
 *   visual : 3D murni (default semua widget OFF; bisa dinyalakan per-widget)
 *
 * Persist: localStorage "ff.layoutMode". Console: setLayoutMode("gcs").
 */

export const MODES = ["full", "gcs", "visual"];
const LS_KEY = "ff.layoutMode";

function applyRenderLoop(mode) {
  const v = state.viewer;
  if (!v) {
    return;
  }
  const wantRunning = mode !== "gcs";
  if (v.useDefaultRenderLoop !== wantRunning) {
    v.useDefaultRenderLoop = wantRunning;
    console.log(
      `[layout] Cesium render loop ${wantRunning ? "AKTIF" : "PAUSE (mode GCS)"}`
    );
  }
}

export function setLayoutMode(mode) {
  if (!MODES.includes(mode)) {
    console.warn(`[layout] mode tak dikenal: ${mode} (${MODES.join("/")})`);
    return;
  }

  state.ui.layoutMode = mode;
  document.body.classList.toggle("mode-gcs", mode === "gcs");
  document.body.classList.toggle("mode-visual", mode === "visual");

  document.querySelectorAll(".layout-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.layout === mode);
  });

  applyRenderLoop(mode);
  applyProfileToUI(); // visibilitas widget & holder mengikuti mode

  try {
    localStorage.setItem(LS_KEY, mode);
  } catch (_e) { /* abaikan */ }
}

export function getLayoutMode() {
  return state.ui.layoutMode;
}

export function initLayoutMode() {
  let saved = "full";
  try {
    const v = localStorage.getItem(LS_KEY);
    if (MODES.includes(v)) {
      saved = v;
    }
  } catch (_e) { /* abaikan */ }

  setLayoutMode(saved);
}

if (typeof window !== "undefined") {
  window.setLayoutMode = setLayoutMode;
}
