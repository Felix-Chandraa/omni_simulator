import { CONFIG } from "../config.js";
import { flattenHeight, updateGeoidOffset } from "./runway.js";
import { updateControlSurfaces } from "./surfaces.js";
import { state } from "../state.js";

export function createAircraftEntities() {
  const m = CONFIG.aircraftModel;
  state.entities.aircraft = state.viewer.entities.add({
    position: Cesium.Cartesian3.fromDegrees(0, 0, 1000),
    model: {
      uri: m.uri ?? CONFIG.aircraftModelUri,
      scale: m.scale,
      minimumPixelSize: m.minimumPixelSize,
      maximumScale: m.maximumScale,
      runAnimations: false
      // TANPA heightReference: posisi entity absolut (terrain+AGL dihitung
      // sinkron di updateAircraftOnMap). RELATIVE_TO_GROUND meng-clamp
      // ASINKRON -> model tertinggal dari kamera (rasa "pegas") dan tinggi
      // render tidak konsisten dengan perhitungan kita.
    }
  });

  state.entities.trail = state.viewer.entities.add({
    polyline: {
      positions: new Cesium.CallbackProperty(() => state.trailPositions, false),
      width: CONFIG.trailWidth,
      material: Cesium.Color.GREEN.withAlpha(0.9),
      clampToGround: false
    }
  });

  state.entities.groundTrail = state.viewer.entities.add({
    polyline: {
      positions: new Cesium.CallbackProperty(() => state.trailPositions, false),
      width: CONFIG.trailWidth,
      material: Cesium.Color.GREEN.withAlpha(0.9),
      clampToGround: true
    }
  });

  state.entities.fallbackAircraft = state.viewer.entities.add({
    position: Cesium.Cartesian3.fromDegrees(0, 0, 1000),
    point: {
      pixelSize: 12,
      color: Cesium.Color.YELLOW,
      outlineColor: Cesium.Color.BLACK,
      outlineWidth: 2,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND
    },
    label: {
      text: "AIRCRAFT",
      font: "14px sans-serif",
      fillColor: Cesium.Color.WHITE,
      outlineColor: Cesium.Color.BLACK,
      outlineWidth: 2,
      style: Cesium.LabelStyle.FILL_AND_OUTLINE,
      pixelOffset: new Cesium.Cartesian2(0, -24),
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND
    }
  });

  state.entities.fallbackAircraft.show = false;
}

/**
 * Fallback tinggi visual saat tile terrain BELUM termuat.
 *
 * BUG P5.5 (diperbaiki): dulu memakai alt_msl MENTAH. SITL memakai MSL
 * (EGM96, spawn 349 m) sedangkan Cesium memakai DEM-nya sendiri (357 m di
 * titik yang sama) -> pesawat spawn melayang / terkubur ~8 m.
 *
 * Aturan: posisi visual TIDAK PERNAH digerakkan MSL mentah. Urutan sumber:
 *   1. slab runway (bila sudah terukur)  -> paling akurat di lapangan
 *   2. MSL + offset geoid (bila terukur) -> di luar area runway
 *   3. MSL apa adanya                    -> upaya terakhir
 */
function fallbackHeight(mslAlt, agl) {
  const slab = state.runway && state.runway.elevM;
  if (Number.isFinite(slab)) {
    return slab + (Number.isFinite(agl) ? agl : 0);
  }

  const off = state.geoid && state.geoid.offsetM;
  if (Number.isFinite(off) && Number.isFinite(mslAlt)) {
    return mslAlt + off;
  }

  return mslAlt;
}

