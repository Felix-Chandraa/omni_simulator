import { MAVLINK_MESSAGES } from "./messages.js";

export function parseMavlinkMessage(message) {
  // Placeholder parser. 
  // 
  // Expected future input example:
  // {
  //   msgid: 33,
  //   lat: 377749000,
  //   lon: -1224194000,
  //   relative_alt: 120000,
  //   hdg: 9200
  // }

  if (!message || typeof message !== "object") {
    return null;
  }

  switch (message.msgid) {
    case MAVLINK_MESSAGES.GLOBAL_POSITION_INT:
      return {
        lat: Number(message.lat) / 1e7,
        lon: Number(message.lon) / 1e7,
        alt_msl: Number(message.alt) / 1000,
        alt: Number(message.relative_alt) / 1000,
        hdg: Number(message.hdg) / 100
      };

    case MAVLINK_MESSAGES.ATTITUDE:
      return {
        roll: radiansToDegrees(message.roll),
        pitch: radiansToDegrees(message.pitch),
        yaw: radiansToDegrees(message.yaw)
      };

    case MAVLINK_MESSAGES.VFR_HUD:
      return {
        as: Number(message.airspeed),
        gs: Number(message.groundspeed),
        hdg: Number(message.heading),
        alt_msl: Number(message.alt),
        throttle: Number(message.throttle)
      };

    case MAVLINK_MESSAGES.SYS_STATUS:
      return {
        bat: Number(message.battery_remaining)
      };

    default:
      return null;
  }
}

function radiansToDegrees(value) {
  return Number(value) * 180 / Math.PI;
}
