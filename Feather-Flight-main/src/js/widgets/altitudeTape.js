import { els } from "../dom.js";

/**
 * Altitude tape (indikator grafis vertikal) — sumber bisa dipilih.
 *
 * "agl" (default): AGL dari FG stream bila aktif; fallback REL MAVLink
 *                  (doktrin hud.js, label selalu jujur).
 * "msl": alt_msl dari bus.
 *
 * Preferensi disimpan settings.js di localStorage "ff.tapeSource".
 * Catatan P1: saat relative-to-home diwujudkan, hanya pemilihan nilai di
 * sini yang berubah — geometri tape tidak.
 */

const PX_PER_M = 4;
const MAJOR_M = 10;
const MINOR_M = 5;
const WINDOW_M = 60;

let lastBucket = null;
let tapeSource = "agl";

try {
  const saved = localStorage.getItem("ff.tapeSource");
  if (saved === "msl" || saved === "agl") {
    tapeSource = saved;
  }
} catch (_e) { /* storage tidak tersedia — pakai default */ }

export function setTapeSource(src) {
  if (src === "agl" || src === "msl") {
    tapeSource = src;
    lastBucket = null; // paksa rebuild skala pada frame berikutnya
  }
}

export function getTapeSource() {
  return tapeSource;
}

function rebuildScale(centerM) {
  const scale = els.altTapeScale;
  if (!scale) {
    return;
  }

  scale.textContent = "";

  const from = Math.floor((centerM - WINDOW_M) / MINOR_M) * MINOR_M;
  const to = Math.ceil((centerM + WINDOW_M) / MINOR_M) * MINOR_M;

  for (let v = from; v <= to; v += MINOR_M) {
    const isMajor = v % MAJOR_M === 0;
    const tick = document.createElement("div");
    tick.className = isMajor ? "alt-tick major" : "alt-tick";
    tick.style.top = `${-v * PX_PER_M}px`; // nilai naik ke ATAS

    if (isMajor) {
      const label = document.createElement("span");
      label.className = "alt-tick-label";
      label.textContent = String(v);
      tick.appendChild(label);
    }

    scale.appendChild(tick);
  }
}

export function updateAltitudeTape(data = {}) {
  let altitude;
  let caption;

  if (tapeSource === "msl") {
    altitude = Number(data.alt_msl);
    caption = "m MSL";
  } else {
    const aglNum = Number(data.agl);
    const fgActive = data.pose_source === "fg" && Number.isFinite(aglNum);
    altitude = Number(fgActive ? aglNum : data.alt);
    caption = fgActive ? "m AGL (FG 30 Hz)" : "m REL (MAVLink)";
  }

  const scale = els.altTapeScale;
  const valueEl = els.altTapeValue;

  if (!scale || !valueEl) {
    return { altitude }; // layout tanpa tape — jangan meledak
  }

  if (!Number.isFinite(altitude)) {
    valueEl.textContent = "---";
    if (els.altCaption) {
      els.altCaption.textContent = "No data";
    }
    return { altitude: null };
  }

  const bucket = Math.round(altitude / MAJOR_M) * MAJOR_M;
  if (bucket !== lastBucket) {
    rebuildScale(bucket);
    lastBucket = bucket;
  }

  const half = scale.parentElement.clientHeight / 2;
  scale.style.transform = `translateY(${half + altitude * PX_PER_M}px)`;

  valueEl.textContent = altitude.toFixed(1);
  valueEl.classList.toggle("negative", altitude < 0);

  if (els.altCaption) {
    els.altCaption.textContent = caption;
  }

  return { altitude };
}
