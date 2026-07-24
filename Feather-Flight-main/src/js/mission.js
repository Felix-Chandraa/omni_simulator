import { state } from "./state.js";
import { setHomePosition } from "./home.js";

export function normalizeWaypoint(wp) {
  if (Array.isArray(wp)) {
    return {
      seq: Number(wp[3] ?? 0),
      lat: Number(wp[0]),
      lon: Number(wp[1]),
      alt: Number(wp[2] ?? 0)
    };
  }

  return {
    seq: Number(wp.seq ?? wp.index ?? 0),
    lat: Number(wp.lat ?? wp.latitude ?? wp.y ?? 0),
    lon: Number(wp.lon ?? wp.lng ?? wp.longitude ?? wp.x ?? 0),
    alt: Number(wp.alt ?? wp.altitude ?? wp.z ?? 0)
  };
}

export function setMissionPath(points) {
  if (!state.viewer) {
    return;
  }

  if (state.entities.mission) {
    state.viewer.entities.remove(state.entities.mission);
    state.entities.mission = null;
  }

  state.entities.waypoints.forEach((entity) => {
    state.viewer.entities.remove(entity);
  });

  state.entities.waypoints = [];

  if (!points || points.length === 0) {
    return;
  }

  const normalized = points
    .map(normalizeWaypoint)
    .filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lon));

  if (normalized.length === 0) {
    return;
  }

  normalized.sort((a, b) => a.seq - b.seq);

  const homeWp = normalized.find((p) => p.seq === 0) || normalized[0];
  const homeAlt = Number(homeWp.alt || 0);

  const resolved = normalized.map((p) => ({
    seq: p.seq,
    lat: p.lat,
    lon: p.lon,
    alt: p.seq === 0 ? p.alt : homeAlt + p.alt
  }));

  const positions = resolved.map((p) =>
    Cesium.Cartesian3.fromDegrees(p.lon, p.lat, p.alt || 0)
  );

  state.entities.mission = state.viewer.entities.add({
    polyline: {
      positions,
      width: 4,
      material: Cesium.Color.CYAN
    }
  });

  resolved.forEach((p, index) => {
    const position = Cesium.Cartesian3.fromDegrees(
      p.lon,
      p.lat,
      p.alt || 0
    );

    const entity = state.viewer.entities.add({
      position,
      point: {
        pixelSize: index === 0 ? 12 : 8,
        color: index === 0 ? Cesium.Color.LIME : Cesium.Color.ORANGE,
        outlineColor: Cesium.Color.BLACK,
        outlineWidth: 2
      },
      label: {
        text: index === 0 ? "HOME" : `WP ${p.seq}`,
        font: "12px monospace",
        fillColor: Cesium.Color.WHITE,
        outlineColor: Cesium.Color.BLACK,
        outlineWidth: 2,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        pixelOffset: new Cesium.Cartesian2(0, -20)
      }
    });

    state.entities.waypoints.push(entity);
  });

  if (
    !Number.isFinite(state.home.lat) ||
    !Number.isFinite(state.home.lon)
  ) {
    const first = resolved[0];

    setHomePosition(first.lat, first.lon, first.alt || null, "mission").catch(
      () => {}
    );
  }

  state.viewer.zoomTo(state.entities.mission).catch(() => {});
}
