"""
Filtra robot_config.json exportado de CoppeliaSim.
Solo articulaciones principales del Niryo One; excluye mecanismo interno de pinza.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "robot_config.json"

ARM_JOINT_COUNT = 6
ARM_PRIMARY_JOINT_NAMES = [
    "base_joint",
    "shoulder_joint",
    "elbow_joint",
    "forearm_roll_joint",
    "wrist_pitch_joint",
    "tool_roll_joint",
]
GRIPPER_DRIVE_NAMES = ("leftJoint1", "rightJoint1")

ARM_JOINT_ROLES = [
    "base",
    "shoulder",
    "elbow",
    "forearm_roll",
    "wrist_pitch",
    "tool_roll",
]

ARM_JOINT_LABELS = [
    "Base",
    "Hombro",
    "Codo",
    "Roll antebrazo",
    "Pitch muñeca",
    "Roll herramienta",
]

ARM_JOINT_AXES = ["y", "x", "x", "z", "x", "z"]


def _is_internal_gripper_joint(joint: dict[str, Any]) -> bool:
    name = joint.get("name", "")
    if name in GRIPPER_DRIVE_NAMES:
        return False
    if name in ("leftJoint", "rightJoint"):
        return True
    parent = joint.get("parent", "")
    if "Link" in parent and "Niryo" in parent:
        return True
    if joint.get("limits", {}).get("cyclic"):
        return True
    return False


def _vec3(joint: dict[str, Any]) -> tuple[float, float, float]:
    p = joint["position_world"]
    return float(p["x"]), float(p["y"]), float(p["z"])


def _dist(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def _coppelia_to_sim_xyz(x: float, y: float, z: float, origin: tuple[float, float, float]) -> tuple[float, float, float]:
    """Convierte coordenadas CoppeliaSim a marco del simulador (Y arriba, base en origen)."""
    ox, oy, oz = origin
    return (x - ox, z - oz, -(y - oy))


def load_raw_config(path: Path | None = None) -> dict[str, Any]:
    path = path or CONFIG_PATH
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def extract_main_arm_joints(joints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extrae las 6 articulaciones principales del brazo en orden jerárquico."""
    named_joints = {
        joint["name"]: joint
        for joint in joints
        if joint.get("type") == "revolute"
        and joint.get("name") in ARM_PRIMARY_JOINT_NAMES
        and not _is_internal_gripper_joint(joint)
    }

    ordered: list[dict[str, Any]] = []
    for joint_name in ARM_PRIMARY_JOINT_NAMES:
        joint = named_joints.get(joint_name)
        if joint is not None:
            ordered.append(joint)
    if len(ordered) == ARM_JOINT_COUNT:
        return ordered

    arm: list[dict[str, Any]] = []
    for joint in joints:
        if joint.get("name") != "Joint":
            continue
        if joint.get("type") != "revolute":
            continue
        if _is_internal_gripper_joint(joint):
            continue
        arm.append(joint)
        if len(arm) >= ARM_JOINT_COUNT:
            break
    return arm


def extract_gripper_drive(joints: list[dict[str, Any]]) -> dict[str, Any] | None:
    for joint in joints:
        if joint.get("name") == "leftJoint1":
            return joint
    return None


def compute_link_geometry(arm_joints: list[dict[str, Any]]) -> dict[str, float]:
    """Longitudes de eslabones a partir de posiciones mundiales filtradas."""
    if len(arm_joints) < 2:
        return _default_link_geometry()

    origin = _vec3(arm_joints[0])
    sim_pts = [_coppelia_to_sim_xyz(*_vec3(j), origin) for j in arm_joints]

    def seg_len(i: int, j: int) -> float:
        return _dist(sim_pts[i], sim_pts[j])

    base_h = max(0.08, float(arm_joints[0]["position_world"]["z"]))
    shoulder_rise = max(0.05, seg_len(0, 1))
    upper_arm = max(0.14, seg_len(1, 2))
    forearm_link_len = max(0.06, seg_len(2, 3)) if len(sim_pts) > 3 else 0.1
    forearm = max(0.06, seg_len(3, 4)) if len(sim_pts) > 4 else 0.11
    wrist_seg = max(0.03, seg_len(4, 5)) if len(sim_pts) > 5 else 0.045

    gripper_reach = 0.055
    if upper_arm > 0:
        gripper_reach = max(0.04, upper_arm * 0.22)

    return {
        "baseRadius": 0.11,
        "baseHeight": round(base_h, 4),
        "shoulderRise": round(shoulder_rise, 4),
        "upperArm": round(upper_arm, 4),
        "forearmLinkLen": round(forearm_link_len, 4),
        "forearmRollOffset": round(forearm_link_len, 4),
        "forearm": round(forearm, 4),
        "wristLength": round(wrist_seg, 4),
        "gripperReach": round(gripper_reach, 4),
        "linkRadius": 0.038,
    }


def _default_link_geometry() -> dict[str, float]:
    return {
        "baseRadius": 0.11,
        "baseHeight": 0.095,
        "shoulderRise": 0.088,
        "upperArm": 0.21,
        "forearmLinkLen": 0.1,
        "forearmRollOffset": 0.1,
        "forearm": 0.11,
        "wristLength": 0.045,
        "gripperReach": 0.055,
        "linkRadius": 0.038,
    }


def build_simulator_config(path: Path | None = None) -> dict[str, Any]:
    raw = load_raw_config(path)
    joints = raw.get("joints", [])
    arm_joints = extract_main_arm_joints(joints)
    gripper_drive = extract_gripper_drive(joints)

    joint_limits: dict[str, list[float]] = {}
    for i, joint in enumerate(arm_joints):
        lim = joint.get("limits", {})
        key = f"joint{i + 1}"
        joint_limits[key] = [float(lim.get("min", -180)), float(lim.get("max", 180))]

    gripper_limits = {"min": 0.0, "max": 1.0, "open_deg": 0.0, "closed_deg": -70.0}
    if gripper_drive:
        lim = gripper_drive.get("limits", {})
        gripper_limits["closed_deg"] = float(lim.get("min", -70))
        gripper_limits["open_deg"] = float(lim.get("max", 0))

    serialized_arm = []
    for i, joint in enumerate(arm_joints):
        serialized_arm.append({
            "index": i,
            "role": ARM_JOINT_ROLES[i] if i < len(ARM_JOINT_ROLES) else f"joint{i + 1}",
            "label": ARM_JOINT_LABELS[i] if i < len(ARM_JOINT_LABELS) else f"Joint {i + 1}",
            "axis": ARM_JOINT_AXES[i] if i < len(ARM_JOINT_AXES) else "z",
            "limits_deg": joint_limits.get(f"joint{i + 1}", [-180, 180]),
            "orientation_world_deg": joint.get("orientation_world_deg", {}),
        })

    return {
        "robot_name": raw.get("robot_name", "NiryoOne"),
        "arm_dof": ARM_JOINT_COUNT,
        "backend_joint_count": ARM_JOINT_COUNT,
        "arm_joints": serialized_arm,
        "joint_limits": joint_limits,
        "joint_labels": ARM_JOINT_LABELS,
        "link_geometry": compute_link_geometry(arm_joints),
        "gripper": gripper_limits,
        "filtered_joint_count": len(arm_joints),
        "ignored_joint_count": len(joints) - len(arm_joints) - (1 if gripper_drive else 0),
    }
