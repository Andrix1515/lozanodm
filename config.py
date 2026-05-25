"""Configuración del control por mano + CoppeliaSim (NiryoOne)."""

# Cámara
CAMERA_INDEX = 0
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# Cuadrícula 3×3 (posición normalizada de la mano en el frame)
GRID_ROWS = 3
GRID_COLS = 3

# Joystick: incremento por articulación (rad) en cada tick
JOINT_STEP = 0.04
JOYSTICK_INTERVAL = 0.10
GRIPPER_COOLDOWN = 0.35

# Rutas de joints (escena NiryoOne en CoppeliaSim)
JOINT_PATHS = [
    "/NiryoOne/Joint",
    "/NiryoOne/Link/Joint",
    "/NiryoOne/Link/Joint/Link/Joint",
    "/NiryoOne/Link/Joint/Link/Joint/Link/Joint",
    "/NiryoOne/Link/Joint/Link/Joint/Link/Joint/Link/Joint",
    "/NiryoOne/Joint/Link/Joint/Link/Joint/Link/Joint/Link/Joint/Link/Joint",
]

GRIPPER_CONNECTION_PATH = "/NiryoOne/connection"
