import { CONFIG } from "./config.js";
import { state } from "./state.js";

export function createAircraftEntities() {
  state.entities.aircraft = state.viewer.entities.add({
    position: Cesium.Cartesian3.fromDegrees(0, 0, 1000),
    model: {
      uri: CONFIG.aircraftModelUri,
      scale: 3.0,
      minimumPixelSize: 48,
      maximumScale: 250,
      runAnimations: false,
      heightReference: Cesium.HeightReference.RELATIVE_TO_GROUND
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

  const aircraftPosition = Cesium.Cartesian3.fromDegrees(
    lon,
    lat,
    relAlt + CONFIG.aircraftAltitudeOffset
  );

  const trailPosition = Cesium.Cartesian3.fromDegrees(
    lon,
    lat,
    trailAlt + CONFIG.aircraftAltitudeOffset
  );

  state.lastPosition = aircraftPosition;

  state.entities.aircraft.show = true;
  state.entities.fallbackAircraft.show = false;
  state.entities.aircraft.position = aircraftPosition;

  const hpr = new Cesium.HeadingPitchRoll(
    Cesium.Math.toRadians((t.hdg ?? 0) - 90),
    Cesium.Math.toRadians(t.pitch ?? 0),
    Cesium.Math.toRadians(t.roll ?? 0)
  );

  state.entities.aircraft.orientation =
    Cesium.Transforms.headingPitchRollQuaternion(aircraftPosition, hpr);

  pushTrailPoint(trailPosition);
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
