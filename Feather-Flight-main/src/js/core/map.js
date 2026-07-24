import { CONFIG } from "../config.js";
import { state } from "../state.js";
import { els } from "../dom.js";
import { setLoading, showToast } from "../widgets/hud.js";
import { createAircraftEntities, updateAircraftOnMap } from "./aircraft.js";
import { updateHomeMarker, ensureHomeReady } from "./home.js";
import { measureRunwayElevation, buildRunwaySlab } from "./runway.js";
import { renderSlavedCamera, initGroundObserverMarker } from "./views.js";

export async function initMap() {
  try {
    setLoading(true, CONFIG.terrainLoadingText);

    Cesium.Ion.defaultAccessToken = CONFIG.cesiumIonAccessToken;

    // P-RES (Jul 2026): terrain dibuat sebagai variabel agar errorEvent-nya
    // bisa dipantau. Bila Cesium Ion gagal (token dicabut / kuota bulanan
    // habis / offline), aplikasi TIDAK boleh lumpuh: jatuh ke terrain
    // ellipsoid + citra OpenStreetMap yang tidak butuh Ion.
    const worldTerrain = Cesium.Terrain.fromWorldTerrain({
      requestVertexNormals: true,
      requestWaterMask: true
    });

    state.viewer = new Cesium.Viewer("map", {
      terrain: worldTerrain,
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

    // P-LIGHT (Jul 2026): HEADLIGHT. Model glTF di Cesium disinari
    // scene.light (default: matahari simulasi) -> lari SITL malam hari
    // membuat pesawat gelap. Lampu diikat ke arah kamera, jadi pesawat
    // SELALU tersinari, jam berapa pun, dari sudut mana pun.
    // (globe.enableLighting=false -> terrain tidak terpengaruh lampu ini.)
    const headlight = new Cesium.DirectionalLight({
      direction: Cesium.Cartesian3.clone(state.viewer.scene.camera.directionWC),
      intensity: 2.0
    });
    state.viewer.scene.light = headlight;
    state.viewer.scene.preRender.addEventListener(() => {
      Cesium.Cartesian3.clone(
        state.viewer.scene.camera.directionWC,
        headlight.direction
      );
    });
    state.viewer.scene.skyAtmosphere.show = true;

    // P-RES: pantau kegagalan Ion -> aktifkan mode fallback sekali saja.
    let fallbackDone = false;
    const useOfflineFallback = (reason) => {
      if (fallbackDone) {
        return;
      }
      fallbackDone = true;
      console.warn("[map] Cesium Ion gagal, pakai fallback offline:", reason);
      try {
        state.viewer.terrainProvider = new Cesium.EllipsoidTerrainProvider();
        state.viewer.imageryLayers.removeAll();
        state.viewer.imageryLayers.addImageryProvider(
          new Cesium.OpenStreetMapImageryProvider({
            url: "https://tile.openstreetmap.org/"
          })
        );
        showToast(
          "Cesium Ion tidak dapat diakses — mode fallback (peta OSM, tanpa terrain 3D)"
        );
        setTerrainReady();
      } catch (e) {
        console.error("[map] fallback gagal:", e);
      }
    };

    if (worldTerrain && worldTerrain.errorEvent) {
      worldTerrain.errorEvent.addEventListener((err) => useOfflineFallback(err));
    }
    const baseImagery = state.viewer.imageryLayers.get(0);
    if (baseImagery && baseImagery.imageryProvider &&
        baseImagery.imageryProvider.errorEvent) {
      baseImagery.imageryProvider.errorEvent.addEventListener((err) =>
        useOfflineFallback(err)
      );
    }

    createAircraftEntities();
    state.viewer.scene.preRender.addEventListener(renderSlavedCamera);

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
    initGroundObserverMarker();
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

  // P5.5: ukur elevasi runway (median) HANYA setelah mesh ter-load penuh
  // (D-08/D-09: sampling dari tile beresolusi rendah = angka salah).
  measureRunwayElevation();
  buildRunwaySlab();

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