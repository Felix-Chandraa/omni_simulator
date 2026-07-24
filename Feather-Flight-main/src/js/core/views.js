import { CONFIG } from "../config.js";
import { state } from "../state.js";
import { els } from "../dom.js";
import { showToast } from "../widgets/hud.js";
import { setCameraMode } from "./camera.js";
import { runwayShoulder, flattenHeight } from "./runway.js";

/**
 * View engine standar training (Ver 0, Tahap C1).
 *
 * FPV    : kamera di hidung pesawat, orientasi persis attitude (h/p/r).
 * TAIL   : kamera di belakang-atas ekor, roll dikunci 0 (chase stabil).
 * FOLLOW : perilaku lama (trackedEntity + lookAt) — delegasi ke camera.js.
 * GROUND : pengamat statis di darat (POV pilot RC di lapangan), kamera
 *          menoleh mengikuti pesawat. Posisi pengamat DIBEKUKAN saat
 *          view diaktifkan.
 * FREE   : kamera bebas, input mouse user aktif.
 *
 * Catatan konvensi Cesium (jebakan klasik, jangan "dirapikan"):
 * - Transforms.headingPitchRollToFixedFrame: sumbu X frame mengarah TIMUR
 *   pada heading 0 -> perlu offset CONFIG.enuHeadingOffsetDeg (-90) agar
 *   X = arah hidung pesawat.
 * - camera.setView({orientation}): heading dihitung DARI UTARA -> pakai
 *   heading mentah TANPA offset.
 */

export const VIEWS = Object.freeze({
  FPV: "fpv",
  TAIL: "tail",
  FOLLOW: "follow",
  GROUND: "ground",
  FREE: "free"
});

let currentView = VIEWS.FOLLOW;
let groundObserver = null; // Cartesian3, snapshot saat GROUND diaktifkan

// P-GV (Jul 2026): kontrol runtime GROUND view.
// - groundOverride  : {lat, lon} pengamat hasil geser user (null = posisi env/config).
//                     Reset tiap muat halaman -> "setiap run start di wiriadinata.env".
// - groundFovDeg    : zoom teropong (FOV). null = belum di-zoom.
// - groundFovDefault: FOV asli Cesium utk dipulihkan saat keluar GROUND.
// - lastGroundHeading: arah pandang ke pesawat (rad), frame gerak WASD.
let groundOverride = null;
let groundFovDeg = null;
let groundFovDefault = null;
let lastGroundHeading = 0;
let groundControlsAttached = false;

// Scratch objects: dipakai ulang tiap frame (30 Hz), hindari alokasi GC.
const scratch = {
  frame: new Cesium.Matrix4(),
  enuInv: new Cesium.Matrix4(),
  offset: new Cesium.Cartesian3(),
  camPos: new Cesium.Cartesian3(),
  rel: new Cesium.Cartesian3(),
  hpr: new Cesium.HeadingPitchRoll(),
  carto: new Cesium.Cartographic()
};

function setUserInputs(enabled) {
  if (state.viewer) {
    state.viewer.scene.screenSpaceCameraController.enableInputs = enabled;
  }
}

export function getTrainingView() {
  return currentView;
}

export function syncViewButtons() {
  if (!els.viewButtons || els.viewButtons.length === 0) {
    return;
  }
  els.viewButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === currentView);
  });
}

export function setTrainingView(name, silent = false) {
  if (!state.viewer || !Object.values(VIEWS).includes(name)) {
    return;
  }

  currentView = name;
  
  // PASTIKAN KAMERA DILEPASKAN SECARA AMAN SAAT PINDAH VIEW
  releaseCameraTransform();

  if (name === VIEWS.FOLLOW) {
    setUserInputs(true);
    setCameraMode(true, true);
  } else if (name === VIEWS.FREE) {
    setUserInputs(true);
    setCameraMode(false, true);
  } else {
    // View slaved: lepas trackedEntity/transform lama, kunci input user.
    setCameraMode(false, true);
    setUserInputs(false);
    if (name === VIEWS.GROUND) {
      ensureGroundControls();
      groundObserver = computeGroundObserver();
    } else {
      restoreGroundFov();
    }
  }

  if (name === VIEWS.FOLLOW || name === VIEWS.FREE) {
    restoreGroundFov();
  }

  syncViewButtons();

  if (!silent) {
    showToast(`View: ${name.toUpperCase()}`);
  }
}

