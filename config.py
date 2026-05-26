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
MOVEMENT_SPEED = 0.7  # Escala de velocidad de movimiento proporcional a la distancia desde el centro (0.1 a 1.0)
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

# Límites físicos del NiryoOne en grados
JOINT_LIMITS = {
    "joint1": (-170.0, 170.0),
    "joint2": (-90.0, 90.0),
    "joint3": (-135.0, 135.0),
    "joint4": (-90.0, 90.0),
    "joint5": (-90.0, 90.0),
    "joint6": (-180.0, 180.0),
}

# Posición HOME segura para el NiryoOne en radianes.
# joint2 y joint3 se desplazan levemente para evitar colisiones con la base.
JOINT_HOME = {
    "joint1": 0.0,
    "joint2": -0.3,
    "joint3": 0.8,
    "joint4": 0.0,
    "joint5": 0.0,
    "joint6": 0.0,
}

GRIPPER_CONNECTION_PATH = "/NiryoOne/connection"
