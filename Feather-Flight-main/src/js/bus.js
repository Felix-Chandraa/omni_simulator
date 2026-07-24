import { updateHUD } from "./telemetry/telemetry.js";

/**
 * F1 — Klien Telemetry Bus (WebSocket).
 *
 * Menggantikan penerimaan telemetri lewat runJavaScript utk window/monitor
 * TAMBAHAN (browser biasa). Window PyQt tetap disuapi runJavaScript; halaman
 * yang di-host PyQt menandai `window.__OMNI_PYQT_HOST__ = true` -> modul ini
 * TIDAK ikut konek di sana (cegah double-feed).
 *
 * Envelope (SDD F1): {"type":"telemetry","data":{...}} -> updateHUD(data).
 * `window.updateHUD` tetap sbg adapter selama transisi (sudah di-set main.js).
 */

let socket = null;
let reconnectTimer = null;
let manualClose = false;

function busUrl() {
  // Port bus terpisah dari port HTTP statis. Host = host halaman (localhost).
  const host = window.location.hostname || "127.0.0.1";
  const port = window.__OMNI_BUS_PORT__ || 8765; // [VERIFY-LOCAL] samakan config.py
  return `ws://${host}:${port}`;
}

function handleMessage(event) {
  let msg;
  try {
    msg = JSON.parse(event.data);
  } catch (err) {
    console.error("[bus] payload bukan JSON:", err);
    return;
  }

  if (msg && msg.type === "telemetry" && msg.data) {
    updateHUD(msg.data);
  }
  // type "event"/"cmd" ditangani modul lain (P3/P4) — F1 hanya telemetry.
}

export function connectBus() {
  // Halaman host PyQt sudah menerima telemetri via runJavaScript.
  if (window.__OMNI_PYQT_HOST__) {
    console.log("[bus] host PyQt terdeteksi — bus.js pasif (anti double-feed).");
    return null;
  }

  manualClose = false;
  const url = busUrl();
  socket = new WebSocket(url);

  socket.addEventListener("open", () => console.log("[bus] tersambung:", url));
  socket.addEventListener("message", handleMessage);
  socket.addEventListener("close", () => {
    if (manualClose) return;
    // Reconnect ringan: backend bisa restart saat sesi latih.
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connectBus, 1000);
  });
  socket.addEventListener("error", (e) => console.error("[bus] error:", e));

  return socket;
}

export function disconnectBus() {
  manualClose = true;
  clearTimeout(reconnectTimer);
  if (socket) {
    socket.close();
    socket = null;
  }
}

/** Kirim pesan client->server (mis. instruktur set_view/cmd). Divalidasi backend. */
export function sendBus(message) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(message));
    return true;
  }
  return false;
}