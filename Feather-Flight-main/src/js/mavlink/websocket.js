import { parseMavlinkMessage } from "./parser.js";
import { updateHUD } from "../telemetry/telemetry.js";

let socket = null;

export function connectMavlinkWebSocket(url) {
  disconnectMavlinkWebSocket();

  socket = new WebSocket(url);

  socket.addEventListener("open", () => {
    console.log("MAVLink WebSocket connected:", url);
  });

  socket.addEventListener("message", (event) => {
    try {
      const raw = JSON.parse(event.data);

      const telemetry = raw.telemetry || parseMavlinkMessage(raw);

      if (telemetry) {
        updateHUD(telemetry);
      }
    } catch (error) {
      console.error("Failed to parse MAVLink WebSocket message:", error);
    }
  });

  socket.addEventListener("close", () => {
    console.log("MAVLink WebSocket disconnected");
  });

  socket.addEventListener("error", (error) => {
    console.error("MAVLink WebSocket error:", error);
  });

  return socket;
}

export function disconnectMavlinkWebSocket() {
  if (socket) {
    socket.close();
    socket = null;
  }
}

export function getMavlinkWebSocket() {
  return socket;
}
