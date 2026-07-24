export function fmtNumber(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "---";
  }

  return Number(value).toFixed(digits);
}

export function fmtCoord(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "---";
  }

  return Number(value).toFixed(6);
}

export function fmtDeg(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "---";
  }

  const normalized = ((Math.round(Number(value)) % 360) + 360) % 360;
  return `${normalized.toString().padStart(3, "0")}°`;
}

export function homeKey(lat, lon, source) {
  return `${Number(lat).toFixed(6)}|${Number(lon).toFixed(6)}|${String(source || "")}`;
}
