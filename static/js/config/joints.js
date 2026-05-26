/**
 * Reexporta configuración del modelo Niryo (robot_config filtrado).
 */

export {
  ARM_DOF,
  BACKEND_JOINT_COUNT,
  JOINT_LABELS,
  JOINT_KEYS,
  BACKEND_KEYS,
  JOINT_AXES,
  DEFAULT_JOINT_LIMITS,
  degToRad,
  radToDeg,
  clampAngleRad,
  getLinkGeometry,
  getJointLimits,
  getGripperConfig,
  loadRobotModel,
  toBackendAngles,
  fromBackendAngles,
} from "./robotModel.js";
