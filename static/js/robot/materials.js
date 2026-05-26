/**
 * Materiales compartidos — paleta Niryo One (bajo número de draw calls).
 */

import * as THREE from "three";

let _cache = null;

export function getNiryoMaterials() {
  if (_cache) return _cache;

  _cache = {
    shell: new THREE.MeshStandardMaterial({
      color: 0xe8eef5,
      metalness: 0.1,
      roughness: 0.5,
    }),
    joint: new THREE.MeshStandardMaterial({
      color: 0x121212,
      metalness: 0.35,
      roughness: 0.42,
    }),
    accent: new THREE.MeshStandardMaterial({
      color: 0xff6b00,
      metalness: 0.25,
      roughness: 0.38,
      emissive: 0x331800,
      emissiveIntensity: 0.12,
    }),
    accentDim: new THREE.MeshStandardMaterial({
      color: 0xcc5500,
      metalness: 0.2,
      roughness: 0.5,
    }),
    gripperPad: new THREE.MeshStandardMaterial({
      color: 0x1e1e1e,
      metalness: 0.2,
      roughness: 0.65,
    }),
    gizmo: new THREE.MeshBasicMaterial({
      color: 0xff6b00,
      transparent: true,
      opacity: 0.55,
      depthWrite: false,
    }),
  };
  return _cache;
}
