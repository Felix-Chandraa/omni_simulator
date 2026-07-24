import { state } from "./state.js";
import { maybeUpdateHomeFromTelemetry } from "./home.js";
import { updateTelemetryUI } from "./ui.js";
import { updateAircraftOnMap } from "./aircraft.js";

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
}

export function setTelemetry(patch) {
  updateHUD(patch);
}
