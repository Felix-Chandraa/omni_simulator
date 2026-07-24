import { CONFIG } from "../config.js";
import { state } from "../state.js";

/**
 * P5.6 — Permukaan lanud: MESH TERRAIN-BLENDED bertekstur, bukan "balok".
 *
 * Evolusi (jangan ulangi jalan buntu):
 * - P5.5a: hanya menggeser koordinat pesawat -> mesh tetap bergelombang.
 * - P5.5b: slab datar + skirt 12 m -> benar secara fisika, tapi tampak
 *   seperti balok raksasa menonjol dari tanah.
 * - P5.6 (ini): satu mesh grid yang tingginya = flattenHeight():
 *      * DATAR sempurna di atas runway,
 *      * MELANDAI mulus (smoothstep) keluar dari zona blend,
 *      * MENYATU persis dengan terrain asli di tepi -> tidak ada tebing.
 *   Ditambah alpha fade di batas terluar (custom fabric shader) untuk
 *   menyembunyikan jahitan & z-fighting, dan tekstur citra udara.
 *
 * Konsistensi kunci: MESH dan PESAWAT digerakkan FUNGSI MURNI YANG SAMA
 * (flattenHeight). Mustahil ada beda tinggi antara ban dan aspal.
 *
 * Kenapa bukan GroundPrimitive/ClassificationType.TERRAIN: primitif itu
 * MENDRAPE mengikuti kontur (kebalikan yang kita mau). Cesium tidak punya
 * API untuk mendeformasi quantized-mesh World Terrain.
 *
 * Biaya render: 1 primitive, ~19k segitiga, 1 tekstur. Tidak membunuh FPS.
 */

const DEG2RAD = Math.PI / 180;
const M_PER_DEG_LAT = 111320;
const LS_KEY = "ff.runwayCal";

let geom = null;

function thresholds() {
  const rw = CONFIG.runway;
  try {
    const saved = JSON.parse(localStorage.getItem(LS_KEY) || "null");
    if (saved && saved.a && saved.b) {
      return { a: saved.a, b: saved.b, calibrated: true };
    }
  } catch (_e) { /* abaikan */ }
  return { a: rw.thresholdA, b: rw.thresholdB, calibrated: false };
}

function getGeom() {
  if (geom) {
    return geom;
  }

  const rw = CONFIG.runway;
  if (!rw || !rw.enabled) {
    return null;
  }

  const { a, b, calibrated } = thresholds();
  const midLat = (a.lat + b.lat) / 2;
  const midLon = (a.lon + b.lon) / 2;
  const mPerDegLon = M_PER_DEG_LAT * Math.cos(midLat * DEG2RAD);

  const vx = (b.lon - a.lon) * mPerDegLon;
  const vy = (b.lat - a.lat) * M_PER_DEG_LAT;
  const len = Math.hypot(vx, vy);

  geom = {
    aLat: a.lat, aLon: a.lon,
    bLat: b.lat, bLon: b.lon,
    midLat, midLon, mPerDegLon,
    ux: vx / len, uy: vy / len,
    length: len,
    halfWidth: rw.widthMeters / 2,
    blend: rw.blendMeters,
    bearingDeg: (Math.atan2(vx, vy) / DEG2RAD + 360) % 360,
    calibrated
  };

  return geom;
}

function invalidateGeom() {
  geom = null;
}

function pt(g, s, t, h) {
  const ex = s * g.ux - t * g.uy;
  const ny = s * g.uy + t * g.ux;
  return [g.aLon + ex / g.mPerDegLon, g.aLat + ny / M_PER_DEG_LAT, h];
}

function toLocal(lon, lat, g) {
  const ex = (lon - g.aLon) * g.mPerDegLon;
  const ny = (lat - g.aLat) * M_PER_DEG_LAT;
  return { s: ex * g.ux + ny * g.uy, t: -ex * g.uy + ny * g.ux };
}

function smoothstep(x) {
  const c = Math.max(0, Math.min(1, x));
  return c * c * (3 - 2 * c);
}

export function flattenWeight(lon, lat) {
  const g = getGeom();
  if (!g) {
    return 0;
  }

  const { s, t } = toLocal(lon, lat, g);
  const outS = Math.max(0, Math.max(-s, s - g.length));
  const outT = Math.max(0, Math.abs(t) - g.halfWidth);
  const dist = Math.hypot(outS, outT);

  if (dist <= 0) {
    return 1;
  }
  if (dist >= g.blend) {
    return 0;
  }
  return 1 - smoothstep(dist / g.blend);
}

