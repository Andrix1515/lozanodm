/**
 * Escena Three.js — Niryo One, animación suave, IK CCD 6 DOF.
 */

import * as THREE from "three";
import { RobotArm } from "../robot/RobotArm.js";
import { EndEffectorTarget } from "../robot/EndEffectorTarget.js";
import { CameraController } from "./CameraController.js";
import { appState, ControlMode } from "../core/state.js";
import { solveCCD } from "../kinematics/inverseKinematics.js";
import { JOINT_KEYS, radToDeg, getLinkGeometry } from "../config/joints.js";

export class SimulatorApp {
  constructor(canvas, linkGeometry = null) {
    this.canvas = canvas;
    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    this.dragState = null;
    this.ikEnabled = true;
    this._ikDistance = 0;
    this._ikActive = false;
    this._clock = new THREE.Clock();

    this._initRenderer();
    this._initScene(linkGeometry);
    this._initInteraction();
    this._bindState();
    this._animate = this._animate.bind(this);
    requestAnimationFrame(this._animate);
  }

  _initRenderer() {
    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      antialias: true,
      alpha: true,
      powerPreference: "high-performance",
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setSize(this.canvas.clientWidth, this.canvas.clientHeight, false);
    this.renderer.shadowMap.enabled = false;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
  }

  _initScene(linkGeometry) {
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x050810);
    this.scene.fog = new THREE.Fog(0x050810, 2.2, 5.5);

    this.camera = new THREE.PerspectiveCamera(
      46,
      this.canvas.clientWidth / Math.max(this.canvas.clientHeight, 1),
      0.05,
      20
    );
    this.camera.position.set(0.7, 0.55, 0.8);

    this.cameraCtrl = new CameraController(this.camera, this.canvas);

    this.scene.add(new THREE.AmbientLight(0x8a9bb0, 0.5));
    const key = new THREE.DirectionalLight(0xffffff, 0.95);
    key.position.set(1, 1.8, 1.2);
    this.scene.add(key);
    const rim = new THREE.DirectionalLight(0xff8844, 0.25);
    rim.position.set(-0.8, 0.4, -1);
    this.scene.add(rim);

    const grid = new THREE.GridHelper(1.4, 16, 0x2a3548, 0x111827);
    grid.position.y = 0.001;
    this.scene.add(grid);

    const floor = new THREE.Mesh(
      new THREE.CircleGeometry(0.75, 24),
      new THREE.MeshStandardMaterial({
        color: 0x0c1018,
        metalness: 0.15,
        roughness: 0.92,
      })
    );
    floor.rotation.x = -Math.PI / 2;
    this.scene.add(floor);

    this.robot = new RobotArm(linkGeometry ?? getLinkGeometry());
    this.scene.add(this.robot);

    this.target = new EndEffectorTarget(
      new THREE.Vector3(
        appState.targetPosition.x,
        appState.targetPosition.y,
        appState.targetPosition.z
      )
    );
    this.scene.add(this.target);

    this._dragPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
    this._dragPoint = new THREE.Vector3();
    this._targetVec = new THREE.Vector3();
    this._eeVec = new THREE.Vector3();

