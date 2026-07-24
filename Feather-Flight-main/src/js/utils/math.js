export function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

export function normalizeDegrees(value) {
  return ((Number(value) % 360) + 360) % 360;
}

export function toRadians(degrees) {
  return degrees * Math.PI / 180;
}

export function toDegrees(radians) {
  return radians * 180 / Math.PI;
}

export function isFiniteNumber(value) {
  return Number.isFinite(Number(value));
}
