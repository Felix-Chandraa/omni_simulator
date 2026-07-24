import { state } from "./state.js";
import { homeKey } from "./format.js";
import { sampleTerrainHeight } from "./terrain.js";
import { showToast } from "./ui.js";

export function updateHomeMarker() {
  if (!state.viewer) {
    return;
  }

  const hasHome =
    Number.isFinite(state.home.lat) &&
    Number.isFinite(state.home.lon);

  if (!hasHome) {
    if (state.entities.home) {
      state.entities.home.show = false;
    }

    return;
  }

  const alt = Number.isFinite(state.home.alt) ? state.home.alt : 0;

  const position = Cesium.Cartesian3.fromDegrees(
    state.home.lon,
    state.home.lat,
    alt
  );

  if (!state.entities.home) {
    state.entities.home = state.viewer.entities.add({
      position,
      point: {
        pixelSize: 11,
        color: Cesium.Color.CYAN,
        outlineColor: Cesium.Color.BLACK,
        outlineWidth: 2,
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND
      },
      label: {
        text: "HOME",
        font: "13px sans-serif",
        fillColor: Cesium.Color.CYAN,
        outlineColor: Cesium.Color.BLACK,
        outlineWidth: 2,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        pixelOffset: new Cesium.Cartesian2(0, -24),
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND
      }
    });
  } else {
    state.entities.home.position = position;
    state.entities.home.show = true;
  }
}

export async function setHomePosition(lat, lon, alt = null, source = "gps") {
  const nLat = Number(lat);
  const nLon = Number(lon);

  if (!Number.isFinite(nLat) || !Number.isFinite(nLon)) {
    return;
  }

  const key = homeKey(nLat, nLon, source);

  if (state.home.key === key) {
    if (Number.isFinite(alt) && !Number.isFinite(state.home.alt)) {
      state.home.alt = Number(alt);
      updateHomeMarker();
    }

    return state.home;
  }

  const version = (state.home.version || 0) + 1;

  state.home = {
    lat: nLat,
    lon: nLon,
    alt: Number.isFinite(alt) ? Number(alt) : null,
    source,
    key,
    version,
    samplePromise: null
  };

  updateHomeMarker();

  if (state.viewer) {
    state.home.samplePromise = (async () => {
      const terrainAlt = await sampleTerrainHeight(nLat, nLon);

      if (state.home.version !== version) {
        return state.home;
      }

      if (Number.isFinite(terrainAlt)) {
        state.home.alt = terrainAlt;
        updateHomeMarker();
      }

      return state.home;
    })().catch(() => state.home);
  }

  if (source && source !== "mission" && source !== "default") {
    showToast(`Home updated (${source})`);
  }

  return state.home;
}

export async function ensureHomeReady() {
  if (
    !Number.isFinite(state.home.lat) ||
    !Number.isFinite(state.home.lon)
  ) {
    return null;
  }

  if (state.home.samplePromise) {
    try {
      await state.home.samplePromise;
    } catch (error) {
      // Ignore.
    }
  }

  if (!Number.isFinite(state.home.alt)) {
    const terrainAlt = await sampleTerrainHeight(
      state.home.lat,
      state.home.lon
    );

    if (Number.isFinite(terrainAlt)) {
      state.home.alt = terrainAlt;
      updateHomeMarker();
    }
  }

  return state.home;
}

export function maybeUpdateHomeFromTelemetry(data) {
  const lat = data.home_lat ?? data.homeLat;
  const lon = data.home_lon ?? data.homeLon;

  if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
    return;
  }

  const source = data.home_source ?? data.homeSource ?? "gps";
  const alt = data.home_alt ?? data.homeAlt ?? null;
  const key = homeKey(lat, lon, source);

  if (state.home.key === key) {
    if (!Number.isFinite(state.home.alt) && Number.isFinite(alt)) {
      setHomePosition(lat, lon, alt, source).catch((error) => {
        console.error("Home update failed:", error);
      });
    }

    return;
  }

  setHomePosition(lat, lon, alt, source).catch((error) => {
    console.error("Home update failed:", error);
  });
}
