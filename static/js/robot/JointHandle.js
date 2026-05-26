/**
 * Anillo de rotación (gizmo) alrededor de cada articulación.
 * Permite arrastrar con el ratón para ajustar el ángulo de la junta.
 */

import * as THREE from "three";

const _plane = new THREE.Plane();
const _intersection = new THREE.Vector3();
const _currentVec = new THREE.Vector3();
const _normal = new THREE.Vector3();
const _cross = new THREE.Vector3();

export class JointHandle extends THREE.Group {
  /**
   * @param {number} index - índice de articulación (0-5)
   * @param {'x'|'y'|'z'} axis
   * @param {number} radius
   */
  constructor(index, axis, radius = 0.11) {
    super();
    this.jointIndex = index;
    this.axis = axis;
    this.userData.isJointHandle = true;

    const geometry = new THREE.TorusGeometry(radius, 0.012, 8, 48);
    const material = new THREE.MeshBasicMaterial({
      color: 0xff6b00,
      transparent: true,
      opacity: 0.5,
      depthWrite: false,
    });
    this.ring = new THREE.Mesh(geometry, material);
    if (axis === "x") this.ring.rotation.y = Math.PI / 2;
    if (axis === "y") this.ring.rotation.x = Math.PI / 2;
    this.add(this.ring);

    const hit = new THREE.Mesh(
      new THREE.TorusGeometry(radius, 0.035, 6, 32),
      new THREE.MeshBasicMaterial({ visible: false })
    );
    if (axis === "x") hit.rotation.y = Math.PI / 2;
    if (axis === "y") hit.rotation.x = Math.PI / 2;
    this.add(hit);
    this.hitMesh = hit;
  }

  getWorldAxis(target = new THREE.Vector3()) {
    if (this.axis === "x") target.set(1, 0, 0);
    else if (this.axis === "y") target.set(0, 1, 0);
    else target.set(0, 0, 1);
    this.localToWorld(target);
    const origin = new THREE.Vector3();
    this.getWorldPosition(origin);
    return target.sub(origin).normalize();
  }

  beginDrag(raycaster) {
    const origin = new THREE.Vector3();
    this.getWorldPosition(origin);
    this.getWorldAxis(_normal);
    _plane.setFromNormalAndCoplanarPoint(_normal, origin);
    if (!raycaster.ray.intersectPlane(_plane, _intersection)) return false;

    this._dragStartVec = _intersection.clone().sub(origin).normalize();
    this._startAngle = this.parent?.rotation?.[this.axis] ?? 0;
    return true;
  }

  /** Ángulo absoluto (rad) durante el arrastre */
  angleFromDrag(raycaster) {
    if (!this._dragStartVec) return this._startAngle ?? 0;

    const origin = new THREE.Vector3();
    this.getWorldPosition(origin);
    this.getWorldAxis(_normal);
    _plane.setFromNormalAndCoplanarPoint(_normal, origin);
    if (!raycaster.ray.intersectPlane(_plane, _intersection)) {
      return this._startAngle;
    }

    _currentVec.subVectors(_intersection, origin).normalize();
    _cross.crossVectors(this._dragStartVec, _currentVec);
    const dot = this._dragStartVec.dot(_currentVec);
    const delta = Math.atan2(_cross.dot(_normal), dot);
    return this._startAngle + delta;
  }

  endDrag() {
    this._dragStartVec = null;
  }

  setHighlight(active) {
    this.ring.material.color.setHex(active ? 0xffaa55 : 0xff6b00);
    this.ring.material.opacity = active ? 0.85 : 0.5;
  }

  setLimitWarning(nearLimit) {
    if (nearLimit) this.ring.material.color.setHex(0xfbbf24);
    else if (!this.ring.material.opacity || this.ring.material.opacity < 0.6) {
      this.ring.material.color.setHex(0xff6b00);
    }
  }
}
