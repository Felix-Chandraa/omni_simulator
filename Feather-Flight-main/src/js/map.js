import { CONFIG } from "./config.js";
import { state } from "./state.js";
import { els } from "./dom.js";
import { setLoading, showToast } from "./ui.js";
import { createAircraftEntities, updateAircraftOnMap } from "./aircraft.js";
import { updateHomeMarker, ensureHomeReady } from "./home.js";

export async function initMap() {
  try {
    setLoading(true, CONFIG.terrainLoadingText);

    Cesium.Ion.defaultAccessToken = CONFIG.cesiumIonAccessToken;

    state.viewer = new Cesium.Viewer("map", {
      terrain: Cesium.Terrain.fromWorldTerrain({
        requestVertexNormals: true,
        requestWaterMask: true
      }),
      animation: false,
      timeline: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      baseLayerPicker: false,
      navigationHelpButton: false,
      fullscreenButton: false,
      infoBox: false,
      selectionIndicator: false,
      shouldAnimate: true,
      scene3DOnly: true
    });

    state.viewer.scene.globe.depthTestAgainstTerrain = true;
    state.viewer.scene.globe.enableLighting = false;
    state.viewer.scene.skyAtmosphere.show = true;

    createAircraftEntities();

    state.viewer.scene.globe.tileLoadProgressEvent.addEventListener(
      (remaining) => {
        const text =
          remaining === 0
            ? CONFIG.terrainReadyText
            : `Loading terrain... (${remaining})`;

        els.terrainStatusText.textContent = text;
        els.loadingText.textContent = text;

        if (remaining === 0) {
          setTerrainReady();
        }
      }
    );

    const home = Cesium.Cartesian3.fromDegrees(
      CONFIG.home.lon,
      CONFIG.home.lat,
      CONFIG.home.alt
    );

    state.viewer.camera.flyTo({
      destination: home,
      duration: 0.1
    });

    setTimeout(() => {
      state.viewer.camera.setView({
        destination: Cesium.Cartesian3.fromDegrees(
          CONFIG.home.lon,
          CONFIG.home.lat,
          CONFIG.home.alt + CONFIG.camera.homeViewHeightMeters
        ),
        orientation: {
          heading: Cesium.Math.toRadians(0),
          pitch: Cesium.Math.toRadians(-35),
          roll: 0
        }
      });
    }, 250);

    updateHomeMarker();
    updateAircraftOnMap();
  } catch (error) {
    console.error("Map initialization failed:", error);
    setLoading(true, "Failed to load terrain");
    showToast("Map failed to initialize", true);
  }
}

export function setTerrainReady() {
  if (state.terrainReady) {
    return;
  }

  state.terrainReady = true;

  els.titleText.textContent = CONFIG.title;
  els.terrainStatusText.textContent = CONFIG.terrainReadyText;

  setLoading(false, CONFIG.terrainReadyText);

  if (
    Number.isFinite(state.home.lat) &&
    Number.isFinite(state.home.lon) &&
    !Number.isFinite(state.home.alt)
  ) {
    ensureHomeReady().catch(() => {});
  }

  showToast("3D terrain ready");
}