/** Posisi pengamat GROUND.
 * Prioritas: (1) koordinat GCS TETAP dari CONFIG (mode "Fixed GCS Position"),
 * (2) fallback: dekat home, (3) fallback terakhir: proyeksi darat pesawat. */
function computeGroundObserver() {
  const g = CONFIG.views.ground;
  let lat;
  let lon;
  let alt;
  let latOffset = g.offsetLatDeg;
  let lonOffset = g.offsetLonDeg;

  const shoulder = g.useRunwayShoulder ? runwayShoulder() : null;

  if (groundOverride) {
    // P-GV: posisi hasil geser user (WASD) — menang atas semua sumber lain
    // selama sesi berjalan. Tinggi tetap disnap ke terrain di bawah.
    lat = groundOverride.lat;
    lon = groundOverride.lon;
    alt = 0;
    latOffset = 0;
    lonOffset = 0;
  } else if (shoulder) {
    // P5.5: pengamat berdiri di BAHU landasan, di tengah panjang runway —
    // bukan di tengah aspal (pesawat lewat di depan mata, bukan menembus).
    lat = shoulder.lat;
    lon = shoulder.lon;
    alt = 0; // disnap ke terrain (kini RATA) di bawah
    latOffset = 0;
    lonOffset = 0;
  } else if (g.gcs && Number.isFinite(g.gcs.lat) && Number.isFinite(g.gcs.lon)) {
    // Mode GCS tetap: koordinat eksplisit, tanpa offset arbitrer.
    lat = g.gcs.lat;
    lon = g.gcs.lon;
    alt = Number.isFinite(g.gcs.altMsl) ? g.gcs.altMsl : 0;
    latOffset = 0;
    lonOffset = 0;
  } else if (Number.isFinite(state.home.lat) && Number.isFinite(state.home.lon)) {
    lat = state.home.lat;
    lon = state.home.lon;
    alt = Number.isFinite(state.home.alt) ? state.home.alt : 0;
  } else if (state.telemetry.lat !== null && state.telemetry.lon !== null) {
    lat = Number(state.telemetry.lat);
    lon = Number(state.telemetry.lon);
    const msl = Number(state.telemetry.alt_msl ?? 0);
    const agl = Number(state.telemetry.agl ?? 0);
    alt = msl - (Number.isFinite(agl) ? agl : 0);
  } else {
    return null;
  }

  // Koreksi ke tinggi terrain aktual bila tile sudah termuat
  // (kecuali altMsl GCS diberikan eksplisit).
  const carto = Cesium.Cartographic.fromDegrees(
    lon + lonOffset,
    lat + latOffset,
    0,
    scratch.carto
  );
  const rawTerrainH = state.viewer.scene.globe.getHeight(carto);
  const terrainH = flattenHeight(rawTerrainH, lon + lonOffset, lat + latOffset);
  const gcsAltExplicit =
    !groundOverride && !shoulder && g.gcs && Number.isFinite(g.gcs.altMsl);
  if (Number.isFinite(terrainH) && !gcsAltExplicit) {
    alt = terrainH;
  }

  return Cesium.Cartesian3.fromDegrees(
    lon + lonOffset,
    lat + latOffset,
    alt + g.eyeHeightMeters
  );
}

/** P-RES: tolak posisi non-finite. Saat terrain gagal (Cesium Ion down),
 * globe.getHeight() -> undefined dan perhitungan bisa menghasilkan NaN;
 * camera.setView(NaN) melempar error tiap frame dan mematikan seluruh
 * kamera GROUND (termasuk zoom). Lebih baik lewati frame ini. */
function isFinitePosition(p) {
  return (
    p instanceof Cesium.Cartesian3 &&
    Number.isFinite(p.x) &&
    Number.isFinite(p.y) &&
    Number.isFinite(p.z)
  );
}

