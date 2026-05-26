/**
 * REST Flask / CoppeliaSim — 6 joints backend ↔ simulador.
 */

import { appState } from "./state.js";
import {
  radToDeg,
  toBackendAngles,
  fromBackendAngles,
  ARM_DOF,
} from "../config/joints.js";

async function postJson(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Comando fallido.");
  }
  return data;
}

export async function fetchRobotConfig() {
  try {
    const response = await fetch("/api/robot-config");
    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}

export async function fetchConfig() {
  const robotCfg = await fetchRobotConfig();
  if (robotCfg) {
    appState.setRobotModel(robotCfg);
    return robotCfg;
  }

  try {
    const response = await fetch("/api/config");
    if (!response.ok) return null;
    const data = await response.json();
    appState.setLimits(data.joint_limits);
    return data;
  } catch {
    return null;
  }
}

export async function fetchStatus() {
  try {
    const response = await fetch("/api/status");
    const data = await response.json();
    if (!response.ok) {
      appState.setConnection({ connected: false, error: data.error });
      return null;
    }

    appState.setConnection(data);
    if (Array.isArray(data.joint_positions) && data.joint_positions.length >= ARM_DOF) {
      const { arm } = fromBackendAngles(data.joint_positions);
      appState.setJointAngles(arm, "sync");
    }
    appState.setGripperOpen(data.gripper_closed ? 0 : 1, "sync");
    return data;
  } catch (error) {
    appState.setConnection({ connected: false, error: error.message });
    return null;
  }
}

export async function sendJoints(armAnglesRad, duration = 0.6) {
  const angles = toBackendAngles(armAnglesRad);
  return postJson("/api/joints", { angles, duration });
}

export async function sendGripper(action) {
  return postJson("/api/gripper", { action });
}

export async function sendHome() {
  return postJson("/api/home", {});
}

export function anglesToBackendPayload(armAnglesRad) {
  return toBackendAngles(armAnglesRad).map((r) => Number(r.toFixed(6)));
}

export function formatAnglesForDisplay(anglesRad) {
  return anglesRad.map((r) => `${radToDeg(r).toFixed(1)}°`);
}
