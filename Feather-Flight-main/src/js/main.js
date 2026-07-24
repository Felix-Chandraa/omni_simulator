import { state } from "./state.js";
import { els } from "./dom.js";

import { initMap } from "./core/map.js";
import { updateHomeMarker, setHomePosition } from "./core/home.js";
import { updateAircraftOnMap, setVehiclePosition } from "./core/aircraft.js";
import { goHome, topView } from "./core/camera.js";
import { VIEWS, setTrainingView, getTrainingView, syncViewButtons } from "./core/views.js";

import { setMissionPath } from "./mission/mission.js";
import { uploadMission } from "./mission/upload.js";
import { downloadMission } from "./mission/download.js";

import { updateHUD, setTelemetry } from "./telemetry/telemetry.js";

import { setPreflightStatus } from "./widgets/preflight.js";
import { updateTelemetryUI, showToast } from "./widgets/hud.js";
import { updateAttitude } from "./widgets/attitudeIndicator.js";
import { updateHeadingTape } from "./widgets/headingTape.js";
import { updateAltitudeTape } from "./widgets/altitudeTape.js";

import { connectBus } from "./bus.js"
import { loadProfile } from "./profile.js";
import { initSettings } from "./widgets/settings.js";
import { initLayoutMode } from "./widgets/layoutMode.js";

import { loadLocation } from "./location.js";

import {
  connectMavlinkWebSocket,
  disconnectMavlinkWebSocket,
  getMavlinkWebSocket
} from "./mavlink/websocket.js";

function exposePublicApi() {
  window.updateHUD = updateHUD;
  window.setVehiclePosition = setVehiclePosition;
  window.setMissionPath = setMissionPath;
  window.setTelemetry = setTelemetry;
  window.setHomePosition = setHomePosition;
  window.setPreflightStatus = setPreflightStatus;

  window.uploadMission = uploadMission;
  window.downloadMission = downloadMission;

  window.updateHeadingTape = updateHeadingTape;
  window.updateAltitudeTape = updateAltitudeTape;
  window.updateAttitude = updateAttitude;

  window.connectMavlinkWebSocket = connectMavlinkWebSocket;
  window.disconnectMavlinkWebSocket = disconnectMavlinkWebSocket;
  window.getMavlinkWebSocket = getMavlinkWebSocket;

  // View training (Tahap C1). Bisa dipanggil dari Python via _call_js_function.
  window.setTrainingView = setTrainingView;
  window.getTrainingView = getTrainingView;
  window.TRAINING_VIEWS = VIEWS;

  window.debugCesium = {
    get viewer() {
      return state.viewer;
    },
    get state() {
      return state;
    }
  };
}

const KEY_TO_VIEW = {
  "1": VIEWS.FPV,
  "2": VIEWS.TAIL,
  "3": VIEWS.FOLLOW,
  "4": VIEWS.GROUND,
  "5": VIEWS.FREE
};

function bindEventListeners() {
  // Semua jalur kamera lewat view engine — satu otoritas, tidak rebutan.
  els.cameraToggleBtn.addEventListener("click", () => {
    setTrainingView(
      getTrainingView() === VIEWS.FOLLOW ? VIEWS.FREE : VIEWS.FOLLOW
    );
  });
  els.homeBtn.addEventListener("click", () => {
    setTrainingView(VIEWS.FREE, true);
    goHome();
  });
  els.topViewBtn.addEventListener("click", () => {
    setTrainingView(VIEWS.FREE, true);
    topView();
  });

  els.viewButtons.forEach((btn) => {
    btn.addEventListener("click", () => setTrainingView(btn.dataset.view));
  });

  window.addEventListener("keydown", (event) => {
    const tag = event.target && event.target.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA") {
      return;
    }
    const view = KEY_TO_VIEW[event.key];
    if (view) {
      setTrainingView(view);
    }
  });

  window.addEventListener("error", (event) => {
    console.error("Unhandled error:", event.error || event.message);
    showToast("Unexpected error while loading map", true);
  });

  window.addEventListener("unhandledrejection", (event) => {
    console.error("Unhandled promise rejection:", event.reason);
    showToast("Map promise failed", true);
  });
}

async function boot() {
  exposePublicApi();
  bindEventListeners();

  await loadProfile();
  initSettings();
  initLayoutMode();
  updateTelemetryUI();
  await loadLocation();
  await initMap();
  connectBus();

  syncViewButtons();

  updateHomeMarker();
  updateAircraftOnMap();
}

boot();