/**
 * FUNGSI MURNI — posisi ban pesawat mengikuti slab DATAR (elevM), agar
 * sinkron dengan atap slab. Di luar zona blend: terrain asli. (Dipertahankan
 * dari seluruh evolusi; kini target = satu nilai datar.)
 */
export function flattenHeight(rawH, lon, lat) {
  if (!Number.isFinite(rawH)) {
    return rawH;
  }

  const elev = state.runway && state.runway.elevM;
  if (!Number.isFinite(elev)) {
    return rawH;
  }

  const w = flattenWeight(lon, lat);
  return w <= 0 ? rawH : rawH + (elev - rawH) * w;
}

/**
 * P5.7 — Ukur PROFIL runway sebagai BIDANG MIRING (regresi linear), bukan
 * satu bidang datar setinggi max.
 *
 * Bug P5.6: runway asli 1,5 km melintasi terrain yang menanjak. Memaksanya
 * ke satu bidang DATAR setinggi max(terrain) = menimbun ujung rendah ->
 * "gunung landasan". Landasan sungguhan memang MIRING.
 *
 * Metode: h(s) = a + b*s (least squares sepanjang centerline), lalu digeser
 * naik sebesar residual positif terbesar + eps sehingga permukaan selalu
 * >= terrain di seluruh runway (tak ada gundukan menembus), tapi tetap
 * mengikuti kemiringan alami -> tidak ada bukit buatan.
 */
/**
 * P5.8 (rollback ke P5.5c): elevasi = SATU nilai datar (max terrain + eps).
 * Rata-air horizontal; tim menerima tebing di ujung rendah. (Regresi miring
 * P5.7 dibuang atas keputusan tim.)
 */
export function measureRunwayElevation(samples = 41) {
  const g = getGeom();
  if (!g || !state.viewer) {
    return null;
  }

  const globe = state.viewer.scene.globe;
  const heights = [];

  for (let i = 0; i < samples; i++) {
    const f = i / (samples - 1);
    const lat = g.aLat + (g.bLat - g.aLat) * f;
    const lon = g.aLon + (g.bLon - g.aLon) * f;
    const h = globe.getHeight(Cesium.Cartographic.fromDegrees(lon, lat));
    if (Number.isFinite(h)) {
      heights.push(h);
    }
  }

  if (heights.length === 0) {
    return null;
  }

  heights.sort((a, b) => a - b);
  const mid = Math.floor(heights.length / 2);
  const median = heights.length % 2
    ? heights[mid] : (heights[mid - 1] + heights[mid]) / 2;
  const max = heights[heights.length - 1];

  state.runway.elevM = max + CONFIG.runway.slabEpsilonM;
  state.runway.elevM = 359;
  state.runway.medianM = median;
  state.runway.spreadM = max - heights[0];
  state.runway.sampleCount = heights.length;

  console.log(
    `[runway] slab DATAR: elev=${state.runway.elevM.toFixed(2)} m ` +
    `(median=${median.toFixed(2)}, sebaran=${state.runway.spreadM.toFixed(2)} m) | ` +
    `bearing=${g.bearingDeg.toFixed(2)}\u00B0 panjang=${g.length.toFixed(0)} m | ` +
    `kalibrasi=${g.calibrated ? "YA" : "TIDAK (seed)"}`
  );

  return state.runway.elevM;
}

/* ===================== Slab (Entity extruded) ===================== */

function clearSlab() {
  const r = state.runway;

  if (r.slabEntity) {
    state.viewer.entities.remove(r.slabEntity);
    r.slabEntity = null;
  }
  if (r.slabTopPrimitive) {
    state.viewer.scene.primitives.remove(r.slabTopPrimitive);
    r.slabTopPrimitive = null;
  }
  if (Array.isArray(r.markingEntities)) {
    r.markingEntities.forEach((e) => state.viewer.entities.remove(e));
  }
  r.markingEntities = [];
}

/**
 * P5.8 — Slab BALOK: Entity polygon datar + extrudedHeight (dinding ke
 * bawah). Rata-air horizontal, dinding vertikal tegas. Marka digambar
 * rata-air di atas atap slab.
 */
