/**
 * IK CCD — cadena principal de 6 articulaciones (Niryo One).
 */

import * as THREE from "three";
import { clampAngleRad, JOINT_KEYS, ARM_DOF } from "../config/joints.js";

const _target = new THREE.Vector3();
const _effector = new THREE.Vector3();
const _jointWorld = new THREE.Vector3();
const _toTarget = new THREE.Vector3();
const _toEffector = new THREE.Vector3();
const _axis = new THREE.Vector3();
const _cross = new THREE.Vector3();
const _quat = new THREE.Quaternion();

function applyChainAngles(chain, angles) {
  for (let i = 0; i < chain.length; i += 1) {
    const { group, axis, index } = chain[i];
    if (index >= ARM_DOF) continue;
    group.rotation[axis] = angles[index];
  }
  if (chain.length > 0) {
    chain[0].group.updateMatrixWorld(true);
  }
}

/**
 * @returns {{ angles: number[], distance: number }}
 */
export function solveCCD({
  endEffector,
  chain,
  target,
  angles,
  limits,
  iterations = 12,
  stepGain = 0.55,
}) {
  const result = angles.slice(0, ARM_DOF);
  while (result.length < ARM_DOF) result.push(0);

  _target.copy(target);
  applyChainAngles(chain, result);

  for (let iter = 0; iter < iterations; iter += 1) {
    for (let i = chain.length - 1; i >= 0; i -= 1) {
      const { group, axis, index } = chain[i];
      if (index >= ARM_DOF) continue;
      
      // Regla de IK: ignorar forearm_roll_joint (3) y tool_roll_joint (5) para posicionamiento básico
      if (index === 3 || index === 5) continue;

      group.getWorldPosition(_jointWorld);
      endEffector.getWorldPosition(_effector);

      if (axis === "x") _axis.set(1, 0, 0);
      else if (axis === "y") _axis.set(0, 1, 0);
      else _axis.set(0, 0, 1);
      _axis.applyQuaternion(group.getWorldQuaternion(_quat)).normalize();

      _toTarget.subVectors(_target, _jointWorld).projectOnPlane(_axis).normalize();
      _toEffector.subVectors(_effector, _jointWorld).projectOnPlane(_axis).normalize();

      if (_toTarget.lengthSq() < 1e-6 || _toEffector.lengthSq() < 1e-6) continue;

      _cross.crossVectors(_toEffector, _toTarget);
      const dot = _toEffector.dot(_toTarget);
      const delta = Math.atan2(_cross.dot(_axis), dot) * stepGain;

      const jointKey = JOINT_KEYS[index];
      result[index] = clampAngleRad(result[index] + delta, jointKey, limits);
      group.rotation[axis] = result[index];
      group.updateMatrixWorld(true);
    }
  }

  endEffector.getWorldPosition(_effector);
  const distance = _effector.distanceTo(_target);

  return { angles: result, distance };
}
