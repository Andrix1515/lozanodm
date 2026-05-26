/**
 * Estado central del simulador (6 DOF brazo + pinza).
 */

import { DEFAULT_JOINT_LIMITS, ARM_DOF } from "../config/joints.js";

export const ControlMode = {
  MANUAL: "manual",
  GIZMO: "gizmo",
  TARGET: "target",
  SYNC: "sync",
};

class SimulatorState extends EventTarget {
  constructor() {
    super();
    this.jointAngles = new Array(ARM_DOF).fill(0);
    this.gripperOpen = 1;
    this.jointLimits = { ...DEFAULT_JOINT_LIMITS };
    this.gripperClosed = false;
    this.connected = false;
    this.lastError = "";
    this.controlMode = ControlMode.MANUAL;
    this.endEffector = { x: 0, y: 0, z: 0 };
    this.targetPosition = { x: 0.32, y: 0.38, z: 0.28 };
    this.ikStatus = {
      enabled: true,
      active: false,
      distance: 0,
      converged: false,
    };
    this.robotModel = null;
  }

  setRobotModel(model) {
    this.robotModel = model;
    if (model?.joint_limits) this.setLimits(model.joint_limits);
  }

  setJointAngles(angles, source = ControlMode.MANUAL) {
    this.jointAngles = angles.slice(0, ARM_DOF);
    while (this.jointAngles.length < ARM_DOF) this.jointAngles.push(0);
    this.controlMode = source;
    this.dispatchEvent(
      new CustomEvent("joints-changed", {
        detail: { angles: [...this.jointAngles], source },
      })
    );
  }

  setGripperOpen(value, source = ControlMode.MANUAL) {
    this.gripperOpen = Math.min(1, Math.max(0, value));
    this.gripperClosed = this.gripperOpen < 0.5;
    this.dispatchEvent(
      new CustomEvent("gripper-changed", {
        detail: { open: this.gripperOpen, source },
      })
    );
  }

  setEndEffector(pos) {
    this.endEffector = { ...pos };
    this.dispatchEvent(
      new CustomEvent("telemetry-changed", { detail: { endEffector: pos } })
    );
  }

  setIkStatus(status) {
    this.ikStatus = { ...this.ikStatus, ...status };
    this.dispatchEvent(
      new CustomEvent("ik-changed", { detail: { ...this.ikStatus } })
    );
  }

  setConnection(data) {
    this.connected = data.connected;
    this.lastError = data.last_error || data.error || "";
    this.gripperClosed = Boolean(data.gripper_closed);
    this.gripperOpen = this.gripperClosed ? 0 : 1;
    this.dispatchEvent(new CustomEvent("connection-changed", { detail: data }));
  }

  setLimits(limits) {
    this.jointLimits = limits;
    this.dispatchEvent(new CustomEvent("limits-changed", { detail: limits }));
  }
}

export const appState = new SimulatorState();
