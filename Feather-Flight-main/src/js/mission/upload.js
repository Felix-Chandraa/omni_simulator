import { validateMission } from "./validation.js";
import { setMissionPath } from "./mission.js";

export async function uploadMission(points) {
  const result = validateMission(points);

  if (!result.valid) {
    throw new Error(result.errors.join("\n"));
  }

  // Placeholder:
  // Send mission to vehicle/backend here.
  //
  // Example:
  // await fetch("/api/mission/upload", {
  //   method: "POST",
  //   headers: { "Content-Type": "application/json" },
  //   body: JSON.stringify(points)
  // });

  setMissionPath(points);

  return {
    ok: true,
    count: points.length
  };
}
