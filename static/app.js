const jointNames = [
  "Base",
  "Hombro",
  "Codo",
  "Muñeca 1",
  "Muñeca 2",
  "Muñeca 3",
];

const state = {
  jointAngles: [0, 0, 0, 0, 0, 0],
  gripperClosed: false,
};

function toRadians(degrees) {
  return (degrees * Math.PI) / 180;
}

function toDegrees(radians) {
  return Math.round((radians * 180) / Math.PI);
}

function buildJointControls() {
  const container = document.getElementById("joint-controls");
  container.innerHTML = "";

  jointNames.forEach((name, index) => {
    const card = document.createElement("div");
    card.className = "joint-card";
    card.innerHTML = `
      <label>${name}
        <span id="joint-label-${index}">0°</span>
      </label>
      <input type="range" id="joint-slider-${index}" min="-180" max="180" step="1" value="0" />
      <div class="value-row">
        <span>Ángulo</span>
        <span id="joint-value-${index}">0°</span>
      </div>
    `;
    container.appendChild(card);

    const slider = card.querySelector("input");
    slider.addEventListener("input", () => {
      const value = slider.value;
      document.getElementById(`joint-value-${index}`).textContent = `${value}°`;
      document.getElementById(`joint-label-${index}`).textContent = `${name} (${value}°)`;
    });
  });
}

async function fetchStatus() {
  try {
    const response = await fetch("/api/status");
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Error al obtener estado.");
    }

    state.jointAngles = data.joint_positions.map(toDegrees);
    state.gripperClosed = data.gripper_closed;
    updateStatus(data);
    fillJointControls();
  } catch (error) {
    setDisconnected(error.message);
  }
}

function updateStatus(data) {
  const connected = data.connected;
  document.getElementById("connected").textContent = connected ? "Sí" : "No";
  const statusPill = document.getElementById("connection-status");
  statusPill.textContent = connected ? "Conectado" : "Desconectado";
  statusPill.style.background = connected
    ? "rgba(56, 189, 248, 0.14)"
    : "rgba(248, 113, 113, 0.14)";
  statusPill.style.color = connected ? "#38bdf8" : "#f87171";
  document.getElementById("gripper-state").textContent = data.gripper_closed ? "Cerrada" : "Abierta";
  document.getElementById("last-error").textContent = data.last_error || "Ninguno";
  document.getElementById("last-update").textContent = new Date().toLocaleTimeString();
}

function setDisconnected(message) {
  document.getElementById("connected").textContent = "No";
  document.getElementById("connection-status").textContent = "Desconectado";
  document.getElementById("gripper-state").textContent = "-";
  document.getElementById("last-error").textContent = message;
  document.getElementById("last-update").textContent = new Date().toLocaleTimeString();
}

function fillJointControls() {
  state.jointAngles.forEach((angle, index) => {
    const slider = document.getElementById(`joint-slider-${index}`);
    slider.value = angle;
    document.getElementById(`joint-value-${index}`).textContent = `${angle}°`;
    document.getElementById(`joint-label-${index}`).textContent = `${jointNames[index]} (${angle}°)`;
  });
}

async function sendJointCommand() {
  const angles = jointNames.map((_, index) => {
    const value = Number(document.getElementById(`joint-slider-${index}`).value);
    return toRadians(value);
  });

  await postJson("/api/joints", { angles, duration: 0.8 });
  await fetchStatus();
}

async function sendGripperCommand(action) {
  await postJson("/api/gripper", { action });
  await fetchStatus();
}

async function sendHome() {
  await postJson("/api/home", {});
  await fetchStatus();
}

async function postJson(path, body) {
  try {
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
  } catch (error) {
    setDisconnected(error.message);
    throw error;
  }
}

function attachButtons() {
  document.getElementById("refresh-button").addEventListener("click", fetchStatus);
  document.getElementById("sync-button").addEventListener("click", fetchStatus);
  document.getElementById("move-button").addEventListener("click", sendJointCommand);
  document.getElementById("open-button").addEventListener("click", () => sendGripperCommand("open"));
  document.getElementById("close-button").addEventListener("click", () => sendGripperCommand("close"));
  document.getElementById("home-button").addEventListener("click", sendHome);
}

window.addEventListener("DOMContentLoaded", () => {
  buildJointControls();
  attachButtons();
  fetchStatus();
  setInterval(fetchStatus, 4000);
});
