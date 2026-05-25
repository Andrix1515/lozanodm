"""
Abstract base class representing the universal robot API.
All concrete adapters (simulation and physical hardware) must implement this interface.
"""

from abc import ABC, abstractmethod

class BaseRobot(ABC):
    """
    BaseRobot defines the universal robot control interface.
    This ensures that the AI/Decision layer doesn't depend on direct servo or hardware libraries.
    """

    @abstractmethod
    def connect(self) -> bool:
        """
        Establishes connection to the robot (simulation or hardware).
        Returns:
            True if connection was successful, False otherwise.
        """
        pass

    @abstractmethod
    def disconnect(self):
        """
        Safely disconnects from the robot and stops ongoing operations.
        """
        pass

    @abstractmethod
    def move_home(self, duration: float = 2.0) -> bool:
        """
        Moves the robotic arm to its default home/reposo position.
        """
        pass

    @abstractmethod
    def move_to_zone(self, zone_name: str, duration: float = 3.0) -> bool:
        """
        Moves the robotic arm smoothly to a predefined zone.
        Args:
            zone_name: The name of the predefined zone (e.g. 'LEFT', 'RIGHT', 'CENTER')
            duration: Total duration for the transition in seconds.
        """
        pass

    @abstractmethod
    def open_gripper(self) -> bool:
        """
        Opens the gripper/end-effector.
        """
        pass

    @abstractmethod
    def close_gripper(self) -> bool:
        """
        Closes the gripper/end-effector.
        """
        pass

    @abstractmethod
    def pick_object(self, zone_name: str) -> bool:
        """
        High-level abstract pick routine.
        Moves to zone, opens gripper, lowers, grips, and lifts.
        """
        pass

    @abstractmethod
    def drop_object(self, zone_name: str) -> bool:
        """
        High-level abstract drop routine.
        Moves to zone (above drop position), lowers, releases gripper, and homes.
        """
        pass

    @abstractmethod
    def stop(self):
        """
        Immediately stops all joints and movements.
        """
        pass

    @abstractmethod
    def adjust_joints(self, deltas: list, duration: float = 0.2) -> bool:
        """
        Applies a small relative change to joint positions.
        Args:
            deltas: Relative change for each joint.
            duration: Transition time in seconds.
        """
        pass

    @abstractmethod
    def get_state(self) -> dict:
        """
        Returns the current state of the robot.
        Returns:
            Dictionary containing 'connected', 'joint_positions', 'gripper_closed', and 'current_pose'.
        """
        pass