/**
 * Dipanggil dari updateAircraftOnMap() setiap frame telemetri (30 Hz).
 * @param {Cesium.Cartesian3} position posisi visual pesawat (world)
 * @param {{headingDeg:number, pitchDeg:number, rollDeg:number}} pose
 */
export function updateViewCamera(position, pose) {
  if (!state.viewer || !position) {
    return;
  }

  if (currentView === VIEWS.TAIL) {
    const tail = CONFIG.views.tail;
    chaseCamera(position, pose, tail.offsetMeters, {
      rollStabilize: !tail.followRoll,
      pitchStabilize: tail.stabilizePitch === true
    });
    return;
  }

  if (currentView === VIEWS.FPV) {
    fpvCamera(position, pose, CONFIG.views.fpv.offsetMeters);
    return;
  }

  if (currentView === VIEWS.GROUND) {
    updateGroundCamera(position);
  }
}

function chaseCamera(position, pose, offset, opts) {
  const stabRoll = opts && opts.rollStabilize;
  const stabPitch = opts && opts.pitchStabilize;

  scratch.hpr.heading = Cesium.Math.toRadians(
    (pose.headingDeg ?? 0) + CONFIG.enuHeadingOffsetDeg
  );
  scratch.hpr.pitch = Cesium.Math.toRadians(stabPitch ? 0 : (pose.pitchDeg ?? 0));
  scratch.hpr.roll = Cesium.Math.toRadians(stabRoll ? 0 : (pose.rollDeg ?? 0));

  const frame = Cesium.Transforms.headingPitchRollToFixedFrame(
    position,
    scratch.hpr,
    Cesium.Ellipsoid.WGS84,
    undefined,
    scratch.frame
  );

  // offset {forward,right,up} meter di frame body (+X depan, +Y kiri, +Z atas).
  scratch.offset.x = offset.forward;
  scratch.offset.y = -offset.right;
  scratch.offset.z = offset.up;

  // Kamera diikat ke frame pesawat, menatap origin (pesawat). enableInputs
  // sudah false di view slaved, jadi lock transform ini aman.
  state.viewer.camera.lookAtTransform(frame, scratch.offset);
}

/**
 * FPV cam RIGID-BY-CONSTRUCTION.
 * Mengikat kamera ke frame pesawat tetapi diset untuk menatap lurus ke depan
 * (sumbu +X lokal), bukan menatap ke origin seperti chaseCamera.
 */
function fpvCamera(position, pose, offset) {
  scratch.hpr.heading = Cesium.Math.toRadians(
    (pose.headingDeg ?? 0) + CONFIG.enuHeadingOffsetDeg
  );
  scratch.hpr.pitch = Cesium.Math.toRadians(pose.pitchDeg ?? 0);
  scratch.hpr.roll = Cesium.Math.toRadians(pose.rollDeg ?? 0);

  const frame = Cesium.Transforms.headingPitchRollToFixedFrame(
    position,
    scratch.hpr,
    Cesium.Ellipsoid.WGS84,
    undefined,
    scratch.frame
  );

  // Kunci koordinat lingkungan ke badan pesawat
  state.viewer.camera.lookAtTransform(frame);

  // Set posisi kamera di hidung pesawat (lokal: +X depan, -Y kanan, +Z atas)
  state.viewer.camera.position = new Cesium.Cartesian3(
    offset.forward,
    -offset.right,
    offset.up
  );

  // Paksa kamera menatap lurus ke depan sumbu pesawat (+X)
  state.viewer.camera.direction = Cesium.Cartesian3.UNIT_X;
  state.viewer.camera.up = Cesium.Cartesian3.UNIT_Z;
  state.viewer.camera.right = new Cesium.Cartesian3(0, -1, 0);
}

