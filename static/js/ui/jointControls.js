/**
 * Sliders manuales — 6 articulaciones + apertura de pinza.
 */

import { appState, ControlMode } from "../core/state.js";
import {
  JOINT_LABELS,
  JOINT_KEYS,
  radToDeg,
  degToRad,
  ARM_DOF,
} from "../config/joints.js";
import {
  fetchStatus,
  sendJoints,
  sendGripper,
  sendHome,
  anglesToBackendPayload,
} from "../core/api.js";

let simulator = null;

export function bindSimulator(sim) {
  simulator = sim;
}

export function initJointControls() {
  buildSliders();

  appState.addEventListener("joints-changed", (e) => {
    if (e.detail.source === ControlMode.MANUAL) return;
    syncSlidersFromState();
  });

  appState.addEventListener("gripper-changed", (e) => {
    if (e.detail.source === ControlMode.MANUAL) return;
    const slider = el("gripper-slider");
    if (slider) slider.value = String(Math.round(appState.gripperOpen * 100));
  });

  el("btn-sync")?.addEventListener("click", () => fetchStatus());
  el("btn-send")?.addEventListener("click", () => sendCurrentPose());
  el("btn-home")?.addEventListener("click", async () => {
    await sendHome();
    await fetchStatus();
  });
  el("btn-open")?.addEventListener("click", () => sendGripper("open").then(fetchStatus));
  el("btn-close")?.addEventListener("click", () => sendGripper("close").then(fetchStatus));

  el("toggle-manual")?.addEventListener("click", () => {
    el("manual-panel")?.classList.toggle("collapsed");
  });

  el("toggle-ik")?.addEventListener("change", (e) => {
    if (simulator) simulator.ikEnabled = e.target.checked;
  });
}

function el(id) {
  return document.getElementById(id);
}

function buildSliders() {
  const container = el("joint-sliders");
  if (!container) return;
  container.innerHTML = "";

  for (let index = 0; index < ARM_DOF; index += 1) {
    const label = JOINT_LABELS[index];
    const key = JOINT_KEYS[index];
    const [minD, maxD] = appState.jointLimits[key] ?? [-180, 180];

    const row = document.createElement("div");
    row.className = "slider-row";
    row.innerHTML = `
      <label>
        <span>${label}</span>
        <strong id="slider-val-${index}">0°</strong>
      </label>
      <input type="range" id="slider-${index}" min="${minD}" max="${maxD}" step="0.5" value="0" />
    `;
    container.appendChild(row);

    row.querySelector("input").addEventListener("input", (ev) => {
      const deg = Number(ev.target.value);
      el(`slider-val-${index}`).textContent = `${deg.toFixed(1)}°`;
      const angles = [...appState.jointAngles];
      angles[index] = degToRad(deg);
      simulator?.setAngles(angles, ControlMode.MANUAL);
    });
  }

  const gripRow = document.createElement("div");
  gripRow.className = "slider-row gripper-slider-row";
  gripRow.innerHTML = `
    <label>
      <span>Pinza (apertura)</span>
      <strong id="gripper-slider-val">100%</strong>
    </label>
    <input type="range" id="gripper-slider" min="0" max="100" step="1" value="100" />
  `;
  container.appendChild(gripRow);

  el("gripper-slider")?.addEventListener("input", (ev) => {
    const pct = Number(ev.target.value);
    el("gripper-slider-val").textContent = `${pct}%`;
    simulator?.setGripperOpen(pct / 100, ControlMode.MANUAL);
  });
}

function syncSlidersFromState() {
  appState.jointAngles.forEach((rad, index) => {
    const slider = el(`slider-${index}`);
    const val = el(`slider-val-${index}`);
    if (!slider) return;
    const deg = radToDeg(rad);
    slider.value = deg;
    val.textContent = `${deg.toFixed(1)}°`;
  });
}

async function sendCurrentPose() {
  try {
    await sendJoints(anglesToBackendPayload(appState.jointAngles));
    await fetchStatus();
  } catch {
    /* api actualiza estado */
  }
}

export function scheduleStatusPoll(intervalMs = 3500) {
  setInterval(fetchStatus, intervalMs);
}
