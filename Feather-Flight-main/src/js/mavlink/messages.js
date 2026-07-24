export const MAVLINK_MESSAGES = {
  HEARTBEAT: 0,
  SYS_STATUS: 1,
  GPS_RAW_INT: 24,
  ATTITUDE: 30,
  GLOBAL_POSITION_INT: 33,
  VFR_HUD: 74,
  BATTERY_STATUS: 147,
  HOME_POSITION: 242
};

export function messageName(messageId) {
  const entry = Object.entries(MAVLINK_MESSAGES).find(
    ([, id]) => id === messageId
  );

  return entry ? entry[0] : `UNKNOWN_${messageId}`;
}