/** Kamera diam di pengamat, heading/pitch menoleh ke pesawat. */
function updateGroundCamera(aircraftPosition) {
  if (!groundObserver) {
    groundObserver = computeGroundObserver();
  }
  if (!isFinitePosition(groundObserver) || !isFinitePosition(aircraftPosition)) {
    return; // P-RES: terrain belum siap / gagal — jangan rusak kamera
  }

  const enu = Cesium.Transforms.eastNorthUpToFixedFrame(
    groundObserver,
    Cesium.Ellipsoid.WGS84,
    scratch.frame
  );
  const enuInv = Cesium.Matrix4.inverseTransformation(enu, scratch.enuInv);
  const rel = Cesium.Matrix4.multiplyByPoint(enuInv, aircraftPosition, scratch.rel);

  const headingRad = Math.atan2(rel.x, rel.y); // atan2(timur, utara): searah jarum jam dari utara
  const horiz = Math.hypot(rel.x, rel.y);
  const pitchRad = Math.atan2(rel.z, horiz);

  lastGroundHeading = headingRad; // P-GV: frame acuan gerak WASD

  state.viewer.camera.setView({
    destination: groundObserver,
    orientation: { heading: headingRad, pitch: pitchRad, roll: 0 }
  });

  // P-GV: zoom teropong — FOV dipaksa tiap frame (setView bisa meresetnya).
  if (groundFovDeg !== null && state.viewer.camera.frustum.fov !== undefined) {
    state.viewer.camera.frustum.fov = Cesium.Math.toRadians(groundFovDeg);
  }
}

/* ================= P-GV: kontrol runtime GROUND view (Jul 2026) =================
 * Zoom : roda mouse = teropong (FOV), posisi TIDAK berpindah, arah tetap
 *        terkunci ke pesawat. Rentang default 65..2 derajat (~32x).
 * Geser: W/S = mendekati/menjauhi pesawat (horizontal), A/D = geser samping,
 *        tombol panah setara, Shift = langkah besar, R = reset ke posisi
 *        wiriadinata.env + zoom normal. Tinggi mata selalu disnap ke terrain.
 * Posisi hasil geser hanya bertahan selama sesi (reload = kembali ke env).
 */
function groundZoomCfg() {
  const z = (CONFIG.views.ground && CONFIG.views.ground.zoom) || {};
  return {
    minFovDeg: Number.isFinite(z.minFovDeg) ? z.minFovDeg : 2,
    maxFovDeg: Number.isFinite(z.maxFovDeg) ? z.maxFovDeg : 65,
    wheelFactor: Number.isFinite(z.wheelFactor) ? z.wheelFactor : 1.15
  };
}

function groundMoveStep(fast) {
  const g = CONFIG.views.ground || {};
  const base = Number.isFinite(g.moveStepMeters) ? g.moveStepMeters : 2;
  const big = Number.isFinite(g.moveStepFastMeters) ? g.moveStepFastMeters : 10;
  return fast ? big : base;
}

function currentObserverLatLon() {
  if (groundOverride) {
    return { lat: groundOverride.lat, lon: groundOverride.lon };
  }
  if (groundObserver) {
    const c = Cesium.Cartographic.fromCartesian(groundObserver, Cesium.Ellipsoid.WGS84, scratch.carto);
    return { lat: Cesium.Math.toDegrees(c.latitude), lon: Cesium.Math.toDegrees(c.longitude) };
  }
  return null;
}

function moveGroundObserver(forwardM, rightM) {
  const cur = currentObserverLatLon();
  if (!cur) {
    return;
  }
  const h = lastGroundHeading;
  const dEast = forwardM * Math.sin(h) + rightM * Math.cos(h);
  const dNorth = forwardM * Math.cos(h) - rightM * Math.sin(h);
  const lat = cur.lat + dNorth / 111320;
  const lon = cur.lon + dEast / (111320 * Math.cos(Cesium.Math.toRadians(cur.lat)));
  groundOverride = { lat, lon };
  groundObserver = computeGroundObserver();
}

function resetGroundObserver() {
  groundOverride = null;
  groundObserver = computeGroundObserver();
  const cam = state.viewer && state.viewer.camera;
  if (groundFovDefault !== null && cam && cam.frustum.fov !== undefined) {
    cam.frustum.fov = groundFovDefault;
  }
  groundFovDeg = null;
  showToast("Ground view: posisi & zoom di-reset");
}

