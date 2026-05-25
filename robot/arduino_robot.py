"""
Arduino/ESP32 Robot Adapter implementing BaseRobot.
Serves as the concrete bridge for future real robotic hardware using serial/ESP communication.
Uses a 4 DOF structure (Base, Shoulder, Elbow, Gripper) mapped to Servo angles in degrees (0-180).
"""

import time
from robot.base_robot import BaseRobot
import config

class ArduinoRobotAdapter(BaseRobot):
    """
    Adapter representing a physical 4 DOF Arduino-controlled robotic arm.
    Isolates serial and micro-controller communication, allowing mock simulation.
    """

    def __init__(self):
        self.connected = False
        self.joint_positions = [90.0, 90.0, 90.0, 0.0]  # Initial default degrees
        self.gripper_closed = False
        self.current_pose = "UNKNOWN"

    def connect(self) -> bool:
        """
        Simulates connection over a Serial Port (e.g. COM3 / 9600 baud rate).
        """
        print("[ArduinoAdapter] Scanning serial ports...")
        print("[ArduinoAdapter] MOCK COM PORT: Connecting to Arduino Board at 9600 baud rate...")
        time.sleep(1.0)
        self.connected = True
        print("[ArduinoAdapter] SUCCESS: Connected to Arduino board physically.")
        self.move_home(duration=1.0)
        return True

    def disconnect(self):
        """
        Safely halts servos and closes serial handle.
        """
        if self.connected:
            print("[ArduinoAdapter] Safely parking robotic arm...")
            self.move_home(duration=1.0)
            print("[ArduinoAdapter] Closing COM serial handle. Disconnected.")
            self.connected = False

    def _write_serial_packet(self, angles: list):
        """
        Helper that simulates sending structured bytes over the UART serial line.
        Example Packet format: '<90,90,90,0>'
        """
        clamped_angles = []
        for i, angle in enumerate(angles):
            if i < len(config.JOINT_LIMITS_4DOF):
                limits = config.JOINT_LIMITS_4DOF[i]
                angle = max(limits[0], min(limits[1], angle))
            clamped_angles.append(int(angle))
        
        self.joint_positions = clamped_angles
        packet = f"<{','.join(map(str, clamped_angles))}>"
        print(f"[ArduinoAdapter] [UART-TX] Serial Send Packet: {packet}")

    def _interpolate_serial(self, target_angles: list, duration: float = 2.0, steps: int = 20):
        """
        Smoothly interpolates angles in degrees and sends serial packets incrementally.
        """
        if not self.connected:
            print("[ArduinoAdapter] ERROR: Port is closed. Cannot write serial values.")
            return False

        start_angles = list(self.joint_positions)
        for step in range(steps):
            alpha = (step + 1) / steps
            interpolated = [
                start + (target - start) * alpha
                for start, target in zip(start_angles, target_angles)
            ]
            self._write_serial_packet(interpolated)
            time.sleep(duration / steps)
        return True

    def adjust_joints(self, deltas: list, duration: float = 0.2) -> bool:
        """
        Applies a small relative change to the current joint angles.
        """
        if not self.connected:
            return False

        target = list(self.joint_positions)
        for i, delta in enumerate(deltas):
            if i < len(target):
                target[i] += delta
        return self._interpolate_serial(target, duration=duration)

    def move_home(self, duration: float = 2.0) -> bool:
        """
        Moves 4 DOF servos to predefined HOME degrees.
        """
        print("[ArduinoAdapter] Moving to position: HOME")
        target = config.PRESET_POSITIONS_4DOF["HOME"]
        success = self._interpolate_serial(target, duration=duration)
        if success:
            self.current_pose = "HOME"
        return success

    def move_to_zone(self, zone_name: str, duration: float = 3.0) -> bool:
        """
        Moves 4 DOF servos to predefined zone degrees.
        """
        if zone_name not in config.PRESET_POSITIONS_4DOF:
            print(f"[ArduinoAdapter] ERROR: Zone '{zone_name}' is not configured.")
            return False

        print(f"[ArduinoAdapter] Moving to position: {zone_name}")
        target = config.PRESET_POSITIONS_4DOF[zone_name]
        success = self._interpolate_serial(target, duration=duration)
        if success:
            self.current_pose = zone_name
        return success

    def open_gripper(self) -> bool:
        """
        Sets gripper servo to open degrees (e.g. 0).
        """
        if not self.connected:
            return False
        print("[ArduinoAdapter] Commands: OPEN GRIPPER")
        angles = list(self.joint_positions)
        angles[3] = 0.0  # Open gripper angle (0 degrees)
        self._write_serial_packet(angles)
        self.gripper_closed = False
        time.sleep(0.5)
        return True

    def close_gripper(self) -> bool:
        """
        Sets gripper servo to closed degrees (e.g. 90).
        """
        if not self.connected:
            return False
        print("[ArduinoAdapter] Commands: CLOSE GRIPPER")
        angles = list(self.joint_positions)
        angles[3] = 90.0  # Close gripper angle (90 degrees)
        self._write_serial_packet(angles)
        self.gripper_closed = True
        time.sleep(0.5)
        return True

    def pick_object(self, zone_name: str) -> bool:
        """
        Executes mock pick operation.
        """
        print(f"[ArduinoAdapter] Autonomous Routine: PICK from {zone_name}")
        if not self.move_to_zone(zone_name, duration=1.5): return False
        if not self.open_gripper(): return False
        
        # Lower shoulder servo (servo index 1)
        lower_angles = list(self.joint_positions)
        lower_angles[1] += 20  # Bend shoulder down
        
        if not self._interpolate_serial(lower_angles, duration=0.8): return False
        if not self.close_gripper(): return False
        
        # Lift and return to zone position
        if not self.move_to_zone(zone_name, duration=0.8): return False
        return True

    def drop_object(self, zone_name: str) -> bool:
        """
        Executes mock drop operation.
        """
        print(f"[ArduinoAdapter] Autonomous Routine: DROP at {zone_name}")
        if not self.move_to_zone(zone_name, duration=1.5): return False
        
        # Lower shoulder servo
        lower_angles = list(self.joint_positions)
        lower_angles[1] += 20
        
        if not self._interpolate_serial(lower_angles, duration=0.8): return False
        if not self.open_gripper(): return False
        
        if not self.move_to_zone(zone_name, duration=0.8): return False
        self.move_home(duration=1.0)
        return True

    def stop(self):
        """
        Immediately holds serial outputs.
        """
        if self.connected:
            print("[ArduinoAdapter] Immediate Stop! Locking all servo streams.")
            self._write_serial_packet(list(self.joint_positions))

    def get_state(self) -> dict:
        """
        Returns connection and servo states.
        """
        return {
            "adapter": "Arduino",
            "connected": self.connected,
            "joint_positions": list(self.joint_positions),
            "gripper_closed": self.gripper_closed,
            "current_pose": self.current_pose
        }