export function buildRunwaySlab() {
  const g = getGeom();
  const elev = state.runway && state.runway.elevM;

  if (!g || !state.viewer || !Number.isFinite(elev)) {
    return false;
  }

  clearSlab();

  const rw = CONFIG.runway;
  const hw = g.halfWidth;

  const cornersTop = Cesium.Cartesian3.fromDegreesArrayHeights([
    ...pt(g, 0, -hw, elev),
    ...pt(g, g.length, -hw, elev),
    ...pt(g, g.length, hw, elev),
    ...pt(g, 0, hw, elev)
  ]);

  // (1) BADAN slab: DINDING/skirt saja (closeTop:false). Tak ada tutup atas
  // yang sebidang dgn atap bertekstur => nol z-fighting.
  const sideColor = Cesium.Color.fromCssColorString(rw.asphaltColor);
  state.runway.slabEntity = state.viewer.entities.add({
    name: "runway-slab",
    polygon: {
      hierarchy: new Cesium.PolygonHierarchy(cornersTop),
      perPositionHeight: true,
      extrudedHeight: elev - rw.skirtMeters,
      closeTop: false,
      closeBottom: false,
      material: sideColor,
      outline: false,
      shadows: Cesium.ShadowMode.DISABLED
    }
  });

  // (2) ATAP bertekstur — PRIMITIVE dgn koordinat ST EKSPLISIT per-vertex.
  // Menghindari pemetaan UV berbasis bounding-box milik Entity polygon (biang
  // skala salah + orientasi meleset pada runway miring). Pemetaan deterministik:
  // s (image X, 0..1) = arah PANJANG (threshold A->B); t (image Y) = LEBAR.
  const ell = Cesium.Ellipsoid.WGS84;
  const cA = Cesium.Cartesian3.fromDegrees(...pt(g, 0, -hw, elev));
  const cB = Cesium.Cartesian3.fromDegrees(...pt(g, g.length, -hw, elev));
  const cC = Cesium.Cartesian3.fromDegrees(...pt(g, g.length, hw, elev));
  const cD = Cesium.Cartesian3.fromDegrees(...pt(g, 0, hw, elev));
  const posVals = new Float64Array([
    cA.x, cA.y, cA.z, cB.x, cB.y, cB.z, cC.x, cC.y, cC.z, cD.x, cD.y, cD.z
  ]);
  const nrm = [];
  [cA, cB, cC, cD].forEach((c) => {
    const n = ell.geodeticSurfaceNormal(c, new Cesium.Cartesian3());
    nrm.push(n.x, n.y, n.z);
  });
  const topGeom = new Cesium.Geometry({
    attributes: {
      position: new Cesium.GeometryAttribute({
        componentDatatype: Cesium.ComponentDatatype.DOUBLE,
        componentsPerAttribute: 3,
        values: posVals
      }),
      normal: new Cesium.GeometryAttribute({
        componentDatatype: Cesium.ComponentDatatype.FLOAT,
        componentsPerAttribute: 3,
        values: new Float32Array(nrm)
      }),
      st: new Cesium.GeometryAttribute({
        componentDatatype: Cesium.ComponentDatatype.FLOAT,
        componentsPerAttribute: 2,
        values: new Float32Array([0, 0, 1, 0, 1, 1, 0, 1])
      })
    },
    indices: new Uint16Array([0, 1, 2, 0, 2, 3]),
    primitiveType: Cesium.PrimitiveType.TRIANGLES,
    boundingSphere: Cesium.BoundingSphere.fromVertices(Array.from(posVals))
  });
  state.runway.slabTopPrimitive = state.viewer.scene.primitives.add(
    new Cesium.Primitive({
      geometryInstances: new Cesium.GeometryInstance({ geometry: topGeom }),
      appearance: new Cesium.MaterialAppearance({
        material: new Cesium.Material({
          fabric: { type: "Image", uniforms: { image: rw.textureUri } }
        }),
        flat: true,
        faceForward: true,
        translucent: false
      }),
      asynchronous: false
    })
  );

  console.log(
    `[runway] slab BALOK: ${g.length.toFixed(0)} x ${rw.widthMeters} m @ ` +
    `${elev.toFixed(2)} m, skirt ${rw.skirtMeters} m (dinding vertikal)`
  );

  return true;
}

