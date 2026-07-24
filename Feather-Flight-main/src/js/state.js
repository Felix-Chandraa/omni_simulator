export const state = {
  viewer: null,

  followAircraft: true,
  terrainReady: false,

  ui: {
    layoutMode: "full"   // full | gcs | visual (widgets/layoutMode.js)
  },

  runway: {
    elevM: null,       // tinggi PERMUKAAN SLAB (max terrain + eps)
    medianM: null,     // median mentah (referensi/diagnostik)
    sampleCount: 0,
    spreadM: null,     // sebaran mentah DEM (bukti seberapa bergelombang)
    surfacePrimitive: null,
    markingEntities: []
  },

  geoid: {
    offsetM: null      // Cesium terrain - SITL alt_msl (fallback spawn saja)
  },

  home: {
    lat: null,
    lon: null,
    alt: null,
    source: null,
    key: null,
    version: 0,
    samplePromise: null
  },

  telemetry: {
    mode: "---",
    armed: false,
    lat: null,
    lon: null,
    alt: 0,
    alt_msl: null,
    gs: 0,
    as: 0,
    hdg: 0,
    roll: 0,
    pitch: 0,
    yaw: 0,
    sat: "---",
    bat: "---"
  },

  entities: {
    aircraft: null,
    fallbackAircraft: null,
    mission: null,
    home: null,
    waypoints: [],
    trail: null,
    groundTrail: null
  },

  lastPosition: null,
  lastCameraPose: null,
  trailPositions: []
};
