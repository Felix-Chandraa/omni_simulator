import { state } from "../state.js";
import { maybeUpdateHomeFromTelemetry } from "../core/home.js";
import { updateTelemetryUI } from "../widgets/hud.js";
import { updateAircraftOnMap } from "../core/aircraft.js";
import { updateAttitude } from "../widgets/attitudeIndicator.js";
import { updateHeadingTape } from "../widgets/headingTape.js";
import { updateAltitudeTape } from "../widgets/altitudeTape.js";

export function updateHUD(data) {
  const homeLat = data.home_lat ?? data.homeLat;
  const homeLon = data.home_lon ?? data.homeLon;
  const homeAlt = data.home_alt ?? data.homeAlt ?? null;
  const homeSource = data.home_source ?? data.homeSource ?? null;

  state.telemetry = {
    ...state.telemetry,
    ...data
  };

  if ("armed" in data) {
    state.telemetry.armed = Boolean(data.armed);
  }

  maybeUpdateHomeFromTelemetry({
    home_lat: homeLat,
    home_lon: homeLon,
    home_alt: homeAlt,
    home_source: homeSource
  });

  updateTelemetryUI();
  updateAircraftOnMap();

  updateAttitude(state.telemetry);
  updateHeadingTape(state.telemetry);
  updateAltitudeTape(state.telemetry);
}

export function setTelemetry(patch) {
  updateHUD(patch);
}
