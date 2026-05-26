/**
 * Control de cámara orbital con suavizado y reset.
 */

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

export class CameraController {
  constructor(camera, domElement) {
    this.camera = camera;
    this.controls = new OrbitControls(camera, domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.minDistance = 0.35;
    this.controls.maxDistance = 2.8;
    this.controls.maxPolarAngle = Math.PI * 0.49;
    this.controls.target.set(0.15, 0.35, 0.15);

    this.defaultPosition = new THREE.Vector3(0.75, 0.65, 0.85);
    this.defaultTarget = this.controls.target.clone();
    this.resetAnimation = null;
  }

  update() {
    this.controls.update();
    if (this.resetAnimation) {
      const { from, to, targetFrom, targetTo, t0 } = this.resetAnimation;
      const t = Math.min(1, (performance.now() - t0) / 700);
      const ease = 1 - Math.pow(1 - t, 3);
      this.camera.position.lerpVectors(from, to, ease);
      this.controls.target.lerpVectors(targetFrom, targetTo, ease);
      if (t >= 1) this.resetAnimation = null;
    }
  }

  reset() {
    this.resetAnimation = {
      from: this.camera.position.clone(),
      to: this.defaultPosition.clone(),
      targetFrom: this.controls.target.clone(),
      targetTo: this.defaultTarget.clone(),
      t0: performance.now(),
    };
  }
}