    this._resize();
    window.addEventListener("resize", () => this._resize());
  }

  _bindState() {
    appState.addEventListener("joints-changed", (e) => {
      const src = e.detail.source;
      if (
        src === ControlMode.GIZMO ||
        src === ControlMode.TARGET ||
        src === ControlMode.MANUAL
      ) {
        return;
      }
      this.robot.applyAngles(e.detail.angles, appState.jointLimits);
    });

    appState.addEventListener("gripper-changed", (e) => {
      if (e.detail.source === ControlMode.MANUAL) return;
      this.robot.setGripperOpen(e.detail.open);
    });

    appState.addEventListener("connection-changed", () => {
      this.robot.setGripperOpen(appState.gripperOpen);
    });
  }

  setAngles(angles, source) {
    const applied = this.robot.applyAngles([...angles], appState.jointLimits);
    appState.setJointAngles(applied, source);
    this._updateTelemetry();
  }

  setGripperOpen(open, source = ControlMode.MANUAL) {
    this.robot.setGripperOpen(open);
    appState.setGripperOpen(open, source);
  }

  _updateTelemetry() {
    appState.setEndEffector(this.robot.getEndEffectorPosition());
    this._updateLimitWarnings();
    this._publishIkStatus();
  }

  _publishIkStatus() {
    appState.setIkStatus({
      enabled: this.ikEnabled,
      active: this._ikActive,
      distance: this._ikDistance,
      converged: this._ikDistance < 0.012,
    });
  }

  _updateLimitWarnings() {
    appState.jointAngles.forEach((rad, i) => {
      const key = JOINT_KEYS[i];
      const [minD, maxD] = appState.jointLimits[key] ?? [-180, 180];
      const deg = radToDeg(rad);
      const margin = 8;
      const near = deg <= minD + margin || deg >= maxD - margin;
      this.robot.jointHandles[i]?.setLimitWarning(near);
    });
  }

  _initInteraction() {
    this.canvas.addEventListener("pointerdown", (e) => this._onPointerDown(e));
    window.addEventListener("pointermove", (e) => this._onPointerMove(e));
    window.addEventListener("pointerup", () => this._onPointerUp());
    document.getElementById("reset-camera")?.addEventListener("click", () => {
      this.cameraCtrl.reset();
    });
  }

  _updatePointer(event) {
    const rect = this.canvas.getBoundingClientRect();
    this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  }

  _pickIntersects() {
    this.raycaster.setFromCamera(this.pointer, this.camera);
    return this.raycaster.intersectObjects(
      [...this.robot.getPickables(), this.target.hitMesh],
      false
    );
  }

  _onPointerDown(event) {
    if (event.button !== 0) return;
    this._updatePointer(event);
    const hits = this._pickIntersects();
    if (!hits.length) return;

    const hit = hits[0].object;
    this.cameraCtrl.controls.enabled = false;

    if (hit === this.target.hitMesh || hit.parent?.userData?.isTarget) {
      this._dragPlane.set(0, 1, 0, -this.target.position.y);
      this.dragState = { type: "target" };
      this.target.setActive(true);
      return;
    }

    const handle = this.robot.jointHandles.find(
      (h) => h.hitMesh === hit || h.hitMesh === hit.parent
    );
    if (handle) {
      handle.setHighlight(true);
      if (handle.beginDrag(this.raycaster)) {
        this.dragState = { type: "joint", handle };
      } else {
        handle.setHighlight(false);
        this.cameraCtrl.controls.enabled = true;
      }
    }
  }

  _onPointerMove(event) {
    if (!this.dragState) return;
    this._updatePointer(event);

    if (this.dragState.type === "target") {
      this.raycaster.setFromCamera(this.pointer, this.camera);
      if (this.raycaster.ray.intersectPlane(this._dragPlane, this._dragPoint)) {
        this.target.position.copy(this._dragPoint);
        appState.targetPosition = {
          x: this._dragPoint.x,
          y: this._dragPoint.y,
          z: this._dragPoint.z,
        };
      }
      return;
    }

    if (this.dragState.type === "joint") {
      const { handle } = this.dragState;
      this.raycaster.setFromCamera(this.pointer, this.camera);
      const next = [...appState.jointAngles];
      next[handle.jointIndex] = handle.angleFromDrag(this.raycaster);
      const applied = this.robot.applyAngles(next, appState.jointLimits, true);
      appState.setJointAngles(applied, ControlMode.GIZMO);
      this._updateTelemetry();
    }
  }

  _onPointerUp() {
    if (this.dragState?.type === "joint") {
      this.dragState.handle?.setHighlight(false);
      this.dragState.handle?.endDrag();
    }
    if (this.dragState?.type === "target") this.target.setActive(false);
    this.dragState = null;
    this.cameraCtrl.controls.enabled = true;
  }

  _runIK() {
    this._targetVec.set(
      appState.targetPosition.x,
      appState.targetPosition.y,
      appState.targetPosition.z
    );

    const { angles, distance } = solveCCD({
      endEffector: this.robot.endEffector,
      chain: this.robot.ikChain,
      target: this._targetVec,
      angles: this.robot.getTargetAngles(),
      limits: appState.jointLimits,
      iterations: 12,
    });

    this._ikDistance = distance;
    this._ikActive = true;
    this.setAngles(angles, ControlMode.TARGET);
  }

  _resize() {
    const w = this.canvas.clientWidth;
    const h = this.canvas.clientHeight;
    this.camera.aspect = w / Math.max(h, 1);
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h, false);
  }

  _animate() {
    requestAnimationFrame(this._animate);
    const dt = Math.min(this._clock.getDelta(), 0.05);

    if (this.ikEnabled && this.dragState?.type !== "joint") {
      this._runIK();
    } else {
      this._ikActive = false;
      this.robot.endEffector.getWorldPosition(this._eeVec);
      this._targetVec.set(
        appState.targetPosition.x,
        appState.targetPosition.y,
        appState.targetPosition.z
      );
      this._ikDistance = this._eeVec.distanceTo(this._targetVec);
      this._publishIkStatus();
    }

    if (this.robot.updateAnimation(dt)) {
      appState.setEndEffector(this.robot.getEndEffectorPosition());
    }

    this.cameraCtrl.update();
    this.renderer.render(this.scene, this.camera);
  }
}
