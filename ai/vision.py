"""
Core Computer Vision & Gesture Recognition System — OPTIMIZED v2.0
────────────────────────────────────────────────────────────────────
Cambios clave respecto a v1:
  • MediaPipe corre en un hilo dedicado (no bloquea la cámara).
  • Buffer de doble-cámara con threading.Event para sincronización limpia.
  • Suavizado de gestos con ventana deslizante (evita destellos).
  • HUD renderizado con cache de overlay para reducir operaciones cv2.
  • Resolución de captura separada de la resolución de inferencia.
"""

import cv2
import mediapipe as mp
import numpy as np
import time
import threading
from collections import deque
from ai.gestures import GestureClassifier
import config


class VisionSystem:
    """
    Gestiona el stream de cámara OpenCV con pipeline de MediaPipe asíncrono.
    """

    # Paleta HUD (BGR)
    PALETTE = {
        "neon_green":    (100, 255, 100),
        "coral_red":     (80,  80,  240),
        "electric_blue": (240, 160, 50),
        "gold_yellow":   (50,  220, 220),
        "bright_white":  (255, 255, 255),
        "dark_panel":    (15,  15,  15),
        "hud_gray":      (160, 160, 160),
        "cyber_cyan":    (220, 220, 0),
    }

    # ─── Parámetros de suavizado ────────────────────────────────────────────
    GESTURE_WINDOW    = 5   # Votos en ventana deslizante para confirmar gesto
    COMMAND_COOLDOWN  = 1.5  # Segundos mínimos entre comandos (evita saturar la cola ZMQ)
    JOYSTICK_DEADZONE = 0.08  # Zona central donde no hay movimiento
    JOYSTICK_MAX_DIST = 0.35  # Distancia normalizada para velocidad máxima
    JOYSTICK_INTERVAL = 0.12  # Segundos entre ajustes de movimiento
    JOYSTICK_GAIN_4DOF = 2.8  # grados por llamada
    JOYSTICK_GAIN_6DOF = 0.04  # radianes por llamada

    def __init__(self, robot_adapter):
        self.robot  = robot_adapter
        self.classifier = GestureClassifier()
        self.cap    = None
        self.running = False

        # ── MediaPipe (solo se usa dentro del hilo de inferencia) ──────────
        self.mp_hands  = mp.solutions.hands
        self.mp_draw   = mp.solutions.drawing_utils
        self.mp_styles = mp.solutions.drawing_styles
        self.hands     = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            model_complexity=0,            # 0 = más rápido, 1 = más preciso
            min_detection_confidence=0.75,
            min_tracking_confidence=0.65,
        )

        # ── Estado compartido (hilo cámara ↔ hilo inferencia) ──────────────
        self._lock             = threading.Lock()
        self._frame_for_mp     = None          # Frame RGB para MediaPipe
        self._new_frame_event  = threading.Event()
        self._mp_results       = None          # Resultados MediaPipe más recientes
        self._last_landmarks   = None

        # ── Estado de la aplicación ────────────────────────────────────────
        self.current_gesture   = "NONE"
        self.hand_detected     = False
        self.operational_mode  = "GESTURE"     # GESTURE | API_MANUAL | AUTONOMOUS
        self.status_msg        = "Iniciando sistema..."
        self.last_command_sent = "stop"
        self._last_command_time= 0.0
        self._last_joystick_time = 0.0
        self._joystick_cell = (1, 1)

        # Suavizado de gestos
        self._gesture_buffer   = deque(maxlen=self.GESTURE_WINDOW)

        # ── Métricas de rendimiento ────────────────────────────────────────
        self._fps_display      = 0
        self._frame_count      = 0
        self._last_fps_time    = time.time()
        self._inference_fps    = 0
        self._inference_count  = 0
        self._last_inf_time    = time.time()

        # ── Cache de overlay HUD (solo se recalcula si cambia el tamaño) ──
        self._hud_overlay      = None
        self._hud_frame_shape  = None

        # Hilo de inferencia MediaPipe
        self._mp_thread = threading.Thread(target=self._mediapipe_worker, daemon=True)

    # ═══════════════════════════════════════════════════════════════════════
    # CICLO DE VIDA
    # ═══════════════════════════════════════════════════════════════════════

    def start_camera(self) -> bool:
        print(f"[Vision] Abriendo cámara índice {config.CAMERA_INDEX}...")
        self.cap = cv2.VideoCapture(config.CAMERA_INDEX)
        if not self.cap.isOpened():
            print("[Vision] ERROR: No se pudo abrir la cámara.")
            return False

        # Configurar resolución de captura
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  config.FRAME_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)   # Minimiza latencia de buffer

        self.running = True
        self._mp_thread.start()
        print("[Vision] Hilo de inferencia MediaPipe iniciado.")
        return True

    def stop_camera(self):
        self.running = False
        self._new_frame_event.set()          # Desbloquea el hilo si está esperando
        if self._mp_thread.is_alive():
            self._mp_thread.join(timeout=2)
        if self.cap:
            self.cap.release()
            self.cap = None
        self.hands.close()
        cv2.destroyAllWindows()
        print("[Vision] Recursos de cámara liberados.")

    def calibrate_hand(self) -> bool:
        if self.hand_detected and self._last_landmarks:
            wrist_coords = self._last_landmarks[0]
            self.classifier.calibrate(wrist_coords)
            self.status_msg = "¡Calibración completada!"
            return True
        self.status_msg = "Calibración fallida — sin mano"
        return False

    # ═══════════════════════════════════════════════════════════════════════
    # HILO MEDIAPIPE (inferencia asíncrona)
    # ═══════════════════════════════════════════════════════════════════════

    def _mediapipe_worker(self):
        """
        Hilo dedicado: espera frames RGB, ejecuta MediaPipe, almacena resultados.
        Nunca bloquea el hilo principal de la cámara.
        """
        while self.running:
            triggered = self._new_frame_event.wait(timeout=0.1)
            if not triggered or not self.running:
                continue
            self._new_frame_event.clear()

            with self._lock:
                frame_rgb = self._frame_for_mp

            if frame_rgb is None:
                continue

            # ── Inferencia ─────────────────────────────────────────────────
            results = self.hands.process(frame_rgb)

            # ── Actualizar estado compartido ───────────────────────────────
            with self._lock:
                self._mp_results = results
                if results and results.multi_hand_landmarks:
                    hand_lm = results.multi_hand_landmarks[0]
                    self._last_landmarks = [
                        (lm.x, lm.y, lm.z) for lm in hand_lm.landmark
                    ]
                else:
                    self._last_landmarks = None

            # Métrica de FPS de inferencia
            self._inference_count += 1
            now = time.time()
            if now - self._last_inf_time >= 1.0:
                self._inference_fps   = self._inference_count
                self._inference_count = 0
                self._last_inf_time   = now

    # ═══════════════════════════════════════════════════════════════════════
    # LOOP PRINCIPAL (llamado desde el hilo de UI/main)
    # ═══════════════════════════════════════════════════════════════════════

    def process_frame(self) -> np.ndarray:
        """
        Captura frame, lo envía al hilo de inferencia, aplica resultados previos
        y renderiza el HUD. Nunca bloquea esperando a MediaPipe.
        """
        if not self.cap:
            return np.zeros((480, 640, 3), dtype=np.uint8)

        ret, frame = self.cap.read()
        if not ret:
            return np.zeros((480, 640, 3), dtype=np.uint8)

        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

        # ── FPS del hilo principal ─────────────────────────────────────────
        self._frame_count += 1
        now = time.time()
        if now - self._last_fps_time >= 1.0:
            self._fps_display  = self._frame_count
            self._frame_count  = 0
            self._last_fps_time = now

        # ── Enviar frame al hilo MediaPipe (sin esperar respuesta) ─────────
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        with self._lock:
            self._frame_for_mp = rgb
        self._new_frame_event.set()

        # ── Leer resultados del hilo MediaPipe (no bloqueante) ─────────────
        with self._lock:
            results     = self._mp_results
            landmarks   = self._last_landmarks

        if results and results.multi_hand_landmarks:
            self.hand_detected = True
            hand_lm = results.multi_hand_landmarks[0]

            # Dibujar malla de mano
            self.mp_draw.draw_landmarks(
                frame, hand_lm,
                self.mp_hands.HAND_CONNECTIONS,
                self.mp_styles.get_default_hand_landmarks_style(),
                self.mp_styles.get_default_hand_connections_style(),
            )

            if landmarks:
                # Punto de muñeca con halo
                wrist_x = int(landmarks[0][0] * w)
                wrist_y = int(landmarks[0][1] * h)
                cv2.circle(frame, (wrist_x, wrist_y), 10, self.PALETTE["electric_blue"], -1)
                cv2.circle(frame, (wrist_x, wrist_y), 13, self.PALETTE["bright_white"],  2)

                if self.operational_mode == "GESTURE":
                    raw_gesture = self.classifier.classify(landmarks)
                    smoothed    = self._smooth_gesture(raw_gesture)
                    display_gesture = smoothed if smoothed in ("OPEN", "CLOSED") else "JOYSTICK"
                    self.current_gesture = display_gesture

                    if smoothed == "CLOSED":
                        self._dispatch_gripper_command("close_gripper")
                    elif smoothed == "OPEN":
                        self._dispatch_gripper_command("open_gripper")
                    else:
                        self._dispatch_joystick_command(landmarks, w, h)
        else:
            self.hand_detected   = False
            self.current_gesture = "NONE"
            self._joystick_cell  = (1, 1)
            self._gesture_buffer.clear()
            if self.operational_mode == "GESTURE":
                self.status_msg = "Esperando mano..."

        # ── Renderizar HUD ─────────────────────────────────────────────────
        self._render_hud(frame, h, w)
        return frame

    # ═══════════════════════════════════════════════════════════════════════
    # SUAVIZADO DE GESTOS
    # ═══════════════════════════════════════════════════════════════════════

    def _smooth_gesture(self, raw: str) -> str:
        """
        Voto por mayoría en ventana deslizante.
        El gesto debe aparecer en ≥ 60 % de los últimos N frames.
        """
        self._gesture_buffer.append(raw)
        if len(self._gesture_buffer) < self.GESTURE_WINDOW:
            return raw

        counts = {}
        for g in self._gesture_buffer:
            counts[g] = counts.get(g, 0) + 1

        best = max(counts, key=counts.get)
        if counts[best] / self.GESTURE_WINDOW >= 0.6:
            return best
        return raw

    # ═══════════════════════════════════════════════════════════════════════
    # DISPATCHER DE COMANDOS
    # ═══════════════════════════════════════════════════════════════════════

    def _dispatch_gripper_command(self, command: str):
        """
        Mapea los comandos de gripper y evita spam.
        """
        if not self.robot or not self.robot.get_state().get("connected"):
            self.status_msg = "Adaptador offline"
            return

        now = time.time()
        same_command = (command == self.last_command_sent)
        within_cooldown = (now - self._last_command_time) < self.COMMAND_COOLDOWN

        if same_command and within_cooldown:
            return   # Evitar spam de comandos duplicados

        self.last_command_sent  = command
        self._last_command_time = now
        self.status_msg         = f"Cmd: {command}"

        try:
            if command == "open_gripper":
                self.robot.open_gripper()
            elif command == "close_gripper":
                self.robot.close_gripper()
        except Exception as e:
            self.status_msg = f"Error API: {str(e)[:30]}"

    def _dispatch_joystick_command(self, landmarks: list, frame_w: int, frame_h: int):
        """
        Usa el centro de la mano como joystick 3x3 para mover las articulaciones.
        """
        if not self.robot or not self.robot.get_state().get("connected"):
            self.status_msg = "Adaptador offline"
            return

        now = time.time()
        if now - self._last_joystick_time < self.JOYSTICK_INTERVAL:
            return
        self._last_joystick_time = now

        wrist = landmarks[0]
        neutral_x = self.classifier.neutral_x if self.classifier.calibrated else 0.5
        neutral_y = self.classifier.neutral_y if self.classifier.calibrated else 0.5

        dx = wrist[0] - neutral_x
        dy = wrist[1] - neutral_y

        x_dir = 0
        y_dir = 0
        if dx < -self.JOYSTICK_DEADZONE:
            x_dir = -1
        elif dx > self.JOYSTICK_DEADZONE:
            x_dir = 1
        if dy < -self.JOYSTICK_DEADZONE:
            y_dir = -1
        elif dy > self.JOYSTICK_DEADZONE:
            y_dir = 1

        self._joystick_cell = (
            1 if abs(dx) < self.JOYSTICK_DEADZONE else (0 if dx < 0 else 2),
            1 if abs(dy) < self.JOYSTICK_DEADZONE else (0 if dy < 0 else 2),
        )

        if x_dir == 0 and y_dir == 0:
            self.status_msg = "Joystick neutral"
            self.last_command_sent = "stop"
            return

        speed = min(max(abs(dx), abs(dy)) / self.JOYSTICK_MAX_DIST, 1.0)
        axis_info = self.robot.get_state().get("joint_positions", [])
        is_4dof = len(axis_info) == 4

        if is_4dof:
            base_delta     = x_dir * self.JOYSTICK_GAIN_4DOF * speed
            shoulder_delta = -y_dir * self.JOYSTICK_GAIN_4DOF * speed
            deltas = [base_delta, shoulder_delta, 0.0, 0.0]
        else:
            base_delta     = x_dir * self.JOYSTICK_GAIN_6DOF * speed
            shoulder_delta = -y_dir * self.JOYSTICK_GAIN_6DOF * speed
            deltas = [base_delta, shoulder_delta, 0.0, 0.0, 0.0, 0.0]

        try:
            self.robot.adjust_joints(deltas, duration=0.12)
            cell_label = f"[{self._joystick_cell[0]},{self._joystick_cell[1]}]"
            self.status_msg = f"Joystick {cell_label} speed {speed:.2f}"
            self.last_command_sent = "joystick"
        except Exception as e:
            self.status_msg = f"Error joystick: {str(e)[:30]}"

    # ═══════════════════════════════════════════════════════════════════════
    # RENDERIZADO HUD
    # ═══════════════════════════════════════════════════════════════════════

    def _render_hud(self, frame: np.ndarray, h: int, w: int):
        """
        HUD con panel lateral semi-transparente y telemetría en tiempo real.
        El overlay de fondo se cachea para evitar recálculos costosos.
        """
        PANEL_W = 260

        # Cache del overlay oscuro (solo recalcular si cambia el tamaño de frame)
        if self._hud_frame_shape != (h, w):
            self._hud_frame_shape = (h, w)
            self._hud_overlay = np.zeros((h, w, 3), dtype=np.uint8)
            cv2.rectangle(self._hud_overlay, (0, 0), (PANEL_W, h),
                          self.PALETTE["dark_panel"], -1)

        cv2.addWeighted(self._hud_overlay, 0.55, frame, 0.45, 0, frame)

        # Borde lateral
        cv2.line(frame, (PANEL_W, 0), (PANEL_W, h), self.PALETTE["electric_blue"], 1)

        # Retícula central en área de cámara
        mx = PANEL_W + (w - PANEL_W) // 2
        my = h // 2
        cv2.line(frame, (mx, 0),      (mx, h),      (50, 50, 50), 1)
        cv2.line(frame, (PANEL_W, my),(w,  my),      (50, 50, 50), 1)
        cv2.rectangle(frame, (mx - 110, my - 110), (mx + 110, my + 110), (40, 40, 40), 1)

        # 3x3 joystick grid
        grid_left   = PANEL_W
        grid_right  = w
        grid_top    = 0
        grid_bottom = h
        cell_w = (grid_right - grid_left) // 3
        cell_h = h // 3
        cv2.line(frame, (grid_left + cell_w, grid_top), (grid_left + cell_w, grid_bottom), (70, 70, 70), 1)
        cv2.line(frame, (grid_left + cell_w * 2, grid_top), (grid_left + cell_w * 2, grid_bottom), (70, 70, 70), 1)
        cv2.line(frame, (grid_left, cell_h), (grid_right, cell_h), (70, 70, 70), 1)
        cv2.line(frame, (grid_left, cell_h * 2), (grid_right, cell_h * 2), (70, 70, 70), 1)

        # Highlight current joystick cell in camera area
        if self.hand_detected and self.operational_mode == "GESTURE":
            cell_x, cell_y = self._joystick_cell
            top_left = (grid_left + cell_x * cell_w + 2, cell_y * cell_h + 2)
            bottom_right = (grid_left + (cell_x + 1) * cell_w - 2, (cell_y + 1) * cell_h - 2)
            cv2.rectangle(frame, top_left, bottom_right, self.PALETTE["neon_green"], 2)

        # ── Sección: cabecera ──────────────────────────────────────────────
        def txt(text, x, y, scale=0.4, color=None, thick=1):
            color = color or self.PALETTE["bright_white"]
            cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX,
                        scale, color, thick, cv2.LINE_AA)

        y = 22
        txt("BRAZO ROBOTICO IA", 12, y, 0.48, self.PALETTE["electric_blue"], 2)
        txt("Framework v2.0  |  Optimizado", 12, y + 14, 0.30, self.PALETTE["hud_gray"])

        y += 28
        cv2.line(frame, (12, y), (PANEL_W - 12, y), self.PALETTE["hud_gray"], 1)

        # ── Sección: estado del sistema ────────────────────────────────────
        y += 16
        txt("ESTADO DEL SISTEMA", 12, y, 0.38, self.PALETTE["cyber_cyan"])

        robot_state  = self.robot.get_state() if self.robot else {"connected": False, "adapter": "N/A"}
        connected    = robot_state.get("connected", False)
        adapter_name = robot_state.get("adapter", "N/A")

        rows = [
            ("Hardware:",    adapter_name,     self.PALETTE["cyber_cyan"]),
            ("Conexión:",    "CONECTADO" if connected else "OFFLINE",
             self.PALETTE["neon_green"] if connected else self.PALETTE["coral_red"]),
            ("Modo:",        self.operational_mode,
             {"GESTURE": self.PALETTE["neon_green"],
              "API_MANUAL": self.PALETTE["electric_blue"],
              "AUTONOMOUS": self.PALETTE["gold_yellow"]}.get(
                 self.operational_mode, self.PALETTE["bright_white"])),
            ("Mano:",        "DETECTADA" if self.hand_detected else "BUSCANDO...",
             self.PALETTE["neon_green"] if self.hand_detected else self.PALETTE["gold_yellow"]),
        ]
        for label, value, color in rows:
            y += 18
            txt(label, 12, y, 0.37, self.PALETTE["bright_white"])
            txt(value,  95, y, 0.37, color)

        y += 12
        cv2.line(frame, (12, y), (PANEL_W - 12, y), (50, 50, 50), 1)

        # ── Sección: reconocimiento IA ─────────────────────────────────────
        y += 14
        txt("RECONOCIMIENTO IA", 12, y, 0.38, self.PALETTE["cyber_cyan"])

        # Badge de gesto
        y += 8
        cv2.rectangle(frame, (12, y), (PANEL_W - 12, y + 42), (30, 30, 30), -1)
        cv2.rectangle(frame, (12, y), (PANEL_W - 12, y + 42), self.PALETTE["electric_blue"], 1)
        txt("Gesto detectado:", 20, y + 14, 0.33, self.PALETTE["hud_gray"])
        g_lbl = self.current_gesture if self.hand_detected else "N/A"
        g_clr = (self.PALETTE["coral_red"] if g_lbl == "CLOSED"
                 else self.PALETTE["neon_green"] if self.hand_detected
                 else self.PALETTE["hud_gray"])
        txt(g_lbl, 20, y + 33, 0.52, g_clr, 2)

        # Badge de comando
        y += 52
        cv2.rectangle(frame, (12, y), (PANEL_W - 12, y + 42), (30, 30, 30), -1)
        cv2.rectangle(frame, (12, y), (PANEL_W - 12, y + 42), self.PALETTE["gold_yellow"], 1)
        txt("Último comando:", 20, y + 14, 0.33, self.PALETTE["hud_gray"])
        cmd = (self.last_command_sent.upper()
               if self.operational_mode == "GESTURE" else "API DIRECTO")
        txt(cmd, 20, y + 33, 0.45, self.PALETTE["bright_white"], 2)

        # ── Sección: log de telemetría ─────────────────────────────────────
        y += 55
        txt("TELEMETRÍA", 12, y, 0.38, self.PALETTE["cyber_cyan"])
        y += 8
        cv2.rectangle(frame, (12, y), (PANEL_W - 12, y + 42), (10, 10, 10), -1)
        lines = [self.status_msg[i:i+27] for i in range(0, min(54, len(self.status_msg)), 27)]
        for i, line in enumerate(lines[:2]):
            txt(line, 18, y + 15 + i * 15, 0.31, self.PALETTE["bright_white"])

        # ── FPS doble (cámara + inferencia) ───────────────────────────────
        y += 55
        txt(f"Cam FPS:  {self._fps_display:>3}",       12, y,      0.35, self.PALETTE["hud_gray"])
        txt(f"MP  FPS:  {self._inference_fps:>3}",     12, y + 14, 0.35, self.PALETTE["hud_gray"])

        # ── Pie: calibración y controles ──────────────────────────────────
        y = h - 28
        cal_ok  = self.classifier.calibrated
        cal_txt = "Calibrado ✓" if cal_ok else "[C] Calibrar"
        cal_clr = self.PALETTE["neon_green"] if cal_ok else self.PALETTE["gold_yellow"]
        txt(cal_txt, 12, y,      0.33, cal_clr)
        txt("[Q] Salir | [M] Modo | [C] Cal.", 12, y + 13, 0.28, self.PALETTE["hud_gray"])