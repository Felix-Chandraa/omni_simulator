const $ = (id) => document.getElementById(id);

export const els = {
  titleText: $("titleText"),
  terrainStatusText: $("terrainStatusText"),

  loadingOverlay: $("loadingOverlay"),
  loadingText: $("loadingText"),
  toast: $("toast"),

  cameraToggleBtn: $("cameraToggleBtn"),
  homeBtn: $("homeBtn"),
  topViewBtn: $("topViewBtn"),

  viewButtons: Array.from(document.querySelectorAll(".view-btn[data-view]")),
  poseBadge: $("poseBadge"),

  modeValue: $("modeValue"),
  armedText: $("armedText"),
  armedDot: $("armedDot"),

  latLonValue: $("latLonValue"),
  satValue: $("satValue"),
  gsValue: $("gsValue"),
  asValue: $("asValue"),

  altAglLabel: $("altAglLabel"),
  altAglValue: $("altAglValue"),
  altMslValue: $("altMslValue"),

  fuelValue: $("fuelValue"),
  fuelBar: $("fuelBar"),
  batPctValue: $("batPctValue"),
  batVoltValue: $("batVoltValue"),
  batBar: $("batBar"),

  headingBig: $("headingBig"),
  hsi: $("hsi"),

  adi: $("adi"),
  rpyReadout: $("rpyReadout"),

  altTapeScale: $("altTapeScale"),
  altTapeValue: $("altTapeValue"),
  altCaption: $("altCaption"),

  settingsBtn: $("settingsBtn"),
  settingsDrawer: $("settingsDrawer"),
  settingsBackdrop: $("settingsBackdrop"),
  settingsModes: $("settingsModes"),
  settingsList: $("settingsList"),
  settingsReset: $("settingsReset"),
  settingsClose: $("settingsClose"),
  tapeSourceSel: $("tapeSourceSel"),

  preflightStatus: $("preflightStatus"),
  preflightText: $("preflightText"),
  preflightDot: $("preflightDot")
};