export function updateAircraftOnMap() {
  if (
    !state.viewer ||
    state.telemetry.lat === null ||
    state.telemetry.lon === null
  ) {
    return;
  }

  if (!state.entities.aircraft || !state.entities.fallbackAircraft) {
    return;
  }

  const t = state.telemetry;

  const lat = Number(t.lat);
  const lon = Number(t.lon);

  if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
    return;
  }

  const relAlt = Math.max(Number(t.alt ?? 0), 0);
  const homeAlt = Number.isFinite(state.home.alt) ? state.home.alt : 0;
  const mslAlt = Number(t.alt_msl ?? relAlt);
  const trailAlt = Math.max(mslAlt - homeAlt, 0);

  // Kanal vertikal: saat pose_source == "fg", pakai AGL dari FG stream
  // (30 Hz). t.alt = relative alt MAVLink (5 Hz) -> hanya fallback.
  const agl = Number(t.agl);
  const heightAboveGround =
    t.pose_source === "fg" && Number.isFinite(agl)
      ? Math.max(agl, 0)
      : relAlt;

  // POSISI TUNGGAL (sumber kebenaran satu): tinggi terrain (sinkron via
  // globe.getHeight) + AGL + clearance. Entity ditempatkan ABSOLUT di sini
  // (tanpa heightReference) dan kamera memakai Cartesian yang SAMA —
  // model & kamera rigid lockstep, bebas lag clamp asinkron.
  // P5.5: tinggi MENTAH dari mesh, lalu diratakan bila di area runway
  // (fungsi murni, dipakai bersama jalur async di core/terrain.js).
  const rawGroundH = state.viewer.scene.globe.getHeight(
    Cesium.Cartographic.fromDegrees(lon, lat)
  );
  const groundH = flattenHeight(rawGroundH, lon, lat);

  // Kalibrasi offset geoid: BERPENJAGA di dalam updateGeoidOffset (hanya saat
  // di darat, diam, pose FG, hasil masuk akal). Bug P5.5b: menerima telemetri
  // sampah pasca-crash -> offset -10783 m.
  if (Number.isFinite(rawGroundH)) {
    updateGeoidOffset(rawGroundH, t);
  }
  const visualHeight = Number.isFinite(groundH)
    ? groundH + heightAboveGround + CONFIG.aircraftModel.groundClearanceMeters
    : fallbackHeight(mslAlt, heightAboveGround) +
      CONFIG.aircraftModel.groundClearanceMeters; // tile belum termuat
  const visualPosition = Cesium.Cartesian3.fromDegrees(lon, lat, visualHeight);

  const trailPosition = Cesium.Cartesian3.fromDegrees(
    lon,
    lat,
    Number.isFinite(groundH) ? visualHeight : trailAlt
  );

  state.lastPosition = visualPosition;

  const hpr = new Cesium.HeadingPitchRoll(
    Cesium.Math.toRadians((t.hdg ?? 0) + CONFIG.enuHeadingOffsetDeg),
    Cesium.Math.toRadians(t.pitch ?? 0),
    Cesium.Math.toRadians(t.roll ?? 0)
  );

  // Kompensasi origin glb: geser ENTITY berlawanan arah offset mesh,
  // dihitung di frame badan pesawat (ikut berotasi -> orbit hilang).
  // Kamera/trail TIDAK ikut digeser: visualPosition = posisi pesawat sejati.
  const mo = CONFIG.aircraftModel.meshOffsetMeters;
  let entityPosition = visualPosition;
  if (mo && (mo.forward || mo.right || mo.up)) {
    const frame = Cesium.Transforms.headingPitchRollToFixedFrame(
      visualPosition,
      hpr
    );
    entityPosition = Cesium.Matrix4.multiplyByPoint(
      frame,
      new Cesium.Cartesian3(-mo.forward, mo.right, -mo.up),
      new Cesium.Cartesian3()
    );
  }

  state.entities.aircraft.show = true;
  updateControlSurfaces();
  updateControlSurfaces();
  state.entities.fallbackAircraft.show = false;
  state.entities.aircraft.position = entityPosition;

  // Kalibrasi sumbu model (C3): komposisi quaternion di body frame.
  // Penjumlahan Euler mentah SALAH utk offset pitch/roll saat manuver.
  // Kamera FPV/tail tetap pakai pose mentah — fix ini murni kosmetik model.
  const poseQuat = Cesium.Transforms.headingPitchRollQuaternion(
    entityPosition,
    hpr
  );
  const mc = CONFIG.aircraftModel;
  if (mc.headingOffsetDeg || mc.pitchOffsetDeg || mc.rollOffsetDeg) {
    const fix = Cesium.Quaternion.fromHeadingPitchRoll(
      new Cesium.HeadingPitchRoll(
        Cesium.Math.toRadians(mc.headingOffsetDeg),
        Cesium.Math.toRadians(mc.pitchOffsetDeg),
        Cesium.Math.toRadians(mc.rollOffsetDeg)
      )
    );
    state.entities.aircraft.orientation = Cesium.Quaternion.multiply(
      poseQuat,
      fix,
      new Cesium.Quaternion()
    );
  } else {
    state.entities.aircraft.orientation = poseQuat;
  }

  pushTrailPoint(trailPosition);

  state.lastCameraPose = {
    position: visualPosition,
    headingDeg: t.hdg ?? 0,
    pitchDeg: t.pitch ?? 0,
    rollDeg: t.roll ?? 0
  };
}

export function pushTrailPoint(position) {
  const last = state.trailPositions[state.trailPositions.length - 1];

  if (
    !last ||
    Cesium.Cartesian3.distance(last, position) > CONFIG.trailMinDistance
  ) {
    state.trailPositions.push(Cesium.Cartesian3.clone(position));

    if (state.trailPositions.length > CONFIG.trailMaxPoints) {
      state.trailPositions.shift();
    }
  }
}

export function setVehiclePosition(lat, lon, alt, heading, roll, pitch) {
  if (lat === null || lon === null || alt === null) {
    return;
  }

  if (!state.viewer) {
    return;
  }

  state.telemetry.lat = Number(lat);
  state.telemetry.lon = Number(lon);
  state.telemetry.alt = Number(alt);
  state.telemetry.hdg = heading ?? state.telemetry.hdg ?? 0;
  state.telemetry.roll = roll ?? state.telemetry.roll ?? 0;
  state.telemetry.pitch = pitch ?? state.telemetry.pitch ?? 0;
  state.telemetry.yaw = heading ?? state.telemetry.yaw ?? state.telemetry.hdg ?? 0;

  updateAircraftOnMap();
}