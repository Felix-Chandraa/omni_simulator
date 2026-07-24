import { CONFIG } from "./config.js";
import { els } from "./dom.js";
import { state } from "./state.js";
import { fmtCoord, fmtDeg, fmtNumber } from "./format.js";

export function setLoading(visible, text) {
  if (typeof text === "string") {
    els.loadingText.textContent = text;
    els.terrainStatusText.textContent = text;
  }

  els.loadingOverlay.classList.toggle("hidden", !visible);
}

export function showToast(message, isError = false) {
  els.toast.textContent = message;
  els.toast.className = "toast show" + (isError ? " error" : "");

  clearTimeout(showToast._timer);

  showToast._timer = setTimeout(() => {
    els.toast.className = "toast";
  }, CONFIG.ui.toastDurationMs);
}

export function setPreflightStatus(data) {
  const complete = Boolean(data && data.complete);
  const missing = Array.isArray(data?.missing) ? data.missing : [];

  const text = complete
    ? "Checklist complete"
    : missing.length
      ? `Pending: ${missing[0]}`
      : "Checklist pending";

  els.preflightText.textContent = text;
  els.preflightStatus.classList.toggle("ok", complete);
  els.preflightText.style.color = complete ? "var(--good)" : "var(--warn)";
  els.preflightDot.style.background = complete ? "var(--good)" : "var(--warn)";
}

export function updateTelemetryUI() {
  const t = state.telemetry;

  els.modeValue.textContent = t.mode ?? "---";

  els.armedText.textContent =
    t.armed === true
      ? "ARMED"
      : t.armed === false
        ? "DISARMED"
        : "---";

  els.armedDot.style.background =
    t.armed === true
      ? "var(--good)"
      : t.armed === false
        ? "var(--bad)"
        : "var(--warn)";

  els.latLonValue.textContent = `${fmtCoord(t.lat)}, ${fmtCoord(t.lon)}`;
  els.satValue.textContent = t.sat ?? "---";

  els.batValue.textContent =
    typeof t.bat === "number"
      ? `${Math.round(t.bat)}%`
      : t.bat ?? "---";

  els.altValue.textContent =
    t.alt !== null && t.alt !== undefined
      ? `${fmtNumber(t.alt, 1)} m`
      : "---";

  els.gsValue.textContent =
    t.gs !== null && t.gs !== undefined
      ? `${fmtNumber(t.gs, 1)}`
      : "---";

  els.asValue.textContent =
    t.as !== null && t.as !== undefined
      ? `${fmtNumber(t.as, 1)}`
      : "---";

  els.hdgValue.textContent = fmtDeg(t.hdg);

  els.rollValue.textContent =
    t.roll !== null && t.roll !== undefined
      ? `${fmtNumber(t.roll, 1)}°`
      : "---";

  els.pitchValue.textContent =
    t.pitch !== null && t.pitch !== undefined
      ? `${fmtNumber(t.pitch, 1)}°`
      : "---";

  els.yawValue.textContent =
    t.yaw !== null && t.yaw !== undefined
      ? `${fmtNumber(t.yaw, 1)}°`
      : "---";

  els.latValue.textContent = fmtCoord(t.lat);
  els.lonValue.textContent = fmtCoord(t.lon);

  els.headingBig.textContent = fmtDeg(t.hdg);

  els.altitudeBig.textContent =
    t.alt !== null && t.alt !== undefined
      ? `${fmtNumber(t.alt, 1)} m`
      : "0.0 m";

  els.compassRing.style.transform = `rotate(${-Number(t.hdg || 0)}deg)`;
}
