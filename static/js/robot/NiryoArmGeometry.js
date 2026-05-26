/**
 * Geometría procedural low-poly del Niryo One.
 * Eslabones rígidos a lo largo de +Z local; bisagras de elevación en X;
 * rolls longitudinales en Z; base en Y.
 */

import * as THREE from "three";
import { getNiryoMaterials } from "./materials.js";

function roundedBox(w, h, d, seg = 2) {
  return new THREE.BoxGeometry(w, h, d, seg, seg, seg);
}

function addShell(group, geometry, material, position, rotation = null) {
  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.copy(position);
  if (rotation) mesh.rotation.copy(rotation);
  group.add(mesh);
  return mesh;
}

/** Cilindro con eje a lo largo de +Z */
function tubeAlongZ(radiusTop, radiusBottom, length, segments = 10) {
  const g = new THREE.CylinderGeometry(
    radiusTop,
    radiusBottom,
    length,
    segments
  );
  g.rotateX(Math.PI / 2);
  return g;
}

/**
 * @param {import('../config/robotModel.js').DEFAULT_LINK_GEOMETRY} g
 */
export function buildNiryoVisuals(g) {
  const mat = getNiryoMaterials();
  const parts = {};
  const r = g.linkRadius;
  const forearmLen = g.forearmLinkLen ?? g.forearmRollOffset ?? 0.1;

  const baseFixed = new THREE.Group();
  addShell(
    baseFixed,
    new THREE.CylinderGeometry(
      g.baseRadius * 1.34,
      g.baseRadius * 1.42,
      g.baseHeight * 0.38,
      14
    ),
    mat.joint,
    new THREE.Vector3(0, g.baseHeight * 0.19, 0)
  );
  const baseRing = new THREE.Mesh(
    new THREE.TorusGeometry(g.baseRadius * 1.08, 0.009, 8, 24),
    mat.accent
  );
  baseRing.rotation.x = Math.PI / 2;
  baseRing.position.y = g.baseHeight * 0.36;
  baseFixed.add(baseRing);
  parts.baseFixed = baseFixed;

  const baseTurntable = new THREE.Group();
  addShell(
    baseTurntable,
    new THREE.CylinderGeometry(
      g.baseRadius * 1.12,
      g.baseRadius * 1.2,
      g.baseHeight * 0.34,
      14
    ),
    mat.joint,
    new THREE.Vector3(0, g.baseHeight * 0.17, 0)
  );
  addShell(
    baseTurntable,
    new THREE.CylinderGeometry(
      g.baseRadius * 0.88,
      g.baseRadius * 0.95,
      g.baseHeight * 0.42,
      14
    ),
    mat.shell,
    new THREE.Vector3(0, g.baseHeight * 0.42, 0)
  );
  parts.baseTurntable = baseTurntable;

  const shoulderColumn = new THREE.Group();
  addShell(
    shoulderColumn,
    roundedBox(r * 2.4, g.shoulderRise * 0.88, r * 2.1),
    mat.shell,
    new THREE.Vector3(0, g.shoulderRise * 0.42, -r * 0.35)
  );
  addShell(
    shoulderColumn,
    roundedBox(r * 1.5, g.shoulderRise * 0.35, r * 1.35),
    mat.accentDim,
    new THREE.Vector3(0, g.shoulderRise * 0.12, -r * 0.2)
  );
  parts.shoulderColumn = shoulderColumn;

  const shoulderHinge = new THREE.Group();
  addShell(
    shoulderHinge,
    new THREE.CylinderGeometry(r * 1.22, r * 1.22, r * 2.5, 12),
    mat.joint,
    new THREE.Vector3(0, 0, 0),
    new THREE.Euler(0, 0, Math.PI / 2)
  );
  addShell(
    shoulderHinge,
    roundedBox(r * 1.7, r * 1.45, r * 1.55),
    mat.accentDim,
    new THREE.Vector3(-r * 0.55, 0, 0)
  );
  parts.shoulderHinge = shoulderHinge;

  const upperArmGroup = new THREE.Group();
  const upperLen = g.upperArm;
  addShell(
    upperArmGroup,
    tubeAlongZ(r * 1.05, r * 0.9, upperLen),
    mat.shell,
    new THREE.Vector3(0, 0, upperLen * 0.5)
  );
  addShell(
    upperArmGroup,
    tubeAlongZ(r * 1.08, r * 1.08, upperLen * 0.12),
    mat.accent,
    new THREE.Vector3(0, 0, upperLen * 0.72)
  );
  parts.upperArm = upperArmGroup;

  parts.elbowHinge = new THREE.Mesh(
    new THREE.CylinderGeometry(r * 1.12, r * 1.12, r * 2.1, 12),
    mat.joint
  );
  parts.elbowHinge.rotation.y = Math.PI / 2;

  const forearmGroup = new THREE.Group();
  addShell(
    forearmGroup,
    tubeAlongZ(r * 0.92, r * 0.78, forearmLen),
    mat.shell,
    new THREE.Vector3(0, 0, forearmLen * 0.5)
  );
  parts.forearm = forearmGroup;

  parts.forearmRollHousing = new THREE.Mesh(
    tubeAlongZ(r * 0.98, r * 0.98, r * 1.65),
    mat.joint
  );
  parts.forearmRollHousing.position.z = 0;

  const wristSupport = new THREE.Group();
  const forkW = r * 2.35;
  const forkH = r * 1.85;
  const forkD = g.forearm * 0.92;
  addShell(
    wristSupport,
    roundedBox(r * 0.42, forkH, forkD),
    mat.joint,
    new THREE.Vector3(-forkW * 0.42, 0, forkD * 0.48)
  );
  addShell(
    wristSupport,
    roundedBox(r * 0.42, forkH, forkD),
    mat.joint,
    new THREE.Vector3(forkW * 0.42, 0, forkD * 0.48)
  );
  addShell(
    wristSupport,
    roundedBox(forkW * 0.55, r * 0.38, r * 0.55),
    mat.accentDim,
    new THREE.Vector3(0, -forkH * 0.38, forkD * 0.12)
  );
  parts.wristSupport = wristSupport;

  parts.wristPitchAxle = new THREE.Mesh(
    tubeAlongZ(r * 0.34, r * 0.34, forkW * 1.05),
    mat.accent
  );
  parts.wristPitchAxle.position.z = forkD * 0.48;

  parts.toolRollHousing = new THREE.Mesh(
    tubeAlongZ(r * 0.82, r * 0.82, r * 1.15),
    mat.joint
  );

  const gripperGroup = new THREE.Group();
  addShell(
    gripperGroup,
    roundedBox(r * 1.75, r * 1.25, g.gripperReach * 1.05),
    mat.shell,
    new THREE.Vector3(0, 0, g.gripperReach * 0.28)
  );
  addShell(
    gripperGroup,
    roundedBox(r * 1.35, r * 0.55, g.gripperReach * 0.45),
    mat.joint,
    new THREE.Vector3(0, 0, g.gripperReach * 0.62)
  );

  const fingerGeom = roundedBox(0.012, 0.032, g.gripperReach * 0.95);
  parts.fingerL = new THREE.Mesh(fingerGeom, mat.gripperPad);
  parts.fingerR = new THREE.Mesh(fingerGeom, mat.gripperPad);
  parts.fingerL.position.set(-0.018, 0, g.gripperReach * 0.78);
  parts.fingerR.position.set(0.018, 0, g.gripperReach * 0.78);
  gripperGroup.add(parts.fingerL, parts.fingerR);

  const fingerAccent = new THREE.Mesh(
    new THREE.BoxGeometry(0.007, 0.011, g.gripperReach * 0.32),
    mat.accent
  );
  fingerAccent.position.z = g.gripperReach * 0.52;
  parts.fingerL.add(fingerAccent.clone());
  parts.fingerR.add(fingerAccent.clone());
  parts.gripper = gripperGroup;

  return parts;
}
