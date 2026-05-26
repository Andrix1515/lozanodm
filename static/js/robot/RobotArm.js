/**
 * Niryo One — jerarquía cinemática y pivotes según mecanismo real.
 *
 * base_joint
 *  └ shoulder_joint
 *     └ upper_arm_link
 *        └ elbow_joint
 *           └ forearm_link
 *              └ forearm_roll_joint
 *                 └ wrist_support
 *                    └ wrist_pitch_joint
 *                       └ tool_roll_joint
 *                          └ gripper
 *
 * Marco del simulador: Y vertical, suelo XZ (Z del robot educativo → Y aquí).
 */

import * as THREE from "three";
import {
  JOINT_AXES,
  JOINT_KEYS,
  ARM_DOF,
  clampAngleRad,
  getLinkGeometry,
  getGripperConfig,
} from "../config/joints.js";
import { JointHandle } from "./JointHandle.js";
import { buildNiryoVisuals } from "./NiryoArmGeometry.js";
import { readEndEffectorWorld } from "../kinematics/forwardKinematics.js";

function createPivot(axis) {
  const g = new THREE.Group();
  g.userData.axis = axis;
  return g;
}

export class RobotArm extends THREE.Group {
  constructor(linkGeometry = null) {
    super();
    this.linkGeometry = linkGeometry ?? getLinkGeometry();
    this.jointGroups = [];
    this.jointHandles = [];
    this.ikChain = [];
    this._displayAngles = new Array(ARM_DOF).fill(0);
    this._targetAngles = new Array(ARM_DOF).fill(0);
    this._gripperOpen = 1;
    this._targetGripperOpen = 1;

    this._buildHierarchy();
    this.endEffector = new THREE.Object3D();
    this.gripperGroup.add(this.endEffector);
    this.endEffector.position.z =
      this.linkGeometry.gripperReach + 0.016;

    const eeAxes = new THREE.AxesHelper(0.04);
    eeAxes.material.depthTest = false;
    this.endEffector.add(eeAxes);
  }

  _buildHierarchy() {
    const g = this.linkGeometry;
    const visuals = buildNiryoVisuals(g);
    const forearmLen = g.forearmLinkLen ?? g.forearmRollOffset ?? 0.1;

    this.add(visuals.baseFixed);

    this.baseJoint = createPivot("y");
    this.baseJoint.position.y = g.baseHeight * 0.52;
    this.add(this.baseJoint);
    this.jointGroups.push(this.baseJoint);
    this.baseJoint.add(visuals.baseTurntable);
    this.baseJoint.add(visuals.shoulderColumn);

    this.shoulderJoint = createPivot("x");
    this.shoulderJoint.position.set(0, g.shoulderRise, 0);
    this.baseJoint.add(this.shoulderJoint);
    this.jointGroups.push(this.shoulderJoint);
    this.shoulderJoint.add(visuals.shoulderHinge);

    this.upperArmLink = new THREE.Group();
    this.shoulderJoint.add(this.upperArmLink);
    this.upperArmLink.add(visuals.upperArm);

    this.elbowJoint = createPivot("x");
    this.elbowJoint.position.z = g.upperArm;
    this.upperArmLink.add(this.elbowJoint);
    this.jointGroups.push(this.elbowJoint);
    this.elbowJoint.add(visuals.elbowHinge);

    this.forearmLink = new THREE.Group();
    this.elbowJoint.add(this.forearmLink);
    this.forearmLink.add(visuals.forearm);

    this.forearmRollJoint = createPivot("z");
    this.forearmRollJoint.position.z = forearmLen;
    this.forearmLink.add(this.forearmRollJoint);
    this.jointGroups.push(this.forearmRollJoint);
    this.forearmRollJoint.add(visuals.forearmRollHousing);

    this.wristSupport = new THREE.Group();
    this.forearmRollJoint.add(this.wristSupport);
    this.wristSupport.add(visuals.wristSupport);

    this.wristPitchJoint = createPivot("x");
    this.wristPitchJoint.position.z = g.forearm;
    this.wristSupport.add(this.wristPitchJoint);
    this.jointGroups.push(this.wristPitchJoint);
    this.wristPitchJoint.add(visuals.wristPitchAxle);

    this.toolRollJoint = createPivot("z");
    this.toolRollJoint.position.z = g.wristLength;
    this.wristPitchJoint.add(this.toolRollJoint);
    this.jointGroups.push(this.toolRollJoint);
    this.toolRollJoint.add(visuals.toolRollHousing);

    this.gripperGroup = visuals.gripper;
    this.toolRollJoint.add(this.gripperGroup);
    this.fingerL = visuals.fingerL;
    this.fingerR = visuals.fingerR;

    this._createHandles();
    this._buildIKChain();
  }

