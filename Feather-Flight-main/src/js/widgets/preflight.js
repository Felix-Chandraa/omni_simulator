import { els } from "../dom.js";

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
