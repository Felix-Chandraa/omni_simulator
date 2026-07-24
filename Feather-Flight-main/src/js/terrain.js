import { state } from "./state.js";

export async function sampleTerrainHeight(lat, lon) {
  if (!state.viewer) {
    return null;
  }

  const key = `${Number(lat).toFixed(5)},${Number(lon).toFixed(5)}`;

  if (sampleTerrainHeight.cache.has(key)) {
    return sampleTerrainHeight.cache.get(key);
  }

  const carto = Cesium.Cartographic.fromDegrees(Number(lon), Number(lat));

  try {
    const updated = await Cesium.sampleTerrainMostDetailed(
      state.viewer.terrainProvider,
      [carto]
    );

    const height = updated && updated[0] ? updated[0].height : null;

    if (Number.isFinite(height)) {
      sampleTerrainHeight.cache.set(key, height);
      return height;
    }
  } catch (error) {
    // Fallback below.
  }

  try {
    const height = state.viewer.scene.globe.getHeight(carto);

    if (Number.isFinite(height)) {
      sampleTerrainHeight.cache.set(key, height);
      return height;
    }
  } catch (error) {
    // Ignore and return null.
  }

  return null;
}

sampleTerrainHeight.cache = new Map();
