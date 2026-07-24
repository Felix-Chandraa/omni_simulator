import { CONFIG } from "../config.js";
import { state } from "../state.js";
import { els } from "../dom.js";
import { showToast } from "../widgets/hud.js";
import { ensureHomeReady } from "./home.js";

export const FOLLOW_CAMERA_RANGE = new Cesium.HeadingPitchRange(
  Cesium.Math.toRadians(CONFIG.camera.followHeadingDeg),
  Cesium.Math.toRadians(CONFIG.camera.followPitchDeg),
  CONFIG.camera.followRangeMeters
);

export function clearCameraTransform() {
  if (!state.viewer) {
    return;
  }

  state.viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
}

export function setFollowCamera(position) {
  if (!state.viewer || !position) {
    return;
  }

  state.viewer.camera.lookAt(position, FOLLOW_CAMERA_RANGE);
}

export function setTopCamera(position) {
  if (!state.viewer || !position) {
    return;
  }

  state.viewer.camera.lookAt(
    position,
    new Cesium.HeadingPitchRange(
      Cesium.Math.toRadians(CONFIG.camera.topHeadingDeg),
      Cesium.Math.toRadians(CONFIG.camera.topPitchDeg),
      CONFIG.camera.topRangeMeters
    )
  );
}

export function setCameraMode(follow, silent = false) {
  state.followAircraft = Boolean(follow);

  els.cameraToggleBtn.classList.toggle("active", state.followAircraft);
  els.cameraToggleBtn.textContent = state.followAircraft
    ? "Follow Camera"
    : "Free Camera";

  if (state.viewer) {
    state.viewer.trackedEntity = state.followAircraft
      ? state.entities.aircraft
      : null;
  }

  if (state.followAircraft) {
    if (state.lastPosition) {
      setFollowCamera(state.lastPosition);
    }
  } else {
    clearCameraTransform();
  }

  if (!silent) {
    showToast(
      state.followAircraft
        ? "Follow camera enabled"
        : "Free camera enabled"
    );
  }
}

export function toggleCameraMode() {
  setCameraMode(!state.followAircraft);
}

export function updateCameraFollow() {
  if (!state.viewer || !state.lastPosition || !state.followAircraft) {
    return;
  }

  state.viewer.camera.lookAt(state.lastPosition, FOLLOW_CAMERA_RANGE);
}

export async function goHome() {
  if (!state.viewer) {
    return;
  }

  if (state.followAircraft) {
    setCameraMode(false, true);
  }

  const home = await ensureHomeReady();
  const target = home || CONFIG.home;

  clearCameraTransform();

  state.viewer.camera.flyTo({
    destination: Cesium.Cartesian3.fromDegrees(
      target.lon,
      target.lat,
      (Number.isFinite(target.alt) ? target.alt : CONFIG.home.alt) +
        CONFIG.camera.homeViewHeightMeters
    ),
    duration: 1.2
  });
}

export function topView() {
  if (!state.viewer) {
    return;
  }

  if (state.followAircraft) {
    setCameraMode(false, true);
  }

  const focus =
    state.lastPosition ||
    (
      Number.isFinite(state.home.lat) &&
      Number.isFinite(state.home.lon)
        ? Cesium.Cartesian3.fromDegrees(
            state.home.lon,
            state.home.lat,
            Number.isFinite(state.home.alt) ? state.home.alt : 0
          )
        : Cesium.Cartesian3.fromDegrees(
            CONFIG.home.lon,
            CONFIG.home.lat,
            CONFIG.home.alt
          )
    );

  clearCameraTransform();

  state.viewer.camera.flyTo({
    destination: Cesium.Cartesian3.fromDegrees(
      Number.isFinite(state.home.lat) && Number.isFinite(state.home.lon)
        ? state.home.lon
        : CONFIG.home.lon,
      Number.isFinite(state.home.lat) && Number.isFinite(state.home.lon)
        ? state.home.lat
        : CONFIG.home.lat,
      (Number.isFinite(state.home.alt) ? state.home.alt : CONFIG.home.alt) +
        CONFIG.camera.topViewHeightMeters
    ),
    duration: 1.0,
    orientation: {
      heading: Cesium.Math.toRadians(0),
      pitch: Cesium.Math.toRadians(-90),
      roll: 0
    }
  });

  setTimeout(() => {
    setTopCamera(focus);
  }, 1200);
}