function restoreGroundFov() {
  const cam = state.viewer && state.viewer.camera;
  if (groundFovDefault !== null && cam && cam.frustum.fov !== undefined) {
    cam.frustum.fov = groundFovDefault;
  }
  groundFovDeg = null;
}

function onGroundWheel(e) {
  if (currentView !== VIEWS.GROUND || !state.viewer) {
    return;
  }
  e.preventDefault();
  const cam = state.viewer.camera;
  if (cam.frustum.fov === undefined) {
    return; // frustum ortho — tidak berlaku
  }
  const z = groundZoomCfg();
  if (groundFovDefault === null) {
    groundFovDefault = cam.frustum.fov;
  }
  if (groundFovDeg === null) {
    groundFovDeg = Cesium.Math.toDegrees(cam.frustum.fov);
  }
  groundFovDeg =
    e.deltaY > 0 ? groundFovDeg * z.wheelFactor : groundFovDeg / z.wheelFactor;
  groundFovDeg = Math.min(z.maxFovDeg, Math.max(z.minFovDeg, groundFovDeg));
  cam.frustum.fov = Cesium.Math.toRadians(groundFovDeg);
}

function onGroundKey(e) {
  if (currentView !== VIEWS.GROUND) {
    return;
  }
  const t = e.target;
  if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) {
    return; // jangan bajak ketikan user di form
  }
  const step = groundMoveStep(e.shiftKey);
  switch (e.key.toLowerCase()) {
    case "w": case "arrowup":    moveGroundObserver(step, 0);  break;
    case "s": case "arrowdown":  moveGroundObserver(-step, 0); break;
    case "a": case "arrowleft":  moveGroundObserver(0, -step); break;
    case "d": case "arrowright": moveGroundObserver(0, step);  break;
    case "r": resetGroundObserver(); return;
    default: return;
  }
  e.preventDefault();
}

function ensureGroundControls() {
  if (groundControlsAttached || !state.viewer) {
    return;
  }
  groundControlsAttached = true;
  state.viewer.scene.canvas.addEventListener("wheel", onGroundWheel, { passive: false });
  document.addEventListener("keydown", onGroundKey);
}

/**
 * Driver kamera slaved di dalam render pipeline. Dipasang sekali ke
 * scene.preRender (60 fps) saat init map. Membaca pose terbaru yang di-cache
 * updateAircraftOnMap (30 Hz) dan meng-apply-nya SETIAP frame render sehingga
 * kamera & entity dijamin lockstep (bukan di callback telemetri async).
 * No-op utk FOLLOW/FREE (updateViewCamera sudah menyaring view).
 */

/**
 * Driver kamera slaved di dalam render pipeline.
 */
export function renderSlavedCamera() {
  if (currentView === VIEWS.FOLLOW || currentView === VIEWS.FREE) {
    return;
  }

  const c = state.lastCameraPose;
  if (!c || !c.position) {
    return;
  }
  
  updateViewCamera(c.position, {
    headingDeg: c.headingDeg,
    pitchDeg: c.pitchDeg,
    rollDeg: c.rollDeg
  });
}
/** * Melepaskan kamera dari frame pesawat tanpa menteleportasinya ke tengah bumi.
 */
function releaseCameraTransform() {
  const cam = state.viewer.camera;
  if (Cesium.Matrix4.equals(cam.transform, Cesium.Matrix4.IDENTITY)) {
    return; // Sudah terlepas
  }
  
  // Simpan posisi & orientasi absolut dunia (World Coordinates)
  const pos = cam.positionWC.clone();
  const dir = cam.directionWC.clone();
  const up = cam.upWC.clone();
  const right = cam.rightWC.clone();

  // Lepaskan ikatan frame dari pesawat
  cam.lookAtTransform(Cesium.Matrix4.IDENTITY);

  // Kembalikan kamera ke posisi dunianya yang benar
  cam.position = pos;
  cam.direction = dir;
  cam.up = up;
  cam.right = right;
}