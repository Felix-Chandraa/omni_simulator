import { els } from "../dom.js";

/**
 * Attitude Direction Indicator (ADI) profesional.
 *
 * Satuan input: DERAJAT (backend sudah konversi di fgnetfdm.py &
 * mav_worker.py — jangan konversi ulang).
 *
 * Konvensi instrumen nyata:
 * - Bank kanan  => horizon & sky-pointer berputar berlawanan: rotate(-roll).
 * - Pitch up    => horizon turun: translateY(+pitch * PX_PER_DEG).
 * - Roll arc & segitiga referensi TETAP di bezel; sky-pointer ikut bola.
 * - Simbol pesawat (sayap amber) TETAP di tengah.
 *
 * Struktur dibangun sekali (lazy) ke dalam kontainer els.adi:
 *   .adi > .adi-roll > .adi-pitch > (.adi-ball + svg ladder)
 *   .adi > svg roll-arc (fixed) ; .adi-roll > .adi-sky-ptr ; .adi > .adi-wings
 */

const PX_PER_DEG = 2.2;
const PITCH_CLAMP = 45;
const SVG_NS = "http://www.w3.org/2000/svg";

let built = false;
let rollEl = null;
let pitchEl = null;

function svgEl(name, attrs) {
  const el = document.createElementNS(SVG_NS, name);
  for (const [k, v] of Object.entries(attrs)) {
    el.setAttribute(k, v);
  }
  return el;
}

function buildLadder() {
  // Ladder ikut bola: garis 10-an berlabel dua sisi, garis pendek 5-an.
  const svg = svgEl("svg", {
    class: "adi-ladder",
    viewBox: "-90 -110 180 220"
  });

  for (let deg = -30; deg <= 30; deg += 5) {
    if (deg === 0) {
      continue; // horizon digambar oleh bola sendiri
    }
    const y = -deg * PX_PER_DEG;
    const major = deg % 10 === 0;
    const half = major ? 26 : 13;

    svg.appendChild(svgEl("line", {
      x1: -half, y1: y, x2: half, y2: y,
      class: "adi-ladder-line" + (major ? " major" : "")
    }));

    if (major) {
      const label = String(Math.abs(deg));
      for (const x of [-half - 14, half + 14]) {
        const t = svgEl("text", { x, y: y + 3.5, class: "adi-ladder-num" });
        t.textContent = label;
        svg.appendChild(t);
      }
    }
  }

  return svg;
}

function buildRollArc() {
  // Skala bank TETAP di bezel: tick 0/±10/±20/±30/±45/±60 + segitiga ref.
  const svg = svgEl("svg", {
    class: "adi-arc",
    viewBox: "-100 -100 200 200"
  });

  const R1 = 88;
  const R2 = 96;
  for (const a of [-60, -45, -30, -20, -10, 0, 10, 20, 30, 45, 60]) {
    const rad = (a - 90) * Math.PI / 180; // 0 deg bank = puncak
    const big = a === 0 || Math.abs(a) === 30 || Math.abs(a) === 60;
    const r1 = big ? R1 - 4 : R1;
    svg.appendChild(svgEl("line", {
      x1: r1 * Math.cos(rad), y1: r1 * Math.sin(rad),
      x2: R2 * Math.cos(rad), y2: R2 * Math.sin(rad),
      class: "adi-arc-tick" + (big ? " major" : "")
    }));
  }

  // Segitiga referensi tetap di 0 (menunjuk ke bawah, ke sky-pointer).
  svg.appendChild(svgEl("path", {
    d: "M 0 -86 L -7 -98 L 7 -98 Z",
    class: "adi-arc-ref"
  }));

  return svg;
}

function build() {
  const host = els.adi;
  if (!host || built) {
    return built;
  }

  rollEl = document.createElement("div");
  rollEl.className = "adi-roll";

  pitchEl = document.createElement("div");
  pitchEl.className = "adi-pitch";

  const ball = document.createElement("div");
  ball.className = "adi-ball";

  pitchEl.appendChild(ball);
  pitchEl.appendChild(buildLadder());
  rollEl.appendChild(pitchEl);

  // Sky-pointer: segitiga yang IKUT roll, menunjuk skala tetap di bezel.
  const skyPtr = document.createElement("div");
  skyPtr.className = "adi-sky-ptr";
  rollEl.appendChild(skyPtr);

  host.appendChild(rollEl);
  host.appendChild(buildRollArc());

  // Simbol pesawat tetap: sayap amber standar ADI.
  const wings = document.createElement("div");
  wings.className = "adi-wings";
  wings.innerHTML =
    '<div class="w l"></div><div class="dot"></div><div class="w r"></div>';
  host.appendChild(wings);

  built = true;
  return built;
}

export function updateAttitude(data = {}) {
  const roll = Number(data.roll);
  const pitch = Number(data.pitch);
  const yaw = Number(data.yaw);

  if (!build()) {
    return { roll, pitch }; // layout tanpa ADI — jangan meledak
  }

  if (!Number.isFinite(roll) || !Number.isFinite(pitch)) {
    if (els.rpyReadout) {
      els.rpyReadout.textContent = "R ---\u00B0  P ---\u00B0  Y ---\u00B0";
    }
    return { roll: null, pitch: null };
  }

  const p = Math.max(-PITCH_CLAMP, Math.min(PITCH_CLAMP, pitch));

  rollEl.style.transform = `rotate(${-roll}deg)`;
  pitchEl.style.transform = `translateY(${p * PX_PER_DEG}px)`;

  if (els.rpyReadout) {
    const y = Number.isFinite(yaw) ? yaw.toFixed(0) : "---";
    els.rpyReadout.textContent =
      `R ${roll.toFixed(0)}\u00B0  P ${pitch.toFixed(0)}\u00B0  Y ${y}\u00B0`;
  }

  return { roll, pitch };
}
