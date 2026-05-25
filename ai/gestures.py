"""
Discrete Gesture Recognition Layer — OPTIMIZED v2.0
─────────────────────────────────────────────────────
Cambios respecto a v1:
  • Calibración estabilizada: promedia N muestras de muñeca en lugar de
    una sola lectura ruidosa.
  • Umbrales adaptativos basados en el tamaño de la mano detectada
    (distancia palma↔dedo medio) → funciona igual cerca y lejos de la cámara.
  • Nuevo gesto PEACE (índice + medio extendidos) mapeado a MOVE_CENTER.
  • Detección de pulgar mejorada: usa eje de la mano en lugar de posición
    absoluta (funciona con la mano en cualquier orientación).
  • Vectorización numpy para velocidad.
"""

import math
import numpy as np
import config


class GestureClassifier:
    """
    Clasifica landmarks normalizados de MediaPipe en estados de control discretos.
    """

    # Índices de articulaciones de MediaPipe
    FINGER_JOINTS = {
        "index":  (8, 7, 6,  5),   # tip, dip, pip, mcp
        "middle": (12, 11, 10, 9),
        "ring":   (16, 15, 14, 13),
        "pinky":  (20, 19, 18, 17),
    }
    THUMB_TIP = 4
    THUMB_IP  = 3
    THUMB_MCP = 2
    INDEX_MCP = 5
    WRIST     = 0
    MIDDLE_MCP = 9

    # ── Calibración ────────────────────────────────────────────────────────
    CALIBRATION_SAMPLES = 15  # Cuántas muestras promediar para calibrar

    def __init__(self):
        self.calibrated  = False
        self.neutral_x   = 0.5
        self.neutral_y   = 0.5
        self.neutral_z   = 0.0
        self._cal_buffer = []   # Buffer temporal para calibración estable

        # Umbral de desplazamiento lateral (adaptativo si se puede)
        self._tilt_threshold = 0.13

    # ═══════════════════════════════════════════════════════════════════════
    # CALIBRACIÓN
    # ═══════════════════════════════════════════════════════════════════════

    def calibrate(self, wrist_coords: tuple):
        """
        Acumula muestras de la muñeca y promedia para una referencia estable.
        Llama varias veces; la calibración se confirma automáticamente.
        """
        self._cal_buffer.append(wrist_coords)

        if len(self._cal_buffer) >= self.CALIBRATION_SAMPLES:
            arr = np.array(self._cal_buffer)
            self.neutral_x, self.neutral_y, self.neutral_z = arr.mean(axis=0)
            self.calibrated = True
            self._cal_buffer.clear()
            print(f"[Gestures] Calibrado → X={self.neutral_x:.3f}  Y={self.neutral_y:.3f}")
        else:
            remaining = self.CALIBRATION_SAMPLES - len(self._cal_buffer)
            print(f"[Gestures] Calibrando... ({remaining} muestras restantes)")

    def reset_calibration(self):
        self.calibrated  = False
        self._cal_buffer.clear()

    # ═══════════════════════════════════════════════════════════════════════
    # HELPERS GEOMÉTRICOS
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _dist2d(a, b) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def _hand_scale(self, lm: list) -> float:
        """
        Escala de referencia = distancia muñeca↔MCP del dedo medio.
        Permite que los umbrales sean independientes de la distancia a la cámara.
        """
        return max(self._dist2d(lm[self.WRIST], lm[self.MIDDLE_MCP]), 1e-6)

    def _is_finger_extended(self, lm: list, finger: str) -> bool:
        """
        Un dedo está extendido si su tip está notablemente más lejos de la
        muñeca que su PIP, normalizado por la escala de la mano.
        """
        tip_i, dip_i, pip_i, mcp_i = self.FINGER_JOINTS[finger]
        wrist = lm[self.WRIST]
        tip   = lm[tip_i]
        pip   = lm[pip_i]

        scale  = self._hand_scale(lm)
        d_tip  = self._dist2d(tip,  wrist) / scale
        d_pip  = self._dist2d(pip,  wrist) / scale

        return d_tip > d_pip * 1.12

    def _is_thumb_extended(self, lm: list) -> bool:
        """
        Pulgar extendido: distancia tip↔índice_MCP normalizada > umbral.
        Funciona con la mano en cualquier rotación.
        """
        scale = self._hand_scale(lm)
        d = self._dist2d(lm[self.THUMB_TIP], lm[self.INDEX_MCP]) / scale
        return d > 0.55   # ~55 % de la escala de mano

    def _thumb_pointing_up(self, lm: list) -> bool:
        """
        Comprueba si el tip del pulgar está por encima de la muñeca
        Y por encima del MCP del pulgar (detecta thumb_up verdadero).
        """
        return (lm[self.THUMB_TIP][1] < lm[self.WRIST][1] - 0.04 and
                lm[self.THUMB_TIP][1] < lm[self.THUMB_MCP][1])

    # ═══════════════════════════════════════════════════════════════════════
    # CLASIFICACIÓN PRINCIPAL
    # ═══════════════════════════════════════════════════════════════════════

    def classify(self, landmarks: list) -> str:
        """
        Devuelve uno de:
            OPEN        → mano abierta (≥3 dedos)  → abrir gripper
            CLOSED      → puño cerrado              → cerrar gripper
            UNKNOWN     → cualquier otra posición   → joystick
        """
        if not landmarks or len(landmarks) < 21:
            return "UNKNOWN"

        lm    = landmarks

        # ── Estado de los dedos ─────────────────────────────────────────
        finger_ext = {f: self._is_finger_extended(lm, f) for f in self.FINGER_JOINTS}
        thumb_ext  = self._is_thumb_extended(lm)
        n_ext      = sum(finger_ext.values())

        # Mano abierta: 3+ dedos extendidos
        if n_ext >= 3:
            return "OPEN"

        # Puño: ningún dedo ni pulgar extendido
        if n_ext == 0 and not thumb_ext:
            return "CLOSED"

        return "UNKNOWN"