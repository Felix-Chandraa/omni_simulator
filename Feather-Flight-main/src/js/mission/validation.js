export function validateMission(points) {
  const errors = [];

  if (!Array.isArray(points)) {
    return {
      valid: false,
      errors: ["Mission must be an array."]
    };
  }

  if (points.length === 0) {
    return {
      valid: false,
      errors: ["Mission cannot be empty."]
    };
  }

  points.forEach((point, index) => {
    const lat = Number(point.lat ?? point.latitude ?? point.y ?? point[0]);
    const lon = Number(point.lon ?? point.lng ?? point.longitude ?? point.x ?? point[1]);

    if (!Number.isFinite(lat)) {
      errors.push(`Waypoint ${index}: invalid latitude.`);
    }

    if (!Number.isFinite(lon)) {
      errors.push(`Waypoint ${index}: invalid longitude.`);
    }

    if (lat < -90 || lat > 90) {
      errors.push(`Waypoint ${index}: latitude out of range.`);
    }

    if (lon < -180 || lon > 180) {
      errors.push(`Waypoint ${index}: longitude out of range.`);
    }
  });

  return {
    valid: errors.length === 0,
    errors
  };
}
