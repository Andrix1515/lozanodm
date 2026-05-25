"""
Global configuration file for the Modular AI Robotic Arm Framework.
Isolates camera, ZMQ, robot presets, limits, and API parameters.
"""

import math

# Active Robot Adapter: "coppelia" or "arduino"
ROBOT_ADAPTER = "coppelia"

# Camera Settings - OPTIMIZED for speed
CAMERA_INDEX = 0
TARGET_FPS = 30
FRAME_WIDTH = 480  # Reduced from 640 for faster processing
FRAME_HEIGHT = 360  # Reduced from 480 for faster processing

# Signal & Filter Parameters - OPTIMIZED for speed
SMOOTHING_ALPHA = 0.35  # Increased for more responsive movement
MEDIAN_BUFFER_SIZE = 3  # Reduced for lower latency

# CoppeliaSim Connection Settings
HOST = "localhost"
PORT = 23000

# Web API server settings
API_HOST = "127.0.0.1"
API_PORT = 5000

# Standard joint paths in CoppeliaSim for NiryoOne
JOINT_PATHS = [
    '/NiryoOne/Joint',
    '/NiryoOne/Link/Joint',
    '/NiryoOne/Link/Joint/Link/Joint',
    '/NiryoOne/Link/Joint/Link/Joint/Link/Joint',
    '/NiryoOne/Link/Joint/Link/Joint/Link/Joint/Link/Joint',
    '/NiryoOne/Joint/Link/Joint/Link/Joint/Link/Joint/Link/Joint/Link/Joint',
]

# Physical limitations of NiryoOne in radians [min, max]
JOINT_LIMITS_6DOF = [
    (-2.87, 2.87),   # Joint 1: Base (rotación horizontal)
    (-1.57, 0.64),   # Joint 2: Hombro (elevación)
    (-1.39, 1.57),   # Joint 3: Codo
    (-2.09, 2.09),   # Joint 4: Antebrazo (rotación)
    (-1.74, 1.74),   # Joint 5: Muñeca (flexión)
    (-2.53, 2.53),   # Joint 6: Muñeca (rotación)
]

# Physical limitations for standard 4 DOF servo arm in degrees [min, max]
JOINT_LIMITS_4DOF = [
    (0, 180),        # Base
    (0, 180),        # Hombro
    (0, 180),        # Codo
    (0, 180),        # Garra
]

# Preset Angular Coordinates (Discrete Control Zones)
# For 6 DOF CoppeliaSim NiryoOne in Radians
PRESET_POSITIONS_6DOF = {
    "HOME": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    "LEFT": [30 * math.pi / 180, -45 * math.pi / 180, 20 * math.pi / 180, -10 * math.pi / 180, 45 * math.pi / 180, 10 * math.pi / 180],
    "CENTER": [0.0, -40 * math.pi / 180, 25 * math.pi / 180, -15 * math.pi / 180, 30 * math.pi / 180, 5 * math.pi / 180],
    "RIGHT": [-30 * math.pi / 180, -45 * math.pi / 180, 20 * math.pi / 180, 10 * math.pi / 180, 45 * math.pi / 180, -10 * math.pi / 180],
    "DROP_ZONE": [60 * math.pi / 180, -35 * math.pi / 180, 35 * math.pi / 180, -5 * math.pi / 180, 50 * math.pi / 180, -20 * math.pi / 180]
}

# For 4 DOF Arduino Arm in Degrees
PRESET_POSITIONS_4DOF = {
    "HOME": [90, 90, 90, 0],
    "LEFT": [120, 80, 100, 0],
    "CENTER": [90, 70, 110, 0],
    "RIGHT": [60, 80, 100, 0],
    "DROP_ZONE": [90, 120, 80, 0]
}

# Gripper Control Names & Signals (CoppeliaSim)
GRIPPER_PATH = '/NiryoOne/NiryoLGripper'
GRIPPER_SIGNAL_NAME = 'NiryoLGripper'

# MediaPipe Gesture Detection Thresholds (normalized wrist distances)
GRIP_OPEN_THRESHOLD = 0.08
GRIP_CLOSE_THRESHOLD = 0.05
