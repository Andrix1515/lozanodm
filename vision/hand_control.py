"""
Detección de mano (MediaPipe), cuadrícula 3×3 y control tipo joystick.
Puño cerrado → cierra gripper. Mano abierta → joystick según celda activa.
"""

import math
import time

import cv2
import mediapipe as mp
import numpy as np

import config

# Landmarks MediaPipe
WRIST = 0
THUMB_TIP, THUMB_IP = 4, 3
INDEX_TIP, INDEX_PIP = 8, 6
MIDDLE_TIP, MIDDLE_PIP = 12, 10
RING_TIP, RING_PIP = 16, 14
PINKY_TIP, PINKY_PIP = 20, 18


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


def deltas_for_cell(col: int, row: int) -> list[float]:
    """
    Celda → incrementos de joints.
    col 0=izq, 2=der | row 0=arriba, 2=abajo | centro sin movimiento.
    """
    step = config.JOINT_STEP
    d = [0.0] * 6
    if col == 0:
        d[0] = -step
    elif col == 2:
        d[0] = step
    if row == 0:
        d[1] = step
    elif row == 2:
        d[1] = -step
    return d


class HandJoystickApp:
    WINDOW_TITLE = "NiryoOne — Control por mano (3x3)"

    def __init__(self, robot):
        self.robot = robot
        self.cap = None
        self.running = False

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

            cx, cy = hand_center(hand_lm)
            self.active_cell = cell_from_position(cx, cy)
            self.fingers = count_extended_fingers(hand_lm)

            px, py = int(cx * w), int(cy * h)
            cv2.circle(frame, (px, py), 12, (0, 255, 120), -1)
            cv2.circle(frame, (px, py), 16, (255, 255, 255), 2)

            self._apply_robot_control()

        else:
            self.active_cell = (1, 1)
            self.status = "Esperando mano..."

        self._draw_grid(frame, w, h)
        self._draw_hud(frame)
        return frame

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

        col, row = self.active_cell
        if col == 1 and row == 1:
            self.status = "Centro — sin movimiento"
            return

        if now - self._last_move_time < config.JOYSTICK_INTERVAL:
            return

        deltas = deltas_for_cell(col, row)
        if self.robot.adjust_joints(deltas):
            labels = ["IZQ", "CENTRO", "DER"]
            vlabels = ["ARRIBA", "MEDIO", "ABAJO"]
            self.status = f"Joystick {labels[col]} / {vlabels[row]}"
            self._last_move_time = now

    def _draw_grid(self, frame: np.ndarray, w: int, h: int):
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
            "[Q] Salir  [H] Home",
        ]
        y = 24
        for line in lines:
            cv2.putText(
                frame, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX,
                0.55, (255, 255, 255), 1, cv2.LINE_AA,
            )
            y += 22