/** Marka rata-air di atas atap slab (edge, centerline, piano keys, nomor). */
function buildMarkings(g, elev) {
  const marks = [];
  const add = (e) => marks.push(state.viewer.entities.add(e));
  const H = elev + 0.05; 
  const white = Cesium.Color.WHITE.withAlpha(0.9);
  const hw = g.halfWidth;

  const stripe = (s1, t1, s2, t2, w) =>
    add({
      polyline: {
        positions: Cesium.Cartesian3.fromDegreesArrayHeights([
          ...pt(g, s1, t1, H), ...pt(g, s2, t2, H)
        ]),
        width: w,
        material: white,
        arcType: Cesium.ArcType.NONE,
        clampToGround: false
      }
    });

  stripe(0, -hw + 1, g.length, -hw + 1, 3);
  stripe(0, hw - 1, g.length, hw - 1, 3);

  for (let s = 60; s < g.length - 60; s += 50) {
    stripe(s, 0, Math.min(s + 30, g.length - 60), 0, 4);
  }

  for (const end of [0, 1]) {
    for (let k = -3; k <= 3; k++) {
      if (k === 0) continue;
      const t = k * 3.2;
      stripe(
        end === 0 ? 6 : g.length - 6, t,
        end === 0 ? 30 : g.length - 30, t,
        6
      );
    }
  }

  const numA = String(Math.round(g.bearingDeg / 10) % 36 || 36).padStart(2, "0");
  const numB = String(Math.round(((g.bearingDeg + 180) % 360) / 10) % 36 || 36).padStart(2, "0");

  const drawDigit = (sCenter, tCenter, char, isRotated) => {
    const h = 5.5; // Lebih kecil (tinggi 11m)
    const w = 2.5; // Lebih kecil (lebar 5m)
    // Perbaikan orientasi cermin (w positif = kiri)
    const pts = {
      tl: [h, w], tr: [h, -w],
      ml: [0, w], mr: [0, -w],
      bl: [-h, w], br: [-h, -w]
    };
    if (isRotated) {
      for (let k in pts) pts[k] = [-pts[k][0], -pts[k][1]];
    }

    // Lebih TEBAL (width: 8)
    const drawLine = (p1, p2) => stripe(sCenter + p1[0], tCenter + p1[1], sCenter + p2[0], tCenter + p2[1], 8);

    if (['0','2','3','5','6','7','8','9'].includes(char)) drawLine(pts.tl, pts.tr);
    if (['0','4','5','6','8','9'].includes(char)) drawLine(pts.tl, pts.ml);
    if (['0','1','2','3','4','7','8','9'].includes(char)) drawLine(pts.tr, pts.mr);
    if (['2','3','4','5','6','8','9'].includes(char)) drawLine(pts.ml, pts.mr);
    if (['0','2','6','8'].includes(char)) drawLine(pts.ml, pts.bl);
    if (['0','1','3','4','5','6','7','8','9'].includes(char)) drawLine(pts.mr, pts.br);
    if (['0','2','3','5','6','8','9'].includes(char)) drawLine(pts.bl, pts.br);
  };

  const drawNumber = (s, text, isRotated) => {
    // Perbaikan offset agar pas di tengah (center) dan urutan baca benar
    drawDigit(s, isRotated ? -3.5 : 3.5, text[0], isRotated);
    drawDigit(s, isRotated ? 3.5 : -3.5, text[1], isRotated);
  };

  drawNumber(45, numA, false);
  drawNumber(g.length - 45, numB, true);

  state.runway.markingEntities = marks;
}

/* ===================== Geoid (berpenjaga) ===================== */

export function updateGeoidOffset(rawTerrainM, telemetry) {
  if (state.geoid.offsetM !== null) {
    return state.geoid.offsetM;
  }

  const agl = Number(telemetry.agl);
  const msl = Number(telemetry.alt_msl);
  const gs = Number(telemetry.gs);

  const onGround =
    telemetry.pose_source === "fg" &&
    Number.isFinite(agl) && agl >= -1 && agl < 3 &&
    Number.isFinite(gs) && gs < 2;

  if (!onGround || !Number.isFinite(msl) || !Number.isFinite(rawTerrainM)) {
    return null;
  }

  const off = rawTerrainM - (msl - agl);

  if (!Number.isFinite(off) || Math.abs(off) > 100) {
    if (!state.geoid.warned) {
      state.geoid.warned = true;
      console.warn(
        `[geoid] offset ditolak (tidak masuk akal): ${off.toFixed(1)} m - ` +
        "peringatan hanya sekali; alt_msl dicurigai salah satuan (hutang forensik)"
      );
    }
    return null;
  }

  state.geoid.offsetM = off;
  console.log(`[geoid] offset TERKUNCI = ${off.toFixed(2)} m (Cesium - SITL MSL)`);
  return off;
}

