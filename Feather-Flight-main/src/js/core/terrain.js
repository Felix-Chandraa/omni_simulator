import { state } from "../state.js";
import { flattenHeight } from "./runway.js";

export async function sampleTerrainHeight(lat, lon) {
  if (!state.viewer) {
    return null;
  }

  const key = `${Number(lat).toFixed(5)},${Number(lon).toFixed(5)}`;

  // Cache menyimpan nilai MENTAH (SDD 8.6a) — perataan diterapkan SETELAH
  // cache, sehingga elevM yang berubah tidak menghasilkan nilai basi.
  if (sampleTerrainHeight.cache.has(key)) {
    return flattenHeight(sampleTerrainHeight.cache.get(key), Number(lon), Number(lat));
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
      return flattenHeight(height, Number(lon), Number(lat));
    }
  } catch (error) {
    // Fallback below.
  }

  try {
    const height = state.viewer.scene.globe.getHeight(carto);

    if (Number.isFinite(height)) {
      sampleTerrainHeight.cache.set(key, height);
      return flattenHeight(height, Number(lon), Number(lat));
    }
  } catch (error) {
    // Ignore and return null.
  }

  return null;
}

sampleTerrainHeight.cache = new Map();
