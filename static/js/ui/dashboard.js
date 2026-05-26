/**
 * Panel de telemetría e indicadores de articulación.
 */

import { appState } from "../core/state.js";
import { JOINT_LABELS, JOINT_KEYS, radToDeg, ARM_DOF } from "../config/joints.js";

function el(id) {
  return document.getElementById(id);
}

export function initDashboard() {
  appState.addEventListener("connection-changed", updateConnection);
  appState.addEventListener("joints-changed", updateJoints);
  appState.addEventListener("gripper-changed", updateGripper);
  appState.addEventListener("telemetry-changed", updateTelemetry);
  appState.addEventListener("limits-changed", updateLimits);
  appState.addEventListener("ik-changed", updateIk);
  renderJointIndicators();
}

export function refreshDashboard() {
  updateConnection();
  updateJoints();
  updateGripper();
  updateTelemetry();
  updateLimits();
  updateIk();
  renderJointIndicators();
}

function updateConnection() {
  const pill = el("connection-status");
  const dot = el("status-dot");
  if (!pill) return;

  if (appState.connected) {
    pill.textContent = "CONECTADO";
    pill.dataset.state = "online";
    dot?.classList.add("online");
    dot?.classList.remove("offline");
  } else {
    pill.textContent = "SIMULACIÓN";
    pill.dataset.state = "offline";
    dot?.classList.add("offline");
    dot?.classList.remove("online");
  }

  el("connected-value").textContent = appState.connected ? "CoppeliaSim" : "Local";
  el("gripper-value").textContent = appState.gripperClosed ? "Cerrada" : "Abierta";
  el("error-value").textContent = appState.lastError || "—";
  el("last-update").textContent = new Date().toLocaleTimeString();

  const meta = el("model-meta");
  if (meta && appState.robotModel) {
    meta.textContent = `${appState.robotModel.robot_name ?? "Niryo One"} · ${ARM_DOF} DOF + pinza`;
  }
}

function updateIk() {
  const { enabled, active, distance, converged } = appState.ikStatus;
  const statusEl = el("ik-status");
  const distEl = el("ik-distance");
  const modeEl = el("ik-mode");

  if (statusEl) {
    if (!enabled) {
      statusEl.textContent = "Desactivado";
      statusEl.dataset.state = "off";
    } else if (converged) {
      statusEl.textContent = "Convergido";
      statusEl.dataset.state = "ok";
    } else if (active) {
      statusEl.textContent = "Rastreando";
      statusEl.dataset.state = "active";
    } else {
      statusEl.textContent = "Inactivo";
      statusEl.dataset.state = "idle";
    }
  }

  if (distEl) distEl.textContent = `${(distance * 1000).toFixed(1)} mm`;
  if (modeEl) {
    modeEl.textContent =
      appState.controlMode === "target"
        ? "IK (objetivo)"
        : appState.controlMode === "gizmo"
          ? "Gizmo"
          : appState.controlMode === "manual"
            ? "Manual"
            : "Sync";
  }
}

function updateJoints() {
  const list = el("angles-list");
  if (!list) return;
  list.innerHTML = "";

  appState.jointAngles.forEach((rad, i) => {
    const key = JOINT_KEYS[i];
    const [minD, maxD] = appState.jointLimits[key] ?? [-180, 180];
    const deg = radToDeg(rad);
    const pct = ((deg - minD) / (maxD - minD)) * 100;

    const row = document.createElement("div");
    row.className = "angle-row";
    row.innerHTML = `
      <div class="angle-row-head">
        <span>${JOINT_LABELS[i]}</span>
        <strong>${deg.toFixed(1)}°</strong>
      </div>
      <div class="limit-bar"><span style="width:${Math.min(100, Math.max(0, pct))}%"></span></div>
      <div class="limit-labels"><span>${minD.toFixed(0)}°</span><span>${maxD.toFixed(0)}°</span></div>
    `;
    list.appendChild(row);
  });

  updateJointIndicators();
}

function updateGripper() {
  const pct = Math.round(appState.gripperOpen * 100);
  const gripEl = el("gripper-pct");
  if (gripEl) gripEl.textContent = `${pct}%`;
  const bar = el("gripper-bar-fill");
  if (bar) bar.style.width = `${pct}%`;
}

function updateTelemetry() {
  const { x, y, z } = appState.endEffector;
  el("ee-x").textContent = x.toFixed(3);
  el("ee-y").textContent = y.toFixed(3);
  el("ee-z").textContent = z.toFixed(3);

  el("target-x").textContent = appState.targetPosition.x.toFixed(3);
  el("target-y").textContent = appState.targetPosition.y.toFixed(3);
  el("target-z").textContent = appState.targetPosition.z.toFixed(3);
}

function updateLimits() {
  const container = el("limits-grid");
  if (!container) return;
  container.innerHTML = "";

  JOINT_KEYS.forEach((key, i) => {
    const [min, max] = appState.jointLimits[key] ?? [-180, 180];
    const cell = document.createElement("div");
    cell.className = "limit-cell";
    cell.innerHTML = `<span>${JOINT_LABELS[i]}</span><strong>${min.toFixed(0)}° … ${max.toFixed(0)}°</strong>`;
    container.appendChild(cell);
  });
}

function renderJointIndicators() {
  const row = el("joint-indicators");
  if (!row) return;
  row.innerHTML = "";

  JOINT_LABELS.forEach((label) => {
    const chip = document.createElement("div");
    chip.className = "joint-chip";
    chip.innerHTML = `<span class="joint-led"></span><span>${label}</span>`;
    row.appendChild(chip);
  });
}

function updateJointIndicators() {
  const row = el("joint-indicators");
  if (!row) return;

  row.querySelectorAll(".joint-chip").forEach((chip, i) => {
    const key = JOINT_KEYS[i];
    const [minD, maxD] = appState.jointLimits[key] ?? [-180, 180];
    const deg = radToDeg(appState.jointAngles[i] ?? 0);
    const margin = 6;
    const led = chip.querySelector(".joint-led");
    chip.classList.toggle("active", appState.controlMode !== "sync");
    if (deg <= minD + margin || deg >= maxD - margin) {
      led?.classList.add("warn");
    } else {
      led?.classList.remove("warn");
    }
  });
}