export function runwayShoulder() {
  const g = getGeom();
  if (!g) {
    return null;
  }

  const rw = CONFIG.runway;
  const off = g.halfWidth + rw.shoulderOffsetMeters;
  const side = rw.shoulderSide === "left" ? -1 : 1;
  const [lon, lat] = pt(g, g.length / 2, side * off, 0);

  return { lat, lon };
}

/* ===================== Alat kalibrasi & utilitas console ============ */

let calHandler = null;
let calPicks = [];

const fmt = (v, d = 7) => Number(v).toFixed(d);

function rebuildAll() {
  invalidateGeom();
  measureRunwayElevation();
  buildRunwaySlab();
}

function finishCal() {
  const [a, b] = calPicks;
  const midLat = (a.lat + b.lat) / 2;
  const mLon = M_PER_DEG_LAT * Math.cos(midLat * DEG2RAD);
  const vx = (b.lon - a.lon) * mLon;
  const vy = (b.lat - a.lat) * M_PER_DEG_LAT;
  const brg = (Math.atan2(vx, vy) / DEG2RAD + 360) % 360;
  const len = Math.hypot(vx, vy);

  localStorage.setItem(LS_KEY, JSON.stringify({ a, b }));
  rebuildAll();

  console.log("%c=== KALIBRASI RUNWAY SELESAI ===", "font-weight:bold;color:#41d1ff");
  console.log(`Panjang: ${len.toFixed(1)} m | Heading true: ${brg.toFixed(2)}\u00B0`);
  console.log(
    `RWY15_LAT=${fmt(a.lat, 6)}\nRWY15_LON=${fmt(a.lon, 6)}\n` +
    `RWY33_LAT=${fmt(b.lat, 6)}\nRWY33_LON=${fmt(b.lon, 6)}\n` +
    `HDG_TRUE=${brg.toFixed(1)}\nLAT=${fmt(a.lat, 7)}\nLON=${fmt(a.lon, 7)}`
  );
  console.log(`Wiriadinata=${fmt(a.lat, 7)},${fmt(a.lon, 7)},349.00,${brg.toFixed(1)}`);

  calHandler.destroy();
  calHandler = null;
  calPicks = [];
}

export function calibrateRunway() {
  if (!state.viewer) {
    return;
  }
  if (calHandler) {
    calHandler.destroy();
  }

  calPicks = [];
  console.log(
    "%c[kalibrasi] Klik ujung runway 15, lalu ujung 33.",
    "color:#ffb61e;font-weight:bold"
  );

  calHandler = new Cesium.ScreenSpaceEventHandler(state.viewer.scene.canvas);
  calHandler.setInputAction((click) => {
    const cart =
      state.viewer.scene.pickPosition(click.position) ||
      state.viewer.camera.pickEllipsoid(click.position);

    if (!cart) {
      console.warn("[kalibrasi] gagal memilih titik, coba lagi");
      return;
    }

    const c = Cesium.Cartographic.fromCartesian(cart);
    calPicks.push({
      lat: Cesium.Math.toDegrees(c.latitude),
      lon: Cesium.Math.toDegrees(c.longitude)
    });
    console.log(`[kalibrasi] titik ${calPicks.length} terekam`);

    if (calPicks.length === 2) {
      finishCal();
    }
  }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
}

export function resetRunwayCalibration() {
  localStorage.removeItem(LS_KEY);
  rebuildAll();
  console.log("[kalibrasi] direset ke CONFIG");
}



export function setRunwayTexture(url) {
  CONFIG.runway.textureUri = url;
  rebuildAll();
  console.log(`[runway] tekstur -> ${url}`);
}

export function setRunwayTextureRotation(deg) {
  CONFIG.runway.textureRotationDeg = Number(deg);
  rebuildAll();
  console.log(`[runway] rotasi UV tekstur = ${deg} deg (kunci di config bila pas)`);
}

if (typeof window !== "undefined") {
  window.calibrateRunway = calibrateRunway;
  window.resetRunwayCalibration = resetRunwayCalibration;
  window.rebuildRunway = rebuildAll;
  window.setRunwayTexture = setRunwayTexture;
  window.setRunwayTextureRotation = setRunwayTextureRotation;
}
