/**
 * Configuración del Niryo One derivada de robot_config.json (filtrada).
 * 6 articulaciones principales + pinza simplificada.
 */

export const ARM_DOF = 6;
export const BACKEND_JOINT_COUNT = 6;

export const JOINT_LABELS = [
  "Base",
  "Hombro",
  "Codo",
  "Roll antebrazo",
  "Pitch muñeca",
  "Roll herramienta",
];

/** Jerarquía CoppeliaSim / Niryo One (orden de la cadena) */
export const ARM_PRIMARY_JOINT_NAMES = [
  "base_joint",
  "shoulder_joint",
  "elbow_joint",
  "forearm_roll_joint",
  "wrist_pitch_joint",
  "tool_roll_joint",
];

export const JOINT_KEYS = [
  "joint1",
  "joint2",
  "joint3",
  "joint4",
  "joint5",
  "joint6",
];
export const BACKEND_KEYS = [...JOINT_KEYS];

/**
 * Ejes locales (simulador Y-up, brazo extendido en +Z):
 * base Y | hombro/codo X (elevación) | rolls Z | pitch muñeca X
 */
export const JOINT_AXES = ["y", "x", "x", "z", "x", "z"];

export const DEFAULT_JOINT_LIMITS = {
  joint1: [-175, 175],
  joint2: [-90, 37],
  joint3: [-80, 90],
  joint4: [-175, 175],
  joint5: [-100, 110],
  joint6: [-147, 147],
};

export const DEFAULT_LINK_GEOMETRY = {
  baseRadius: 0.11,
  baseHeight: 0.095,
  shoulderRise: 0.088,
  upperArm: 0.21,
  /** Longitud del antebrazo rígido (codo → forearm_roll) */
  forearmLinkLen: 0.1,
  forearmRollOffset: 0.1,
  /** Tramo roll → pitch muñeca (soporte en U) */
  forearm: 0.11,
  wristLength: 0.045,
  gripperReach: 0.055,
  linkRadius: 0.038,
};

export const DEFAULT_GRIPPER = {
  min: 0,
  max: 1,
  open_deg: 0,
  closed_deg: -70,
};

/** @type {import('./robotModel.js').SimulatorModelConfig | null} */
let _model = null;

export function getRobotModel() {
  return _model;
}

export function getLinkGeometry() {
  return _model?.link_geometry ?? DEFAULT_LINK_GEOMETRY;
}

export function getJointLimits() {
  return _model?.joint_limits ?? DEFAULT_JOINT_LIMITS;
}

export function getGripperConfig() {
  return _model?.gripper ?? DEFAULT_GRIPPER;
}

export async function loadRobotModel() {
  try {
    const response = await fetch("/api/robot-config");
    if (response.ok) {
      _model = await response.json();
      return _model;
    }
  } catch {
    /* fallback estático */
  }

  try {
    const response = await fetch("/static/robot_config.json");
    if (response.ok) {
      const raw = await response.json();
      _model = parseRawExport(raw);
      return _model;
    }
  } catch {
    /* defaults */
  }

  _model = {
    arm_dof: ARM_DOF,
    link_geometry: { ...DEFAULT_LINK_GEOMETRY },
    joint_limits: { ...DEFAULT_JOINT_LIMITS },
    gripper: { ...DEFAULT_GRIPPER },
    arm_joints: JOINT_LABELS.map((label, i) => ({
      index: i,
      label,
      axis: JOINT_AXES[i],
      limits_deg: DEFAULT_JOINT_LIMITS[JOINT_KEYS[i]],
    })),
  };
  return _model;
}

/** Parser cliente si no hay endpoint */
export function parseRawExport(raw) {
  const joints = raw.joints ?? [];
  const joint_limits = { ...DEFAULT_JOINT_LIMITS };

  const namedArm = ARM_PRIMARY_JOINT_NAMES.map((name) =>
    joints.find((j) => j.name === name && j.type === "revolute")
  ).filter(Boolean);

  const arm =
    namedArm.length === ARM_DOF
      ? namedArm
      : (() => {
          const fallback = [];
          for (const j of joints) {
            if (j.name !== "Joint" || j.type !== "revolute") continue;
            if (j.limits?.cyclic) continue;
            fallback.push(j);
            if (fallback.length >= ARM_DOF) break;
          }
          return fallback;
        })();

  arm.forEach((j, i) => {
    const key = JOINT_KEYS[i];
    joint_limits[key] = [j.limits.min, j.limits.max];
  });

  const gripperDrive = joints.find((j) => j.name === "leftJoint1");
  const gripper = { ...DEFAULT_GRIPPER };
  if (gripperDrive?.limits) {
    gripper.closed_deg = gripperDrive.limits.min;
    gripper.open_deg = gripperDrive.limits.max;
  }

  return {
    robot_name: raw.robot_name ?? "NiryoOne",
    arm_dof: ARM_DOF,
    link_geometry: estimateLinkGeometry(arm),
    joint_limits,
    gripper,
    arm_joints: arm.map((_, i) => ({
      index: i,
      label: JOINT_LABELS[i],
      axis: JOINT_AXES[i],
      limits_deg: joint_limits[JOINT_KEYS[i]],
    })),
  };
}

function estimateLinkGeometry(arm) {
  if (arm.length < 2) return { ...DEFAULT_LINK_GEOMETRY };

  const origin = arm[0].position_world;
  const toSim = (p) => ({
    x: p.x - origin.x,
    y: p.z - origin.z,
    z: -(p.y - origin.y),
  });

  const pts = arm.map((j) => toSim(j.position_world));
  const dist = (a, b) =>
    Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);

  const g = { ...DEFAULT_LINK_GEOMETRY };
  g.baseHeight = Math.max(0.08, arm[0].position_world.z);
  g.shoulderRise = Math.max(0.05, dist(pts[0], pts[1]));
  g.upperArm = Math.max(0.14, dist(pts[1], pts[2]));

  if (pts[3]) {
    const forearmLink = Math.max(0.06, dist(pts[2], pts[3]));
    g.forearmLinkLen = forearmLink;
    g.forearmRollOffset = forearmLink;
    g.forearm = Math.max(0.06, pts[4] ? dist(pts[3], pts[4]) : 0.11);
  }
  if (pts[4] && pts[5]) {
    g.wristLength = Math.max(0.03, dist(pts[4], pts[5]));
  }

  return g;
}

export function degToRad(deg) {
  return (deg * Math.PI) / 180;
}

export function radToDeg(rad) {
  return (rad * 180) / Math.PI;
}

export function clampAngleRad(angle, jointKey, limits) {
  const [minDeg, maxDeg] = limits[jointKey] ?? [-180, 180];
  const min = degToRad(minDeg);
  const max = degToRad(maxDeg);
  return Math.min(Math.max(angle, min), max);
}

/** Estado sim (6) → payload Coppelia (6) */
export function toBackendAngles(armAnglesRad) {
  const a = armAnglesRad ?? [];
  return [
    a[0] ?? 0,
    a[1] ?? 0,
    a[2] ?? 0,
    a[3] ?? 0,
    a[4] ?? 0,
    a[5] ?? 0,
  ];
}

/** Coppelia (6) → estado sim (6) */
export function fromBackendAngles(backend) {
  if (!backend || backend.length < ARM_DOF) {
    return { arm: new Array(ARM_DOF).fill(0) };
  }
  return { arm: backend.slice(0, ARM_DOF) };
}

export function gripperOpenFromClosed(closed) {
  return closed ? 0 : 1;
}

export function gripperClosedFromOpen(open01) {
  return open01 < 0.5;
}