  _createHandles() {
    const radii = [0.14, 0.11, 0.1, 0.085, 0.075, 0.065];
    this.jointGroups.forEach((group, index) => {
      const axis = JOINT_AXES[index];
      const handle = new JointHandle(index, axis, radii[index]);
      group.add(handle);
      this.jointHandles.push(handle);
    });
  }

  _buildIKChain() {
    this.ikChain = this.jointGroups.map((group, index) => ({
      group,
      axis: JOINT_AXES[index],
      index,
    }));
  }

  _applyChainAngles(angles) {
    for (let i = 0; i < ARM_DOF; i += 1) {
      this.jointGroups[i].rotation[JOINT_AXES[i]] = angles[i] ?? 0;
    }
    this.updateMatrixWorld(true);
  }

  applyAngles(anglesRad, limits, immediate = false) {
    const src =
      anglesRad.length >= ARM_DOF ? anglesRad : anglesRad.slice(0, ARM_DOF);
    for (let i = 0; i < ARM_DOF; i += 1) {
      const key = JOINT_KEYS[i];
      const clamped = clampAngleRad(src[i] ?? 0, key, limits);
      this._targetAngles[i] = clamped;
      if (immediate) {
        this._displayAngles[i] = clamped;
      }
    }
    if (immediate) {
      this._applyChainAngles(this._displayAngles);
    }
    return [...this._targetAngles];
  }

  setGripperOpen(open01, immediate = false) {
    this._targetGripperOpen = Math.min(1, Math.max(0, open01));
    if (immediate) this._applyGripperVisual(this._targetGripperOpen);
  }

  setGripperClosed(closed) {
    this.setGripperOpen(closed ? 0 : 1);
  }

  _applyGripperVisual(open01) {
    this._gripperOpen = open01;
    const cfg = getGripperConfig();
    const t = 1 - open01;
    const spread =
      0.012 + ((Math.abs(cfg.closed_deg) || 70) / 70) * 0.022 * t;
    this.fingerL.position.x = -spread;
    this.fingerR.position.x = spread;
  }

  updateAnimation(dt, smoothing = 14) {
    const alpha = 1 - Math.exp(-smoothing * dt);
    let changed = false;

    for (let i = 0; i < ARM_DOF; i += 1) {
      const axis = JOINT_AXES[i];
      const cur = this._displayAngles[i];
      const tgt = this._targetAngles[i];
      if (Math.abs(cur - tgt) > 1e-5) {
        this._displayAngles[i] = cur + (tgt - cur) * alpha;
        this.jointGroups[i].rotation[axis] = this._displayAngles[i];
        changed = true;
      }
    }

    if (Math.abs(this._gripperOpen - this._targetGripperOpen) > 1e-4) {
      this._gripperOpen += (this._targetGripperOpen - this._gripperOpen) * alpha;
      this._applyGripperVisual(this._gripperOpen);
      changed = true;
    }

    if (changed) this.updateMatrixWorld(true);
    return changed;
  }

  getAngles() {
    return [...this._displayAngles];
  }

  getTargetAngles() {
    return [...this._targetAngles];
  }

  getEndEffectorPosition() {
    return readEndEffectorWorld(this.endEffector);
  }

  getPickables() {
    return this.jointHandles.map((h) => h.hitMesh);
  }
}
