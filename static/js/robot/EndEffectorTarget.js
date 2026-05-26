/**
 * Esfera objetivo arrastrable en el espacio de trabajo.
 * Al moverla se dispara el solver IK (CCD).
 */

import * as THREE from "three";

export class EndEffectorTarget extends THREE.Group {
  constructor(position = new THREE.Vector3(0.35, 0.35, 0.25)) {
    super();
    this.userData.isTarget = true;

    const core = new THREE.Mesh(
      new THREE.SphereGeometry(0.035, 16, 16),
      new THREE.MeshBasicMaterial({ color: 0xff6b00, transparent: true, opacity: 0.95 })
    );
    this.add(core);

    const halo = new THREE.Mesh(
      new THREE.SphereGeometry(0.055, 12, 12),
      new THREE.MeshBasicMaterial({
        color: 0xff6b00,
        wireframe: true,
        transparent: true,
        opacity: 0.35,
      })
    );
    this.add(halo);

    const ring = new THREE.Mesh(
      new THREE.RingGeometry(0.07, 0.075, 32),
      new THREE.MeshBasicMaterial({
        color: 0xff6b00,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.5,
      })
    );
    ring.rotation.x = -Math.PI / 2;
    this.add(ring);

    this.position.copy(position);
    this.hitMesh = new THREE.Mesh(
      new THREE.SphereGeometry(0.08, 12, 12),
      new THREE.MeshBasicMaterial({ visible: false })
    );
    this.add(this.hitMesh);
  }

  setActive(active) {
    this.children[0].material.opacity = active ? 1 : 0.85;
  }
}
