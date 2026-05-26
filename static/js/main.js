/**
 * Entrada del simulador Niryo One (config filtrada + escena 3D).
 */

import { SimulatorApp } from "./scene/SimulatorApp.js";
import { initDashboard, refreshDashboard } from "./ui/dashboard.js";
import { initJointControls, bindSimulator, scheduleStatusPoll } from "./ui/jointControls.js";
import { fetchConfig, fetchStatus } from "./core/api.js";
import { loadRobotModel } from "./config/robotModel.js";
import { appState, ControlMode } from "./core/state.js";
import { degToRad } from "./config/joints.js";

async function bootstrap() {
  const canvas = document.getElementById("sim-canvas");
  if (!canvas) return;

  const model = await loadRobotModel();
  appState.setRobotModel(model);

  initDashboard();
  initJointControls();
  refreshDashboard();

  const simulator = new SimulatorApp(canvas, model.link_geometry);
  bindSimulator(simulator);

  const status = await fetchStatus();
  if (status?.joint_positions) {
    simulator.robot.applyAngles(appState.jointAngles, appState.jointLimits, true);
    simulator.robot.setGripperOpen(appState.gripperOpen, true);
  } else {
    simulator.setAngles(
      [
        0,
        degToRad(-17),
        degToRad(46),
        0,
        degToRad(-8),
        0,
      ],
      ControlMode.SYNC
    );
    simulator.setGripperOpen(1, ControlMode.SYNC);
  }

  await fetchConfig();
  refreshDashboard();
  scheduleStatusPoll();
}

bootstrap();
