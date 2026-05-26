import json
import math
from coppeliasim_zmqremoteapi_client import RemoteAPIClient

# -----------------------------------------
# CONNECT TO COPPELIASIM
# -----------------------------------------

client = RemoteAPIClient()
sim = client.require('sim')

print("Connected to CoppeliaSim")

# -----------------------------------------
# HELPERS
# -----------------------------------------

def rad_to_deg(rad):
    return rad * 180.0 / math.pi

def get_joint_type_name(joint_type):
    if joint_type == sim.joint_revolute_subtype:
        return "revolute"
    elif joint_type == sim.joint_prismatic_subtype:
        return "prismatic"
    elif joint_type == sim.joint_spherical_subtype:
        return "spherical"
    return "unknown"

# -----------------------------------------
# GET ALL OBJECTS IN SCENE
# -----------------------------------------

objects = sim.getObjectsInTree(sim.handle_scene)

robot_data = {
    "robot_name": "AutoExtractedRobot",
    "joints": []
}

print(f"Found {len(objects)} objects in scene")

# -----------------------------------------
# EXTRACT JOINT DATA
# -----------------------------------------

for obj in objects:

    obj_type = sim.getObjectType(obj)

    if obj_type == sim.object_joint_type:

        try:

            name = sim.getObjectAlias(obj)

            # Joint subtype
            joint_subtype = sim.getJointType(obj)
            joint_type = get_joint_type_name(joint_subtype)

            # Current position
            current_position = sim.getJointPosition(obj)

            # Limits
            cyclic, interval = sim.getJointInterval(obj)

            # Parent
            parent = sim.getObjectParent(obj)

            if parent != -1:
                parent_name = sim.getObjectAlias(parent)
            else:
                parent_name = None

            # Position in world
            position = sim.getObjectPosition(obj, sim.handle_world)

            # Orientation in world
            orientation = sim.getObjectOrientation(obj, sim.handle_world)

            # Convert orientation to degrees
            orientation_deg = [
                rad_to_deg(orientation[0]),
                rad_to_deg(orientation[1]),
                rad_to_deg(orientation[2])
            ]

            # Convert interval to degrees if revolute
            if joint_type == "revolute":
                min_angle = rad_to_deg(interval[0])
                max_angle = rad_to_deg(interval[0] + interval[1])
                current_deg = rad_to_deg(current_position)
            else:
                min_angle = interval[0]
                max_angle = interval[0] + interval[1]
                current_deg = current_position

            joint_data = {
                "name": name,
                "type": joint_type,
                "parent": parent_name,

                "position_world": {
                    "x": position[0],
                    "y": position[1],
                    "z": position[2]
                },

                "orientation_world_deg": {
                    "x": orientation_deg[0],
                    "y": orientation_deg[1],
                    "z": orientation_deg[2]
                },

                "limits": {
                    "cyclic": cyclic,
                    "min": min_angle,
                    "max": max_angle
                },

                "current_position": current_deg
            }

            robot_data["joints"].append(joint_data)

            print(f"Extracted joint: {name}")

        except Exception as e:
            print(f"Error processing object: {e}")

# -----------------------------------------
# SAVE JSON
# -----------------------------------------

with open("robot_config.json", "w") as f:
    json.dump(robot_data, f, indent=4)

print("\nrobot_config.json exported successfully!")
print(f"Total joints extracted: {len(robot_data['joints'])}")