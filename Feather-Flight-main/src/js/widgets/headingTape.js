import { els } from "../dom.js";
import { fmtDeg } from "../utils/format.js";

/**
 * Heading indicator (HSI-style compass rose) profesional.
 *
 * - Rose (tick + angka + kardinal) BERPUTAR: rotate(-heading), sehingga
 *   arah hidung pesawat selalu di lubber line atas (konvensi HSI nyata).
 * - Lubber line & glyph pesawat TETAP.
 * - Rumah kanonik SEMUA tampilan heading (rose + angka besar) ada di
 *   modul ini — hud.js tidak lagi menyentuh heading.
 *
 * Dibangun lazy sekali ke kontainer els.hsi.
 */

const SVG_NS = "http://www.w3.org/2000/svg";

let built = false;
let roseEl = null;

function svgEl(name, attrs) {
  const el = document.createElementNS(SVG_NS, name);
  for (const [k, v] of Object.entries(attrs)) {
    el.setAttribute(k, v);
  }
  return el;
}

const CARDINALS = { 0: "N", 90: "E", 180: "S", 270: "W" };

function buildRose() {
  const g = svgEl("g", { class: "hsi-rose" });

  for (let deg = 0; deg < 360; deg += 5) {
    const major30 = deg % 30 === 0;
    const major10 = deg % 10 === 0;
    const len = major30 ? 13 : major10 ? 9 : 5;

    g.appendChild(svgEl("line", {
      x1: 0, y1: -92, x2: 0, y2: -92 + len,
      transform: `rotate(${deg})`,
      class: "hsi-tick" + (major10 ? " major" : "")
    }));

    if (major30) {
      const cardinal = CARDINALS[deg];
      const t = svgEl("text", {
        x: 0, y: -64,
        transform: `rotate(${deg})`,
        class: "hsi-num" + (cardinal ? " cardinal" : "")
      });
      t.textContent = cardinal || String(deg / 10);
      g.appendChild(t);
    }
  }

  return g;
}

function build() {
  const host = els.hsi;
  if (!host || built) {
    return built;
  }

  const svg = svgEl("svg", { class: "hsi-svg", viewBox: "-100 -100 200 200" });

  // Cincin dasar
  svg.appendChild(svgEl("circle", { cx: 0, cy: 0, r: 92, class: "hsi-ring" }));

  roseEl = buildRose();
  svg.appendChild(roseEl);

  // Lubber line tetap (atas) + tick referensi 45-an halus
  for (const a of [45, 135, 225, 315]) {
    svg.appendChild(svgEl("line", {
      x1: 0, y1: -99, x2: 0, y2: -93,
      transform: `rotate(${a})`,
      class: "hsi-fixed-tick"
    }));
  }
  svg.appendChild(svgEl("path", {
    d: "M 0 -84 L -6 -98 L 6 -98 Z",
    class: "hsi-lubber"
  }));

  // Glyph pesawat tetap di tengah (menghadap lubber line)
  svg.appendChild(svgEl("path", {
    d: "M 0 -16 L 3.2 -5 L 14 2 L 14 6 L 3 3.4 L 2.6 12 L 7 15.5 L 7 18.5 " +
       "L 0 16.5 L -7 18.5 L -7 15.5 L -2.6 12 L -3 3.4 L -14 6 L -14 2 " +
       "L -3.2 -5 Z",
    class: "hsi-plane"
  }));

  host.appendChild(svg);
  built = true;
  return built;
}

export function updateHeadingTape(data = {}) {
  const hdg = Number(data.hdg);

  if (!build()) {
    return { heading: hdg }; // layout tanpa HSI — jangan meledak
  }

  if (!Number.isFinite(hdg)) {
    if (els.headingBig) {
      els.headingBig.textContent = "---";
    }
    return { heading: null };
  }

  roseEl.setAttribute("transform", `rotate(${-hdg})`);

  if (els.headingBig) {
    els.headingBig.textContent = fmtDeg(hdg);
  }

  return { heading: hdg };
}
