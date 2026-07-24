export const CONFIG = {
  title: "Feather Flight",
  vehicleProfile: "fixed_wing",

  terrainReadyText: "3D terrain ready",
  terrainLoadingText: "Loading terrain...",

  cesiumIonAccessToken:
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiI1NTIwYTI0ZC1hNzhkLTQxOTQtYTUyZS01MzJkY2FjZjRmOTEiLCJpZCI6NDM4NDA1LCJpc3MiOiJodHRwczovL2FwaS5jZXNpdW0uY29tIiwiYXVkIjoidW5kZWZpbmVkX2RlZmF1bHQiLCJpYXQiOjE3ODAxODcyNTV9.CjL3_OhS1sa5uQvoez9unMWVm07PGhT082pYLNnVGfk",

  aircraftModelUri:
    "https://cesium.com/downloads/cesiumjs/releases/1.118/Apps/SampleData/models/CesiumAir/Cesium_Air.glb",

  // Kalibrasi model 3D custom (C3). uri null = pakai aircraftModelUri di atas.
  // *OffsetDeg mengoreksi konvensi sumbu hasil ekspor/konversi (mis. model
  // menghadap +Z, atau Z-up) — dikomposisi sebagai quaternion di body frame,
  // TIDAK memengaruhi kamera FPV/tail (kamera pakai pose mentah).
  aircraftModel: {
    uri: "./dist/models/omni_plane.glb",
    // uri: null,
    scale: 1,
    minimumPixelSize: 0,
    maximumScale: 250,
    headingOffsetDeg: 0,   // hidung salah arah horizontal: coba 90/-90/180
    pitchOffsetDeg: 90,    // model "berdiri" (Z-up export): coba -90
    rollOffsetDeg: 0,
    // Jarak origin model -> perut/roda, meter. Pengganti fudge global
    // aircraftAltitudeOffset (+3 m) yang membuat pesawat melayang.
    // Kalibrasi: 0 dulu; kalau model tenggelam sebagian di runway,
    // naikkan sedikit (skala model kalian: coba 0.02-0.10).
    groundClearanceMeters: 0.38,
    // KOMPENSASI ORIGIN GLB: bila origin file glb TIDAK di badan pesawat
    // (khas ekspor CAD: origin di titik nol dokumen), mesh menggantung
    // sejauh offset itu -> melayang konstan + "mengorbit" saat manuver.
    // Isi vektor dari titik telemetri KE mesh dalam sumbu badan pesawat
    // (meter): mesh tampak 0.4 m di atas -> up: 0.4. Ikut berotasi dgn
    // pesawat, jadi sekaligus menghilangkan efek ayunan/pegas.
    // Fix sejati tetap: re-export dgn origin di CG (lihat instruksi).
    meshOffsetMeters: { forward: 0, right: 0, up: 0 }
  },

  home: {
    lat: 37.7749,
    lon: -122.4194,
    alt: 1200
  },

  trailWidth: 5,
  trailMaxPoints: 250,
  trailMinDistance: 2.0,

  // Konvensi HPR Cesium: sumbu X frame lokal mengarah TIMUR pada heading 0.
  // Offset ini menormalkan heading-dari-utara (telemetri) ke konvensi itu.
  // Berlaku utk entity DAN frame kamera body — JANGAN dihapus saat ganti model.
  enuHeadingOffsetDeg: -90,

  views: {
    fpv: {
      // offset body-frame dari pusat model, meter
      offsetMeters: { forward: 1, right: 0, up: 0.2 }
    },
    tail: {
      offsetMeters: { forward: -1.1, right: 0, up: 0.45 },
      pitchDeg: -20,    // kamera sedikit menunduk
      followRoll: true  // true: kamera ikut roll pesawat; false: horizon dikunci datar
    },
    ground: {
      eyeHeightMeters: 1.8,
      // P5.5: null => pengamat ditempatkan otomatis di BAHU runway, di
      // tengah panjang landasan (core/runway.js runwayShoulder()).
      useRunwayShoulder: false,      // false => pakai koordinat GCS tetap (views.ground.gcs)
      // Posisi GCS TETAP (usulan UX): isi koordinat stasiun di lapangan
      // training. null = fallback perilaku lama (dekat home + offset).
      gcs: { lat: null, lon: null, altMsl: null },
      offsetLatDeg: -0.0003,      // dipakai HANYA pada mode fallback
      offsetLonDeg: 0,
      // P-GV: kontrol runtime (zoom teropong + geser pengamat)
      moveStepMeters: 2,          // langkah WASD
      moveStepFastMeters: 10,     // langkah WASD + Shift
      zoom: { minFovDeg: 2, maxFovDeg: 65, wheelFactor: 1.15 }
    }
  },

  // P5.5 — Geometri runway Wiriadinata (SDD Bab 8.6).
  // Threshold = locations/wiriadinata.env (RWY15/RWY33). Bearing terhitung
  // 148.09 deg (cocok HDG_TRUE 148.1), panjang ~1128 m.
  runway: {
    enabled: true,
    // TERKALIBRASI 14 Jul 2026 via calibrateRunway() (klik di citra).
    // Menggantikan seed A.4 yang meleset ~500 m. Salin juga ke
    // locations/wiriadinata.env + locations.txt (HDG_TRUE=147.7).
    thresholdA: { lat: -7.342176, lon: 108.243348 }, // RWY15 (barat-laut)
    thresholdB: { lat: -7.354103, lon: 108.250961 }, // RWY33 (tenggara)
    widthMeters: 30,          // lebar aspal
    blendMeters: 140,         // sabuk transisi ke terrain asli (anti-tebing).
                              // P5.7: dilebarkan agar landaian sangat halus.
    shoulderOffsetMeters: 12, // jarak pengamat dari TEPI aspal
    shoulderSide: "right",    // sisi kanan arah pendaratan (15 -> 33)

    // --- P5.5b: slab datar yang MENIMPA mesh ---
    slabEpsilonM: 0.05,
    skirtMeters: 12,
    asphaltColor: "#21201f",       // warna DINDING/skirt slab (sisi samping)
    // P5.9 — tekstur ATAP slab (aspal + marka dipanggang jadi 1 gambar):
    // marka menyatu rata dgn permukaan, tanpa polyline mengambang (anti mata-sakit).
    // Ganti ke foto ortho asli via setRunwayTexture('url'); bila arah marka
    // melintang, putar UV via setRunwayTextureRotation(deg) lalu kunci angkanya di sini.
    textureUri: "./dist/models/runway_wiriadinata.png",
    textureRotationDeg: null       // null => auto dari bearing; angka => paksa
  },

  // P5.6 — Permukaan lanud: mesh grid bertekstur yang MELANDAI ke terrain.
  // Tidak ada skirt/balok: tinggi tiap simpul = flattenHeight(raw terrain),
  // jadi datar di runway dan menyatu mulus dengan tanah asli di tepi.
camera: {
    followHeadingDeg: 0,
    followPitchDeg: -22,
    followRangeMeters: 1100,
    topHeadingDeg: 0,
    topPitchDeg: -90,
    topRangeMeters: 4500,
    homeViewHeightMeters: 8000,
    topViewHeightMeters: 30000
  },

  ui: {
    toastDurationMs: 2600
  }
};