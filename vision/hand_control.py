"""
Detección de mano (MediaPipe), cuadrícula 3×3 y control tipo joystick.
Puño cerrado → cierra gripper. Mano abierta → joystick según celda activa.
"""

import json
import math
import os
import time

import cv2
import numpy as np

try:
    import mediapipe as mp
except ImportError as error:
    raise ImportError(
        "MediaPipe no está instalado. Ejecuta: pip install mediapipe==0.10.0"
    ) from error

import config
from utils.kinematics import AdaptiveEMAFilter

# Landmarks MediaPipe
WRIST = 0
THUMB_TIP, THUMB_IP = 4, 3
INDEX_TIP, INDEX_PIP = 8, 6
MIDDLE_TIP, MIDDLE_PIP = 12, 10
RING_TIP, RING_PIP = 16, 14
PINKY_TIP, PINKY_PIP = 20, 18

CALIBRATION_HOLD_SECONDS = 2.0
CALIBRATION_STABILITY_RADIUS = 0.04
DEAD_ZONE_HALF_SIZE = 0.15
CALIBRATION_FILENAME = "calibration.json"


def _dist(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _finger_extended(lm, tip_idx, pip_idx) -> bool:
    return _dist(lm[tip_idx], lm[WRIST]) > _dist(lm[pip_idx], lm[WRIST])


def count_extended_fingers(hand_landmarks) -> int:
    lm = hand_landmarks.landmark
    count = sum(
        _finger_extended(lm, tip, pip)
        for tip, pip in (
            (INDEX_TIP, INDEX_PIP),
            (MIDDLE_TIP, MIDDLE_PIP),
            (RING_TIP, RING_PIP),
            (PINKY_TIP, PINKY_PIP),
        )
    )
    thumb = abs(lm[THUMB_TIP].x - lm[THUMB_IP].x) > 0.04
    return count + (1 if thumb else 0)


def hand_center(hand_landmarks) -> tuple[float, float]:
    lm = hand_landmarks.landmark
    xs = [p.x for p in lm]
    ys = [p.y for p in lm]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def cell_from_position(cx: float, cy: float) -> tuple[int, int]:
    """Mapea centro de mano [0,1] a celda (col, row) de la cuadrícula 3×3."""
    col = min(config.GRID_COLS - 1, int(cx * config.GRID_COLS))
    row = min(config.GRID_ROWS - 1, int(cy * config.GRID_ROWS))
    return col, row


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


class HandJoystickApp:
    WINDOW_TITLE = "NiryoOne — Control por mano (3x3)"

    def __init__(self, robot):
        self.robot = robot
        self.cap = None
        self.running = False

        if not hasattr(mp, 'solutions'):
            raise RuntimeError(
                "La versión instalada de MediaPipe no es compatible. "
                "Instala la versión correcta con:\n"
                "    pip install mediapipe==0.10.5"
            )

        self.mp_hands = mp.solutions.hands
        self.mp_draw = mp.solutions.drawing_utils
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            model_complexity=0,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.6,
        )

        self.hand_detected = False
        self.active_cell = (1, 1)
        self.fingers = 0
        self.gripper_state = "?"
        self.status = "Iniciando..."
        self._last_move_time = 0.0
        self._last_grip_time = 0.0
        self._gripper_is_closed = False

        self._hand_x = 0.5
        self._hand_y = 0.5
        self._position_filter_x = AdaptiveEMAFilter()
        self._position_filter_y = AdaptiveEMAFilter()
        self._calibration_stage = None
        self._calibration_reference = None
        self._calibration_hold_start = 0.0
        self._calibration_countdown = CALIBRATION_HOLD_SECONDS
        self._calibration_points = {}
        self._calibration_steps = [
            ("Centra la mano → mantén 2 segundos", "center"),
            ("Lleva la mano a la esquina superior izquierda → mantén 2 segundos", "min"),
            ("Lleva la mano a la esquina inferior derecha → mantén 2 segundos", "max"),
        ]
        self._calibration_file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", CALIBRATION_FILENAME)
        )
        self.calibration = self._load_calibration()

    def start_camera(self) -> bool:
        self.cap = cv2.VideoCapture(config.CAMERA_INDEX)
        if not self.cap.isOpened():
            return False
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.running = True
        return True

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()
        self.hands.close()
        cv2.destroyAllWindows()

    def _load_calibration(self):
        try:
            if os.path.exists(self._calibration_file_path):
                with open(self._calibration_file_path, "r", encoding="utf-8") as handle:
                    calibration = json.load(handle)
                if all(key in calibration for key in ("center", "min", "max")):
                    self.status = "Calibración cargada."
                    return calibration
        except Exception as error:
            self.status = f"Error al cargar calibración: {error}"
        return None

    def _save_calibration(self):
        try:
            with open(self._calibration_file_path, "w", encoding="utf-8") as handle:
                json.dump(self.calibration, handle, indent=2)
            self.status = "Calibración guardada en calibration.json"
        except Exception as error:
            self.status = f"No se pudo guardar calibración: {error}"

    def start_calibration(self):
        self._calibration_stage = 0
        self._calibration_reference = None
        self._calibration_hold_start = 0.0
        self._calibration_countdown = CALIBRATION_HOLD_SECONDS
        self._calibration_points = {}
        self.status = "Iniciando calibración..."

    def process_frame(self) -> np.ndarray:
        ret, frame = self.cap.read()
        if not ret:
            return np.zeros((config.FRAME_HEIGHT, config.FRAME_WIDTH, 3), dtype=np.uint8)

        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb)

        self.hand_detected = False
        if results.multi_hand_landmarks:
            hand_lm = results.multi_hand_landmarks[0]
            self.hand_detected = True
            self.mp_draw.draw_landmarks(
                frame, hand_lm, self.mp_hands.HAND_CONNECTIONS
            )

            raw_cx, raw_cy = hand_center(hand_lm)
            self._update_calibration(raw_cx, raw_cy)
            filtered_cx = self._position_filter_x.update(raw_cx)
            filtered_cy = self._position_filter_y.update(raw_cy)
            self._hand_x, self._hand_y = self._apply_calibration(filtered_cx, filtered_cy)
            self.active_cell = cell_from_position(self._hand_x, self._hand_y)
            self.fingers = count_extended_fingers(hand_lm)

            px, py = int(self._hand_x * w), int(self._hand_y * h)
            cv2.circle(frame, (px, py), 12, (0, 255, 120), -1)
            cv2.circle(frame, (px, py), 16, (255, 255, 255), 2)

            if self._calibration_stage is None:
                self._apply_robot_control()
        else:
            self.active_cell = (1, 1)
            if self._calibration_stage is None:
                self.status = "Esperando mano..."
            else:
                self._update_calibration(None, None)

        self._draw_grid(frame, w, h)
        self._draw_hud(frame)
        return frame

    def _update_calibration(self, cx, cy):
        if self._calibration_stage is None:
            return

        if cx is None or cy is None:
            self.status = "Busca mano para calibrar..."
            self._calibration_reference = None
            return

        prompt, key = self._calibration_steps[self._calibration_stage]
        if self._calibration_reference is None:
            self._calibration_reference = (cx, cy)
            self._calibration_hold_start = time.time()
            self._calibration_countdown = CALIBRATION_HOLD_SECONDS
            self.status = f"{prompt} ({self._calibration_stage + 1}/3)"
            return

        distance = math.hypot(cx - self._calibration_reference[0], cy - self._calibration_reference[1])
        if distance <= CALIBRATION_STABILITY_RADIUS:
            elapsed = time.time() - self._calibration_hold_start
            remaining = max(0.0, CALIBRATION_HOLD_SECONDS - elapsed)
            self._calibration_countdown = remaining
            if elapsed >= CALIBRATION_HOLD_SECONDS:
                self._calibration_points[key] = {"x": cx, "y": cy}
                self._calibration_stage += 1
                self._calibration_reference = None
                if self._calibration_stage >= len(self._calibration_steps):
                    self.calibration = self._calibration_points
                    self._save_calibration()
                    self._calibration_stage = None
                    self.status = "Calibración completada."
                else:
                    next_prompt = self._calibration_steps[self._calibration_stage][0]
                    self.status = f"Capturado {key}. {next_prompt}"
            else:
                self.status = f"{prompt} — Mantén {remaining:.1f}s"
        else:
            self._calibration_reference = (cx, cy)
            self._calibration_hold_start = time.time()
            self._calibration_countdown = CALIBRATION_HOLD_SECONDS
            self.status = f"Estabiliza la mano para {prompt}"

    def _apply_calibration(self, cx: float, cy: float) -> tuple[float, float]:
        if not self.calibration:
            return cx, cy

        min_x = self.calibration["min"]["x"]
        max_x = self.calibration["max"]["x"]
        min_y = self.calibration["min"]["y"]
        max_y = self.calibration["max"]["y"]
        center_x = self.calibration["center"]["x"]
        center_y = self.calibration["center"]["y"]

        if max_x <= min_x or max_y <= min_y:
            return cx, cy

        raw_x = (cx - min_x) / (max_x - min_x)
        raw_y = (cy - min_y) / (max_y - min_y)
        center_x_norm = (center_x - min_x) / (max_x - min_x)
        center_y_norm = (center_y - min_y) / (max_y - min_y)

        adjusted_x = _clamp01(raw_x + (0.5 - center_x_norm))
        adjusted_y = _clamp01(raw_y + (0.5 - center_y_norm))
        return adjusted_x, adjusted_y

    def _is_in_dead_zone(self, cx: float, cy: float) -> bool:
        return (
            abs(cx - 0.5) <= DEAD_ZONE_HALF_SIZE
            and abs(cy - 0.5) <= DEAD_ZONE_HALF_SIZE
        )

    def _movement_scale(self, cx: float, cy: float) -> float:
        distance = math.hypot(cx - 0.5, cy - 0.5)
        max_distance = math.hypot(0.5, 0.5)
        return config.MOVEMENT_SPEED * min(1.0, distance / max_distance)

    def _deltas_for_position(self, cx: float, cy: float) -> list[float]:
        scale = self._movement_scale(cx, cy)
        if scale <= 0.0:
            return [0.0] * 6

        step = config.JOINT_STEP * scale
        dx = cx - 0.5
        dy = 0.5 - cy
        deltas = [0.0] * 6
        if abs(dx) >= 0.02:
            deltas[0] = math.copysign(step, dx)
        if abs(dy) >= 0.02:
            deltas[1] = math.copysign(step, dy)
        return deltas

    def _apply_robot_control(self):
        if not self.robot.connected:
            err = getattr(self.robot, "last_error", "") or "sin conexion"
            self.status = f"CoppeliaSim: {err[:40]}"
            return
        if not self.robot.simulation_running:
            self.status = "Simulacion detenida en CoppeliaSim"
            return

        now = time.time()
        fist_closed = self.fingers <= 1

        if fist_closed != self._gripper_is_closed:
            if now - self._last_grip_time >= config.GRIPPER_COOLDOWN:
                if fist_closed:
                    self.robot.close_gripper()
                    self.gripper_state = "CERRADO"
                else:
                    self.robot.open_gripper()
                    self.gripper_state = "ABIERTO"
                self._gripper_is_closed = fist_closed
                self._last_grip_time = now

        if fist_closed:
            self.status = f"Puño cerrado — gripper {self.gripper_state}"
            return

        if self._is_in_dead_zone(self._hand_x, self._hand_y):
            self.status = "Zona muerta central"
            return

        if now - self._last_move_time < config.JOYSTICK_INTERVAL:
            return

        deltas = self._deltas_for_position(self._hand_x, self._hand_y)
        if any(abs(value) > 0.0 for value in deltas) and self.robot.adjust_joints(deltas):
            labels = ["IZQ", "CENTRO", "DER"]
            vlabels = ["ARRIBA", "MEDIO", "ABAJO"]
            self.status = f"Joystick {labels[self.active_cell[0]]} / {vlabels[self.active_cell[1]]}"
            self._last_move_time = now

    def _draw_grid(self, frame: np.ndarray, w: int, h: int):
        dead_x1 = int((0.5 - DEAD_ZONE_HALF_SIZE) * w)
        dead_y1 = int((0.5 - DEAD_ZONE_HALF_SIZE) * h)
        dead_x2 = int((0.5 + DEAD_ZONE_HALF_SIZE) * w)
        dead_y2 = int((0.5 + DEAD_ZONE_HALF_SIZE) * h)
        cv2.rectangle(frame, (dead_x1, dead_y1), (dead_x2, dead_y2), (0, 200, 200), 1)

        for i in range(1, config.GRID_COLS):
            x = w * i // config.GRID_COLS
            cv2.line(frame, (x, 0), (x, h), (70, 70, 70), 1)
        for i in range(1, config.GRID_ROWS):
            y = h * i // config.GRID_ROWS
            cv2.line(frame, (0, y), (w, y), (70, 70, 70), 1)

        col, row = self.active_cell
        cw, ch = w // config.GRID_COLS, h // config.GRID_ROWS
        x1, y1 = col * cw + 3, row * ch + 3
        x2, y2 = (col + 1) * cw - 3, (row + 1) * ch - 3
        color = (0, 220, 255) if self.hand_detected else (60, 60, 60)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

    def _draw_hud(self, frame: np.ndarray):
        sim_ok = getattr(self.robot, "simulation_running", False)
        lines = [
            "NiryoOne | Control 3x3",
            f"Robot: {'OK' if self.robot.connected else 'OFFLINE'}"
            + ("" if sim_ok else " (sim parada)"),
            f"Mano: {'SI' if self.hand_detected else 'NO'}",
            f"Celda: {self.active_cell[0]},{self.active_cell[1]}",
            f"Dedos: {self.fingers}",
            f"Gripper: {self.gripper_state}",
            self.status,
            "[Q] Salir  [H] Home  [C] Calibrar",
        ]
        if self._calibration_stage is not None:
            lines.append(
                f"Calibración {self._calibration_stage + 1}/3 — {self._calibration_countdown:.1f}s"
            )

        y = 24
        for line in lines:
            cv2.putText(
                frame, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX,
                0.55, (255, 255, 255), 1, cv2.LINE_AA,
            )
            y += 22
