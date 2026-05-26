/**
 * Cinemática directa sobre la jerarquía del brazo simulado.
 * Usa la matriz mundial del marcador del efector final en Three.js.
 */

import * as THREE from "three";

export function readEndEffectorWorld(eeObject) {
  const pos = new THREE.Vector3();
  eeObject.getWorldPosition(pos);
  return { x: pos.x, y: pos.y, z: pos.z };
}

export function readJointWorldPositions(jointGroups) {
  return jointGroups.map((group) => {
    const v = new THREE.Vector3();
    group.getWorldPosition(v);
    return { x: v.x, y: v.y, z: v.z };
  });
}
