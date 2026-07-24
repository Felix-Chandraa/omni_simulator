/**
 * Registry widget — SATU sumber kebenaran daftar widget UI.
 *
 * Kontrak: setiap elemen ber-`data-widget="<key>"` di map.html WAJIB punya
 * entri di sini (dan sebaliknya). Checklist settings.js digenerate dari
 * daftar ini; profil (vehicle_profiles/*.json) mendaftar key baseline-nya.
 * Menambah widget = 1 tag di HTML + 1 entri di sini. (Melunasi D-10.)
 */

export const WIDGETS = [
  { key: "mode",           label: "Mode",                group: "Status" },
  { key: "armed",          label: "Armed",               group: "Status" },
  { key: "position",       label: "Position (lat/lon)",  group: "Status" },
  { key: "altitude",       label: "Altitude (AGL/MSL)",  group: "Status" },
  { key: "groundspeed",    label: "Ground speed",        group: "Status" },
  { key: "airspeed",       label: "Air speed",           group: "Status" },
  { key: "satellites",     label: "Satellites",          group: "Status" },
  { key: "fuel",           label: "Fuel (bensin)",       group: "Status" },
  { key: "battery",        label: "Avionics battery",    group: "Status" },

  { key: "attitude_gauge", label: "Attitude (ADI)",      group: "Instrumen" },
  { key: "heading_gauge",  label: "Heading (kompas)",    group: "Instrumen" },
  { key: "altitude_gauge", label: "Altitude tape",       group: "Instrumen" },

  { key: "pose_badge",     label: "Pose source badge",   group: "Sistem" },
  { key: "profile_label",  label: "Profile label",       group: "Sistem" },
  { key: "preflight",      label: "Preflight status",    group: "Sistem" }
];
