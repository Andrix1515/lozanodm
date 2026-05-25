"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         SISTEMA DE CONTROL ROBÓTICO POR GESTOS DE MANO                     ║
║         NiryoOne + CoppeliaSim + MediaPipe + OpenCV                        ║
║                                                                              ║
║  Arquitectura:                                                               ║
║    Cámara → MediaPipe → Intérprete de gestos → Controlador → CoppeliaSim   ║
╚══════════════════════════════════════════════════════════════════════════════╝

Dependencias:
    pip install coppeliasim-zmqremoteapi-client opencv-python mediapipe numpy

Uso:
    1. Abrir CoppeliaSim con la escena NiryoOne cargada
    2. Iniciar la simulación en CoppeliaSim (Play)
    3. Ejecutar este script: python hand_robot_control.py
    4. Mostrar la mano frente a la cámara
    5. Presionar 'c' para calibrar, 'q' para salir
"""

import cv2
import mediapipe as mp
import numpy as np
import math
import time
import sys
from collections import deque

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN GLOBAL
# Ajusta estos valores según tu setup
# ─────────────────────────────────────────────────────────────────────────────
CONFIG = {
    # CoppeliaSim
    "host": "localhost",
    "port": 23000,

    # Cámara
    "camera_index": 0,
    "target_fps": 30,
    "frame_width": 640,
    "frame_height": 480,

    # Suavizado exponencial (0=sin suavizado, 1=congelado)
    # Valores más altos = movimiento más suave pero más lento
    "smoothing_alpha": 0.25,

    # Tamaño del buffer para el filtro de mediana (frames)
    "median_buffer_size": 5,

    # Límites angulares de los joints en radianes [min, max]
    # Basados en las limitaciones físicas del NiryoOne real
    "joint_limits": [
        (-2.87, 2.87),   # Joint 1: Base (rotación horizontal)
        (-1.57, 0.64),   # Joint 2: Hombro (elevación)
        (-1.39, 1.57),   # Joint 3: Codo
        (-2.09, 2.09),   # Joint 4: Antebrazo (rotación)
        (-1.74, 1.74),   # Joint 5: Muñeca (flexión)
        (-2.53, 2.53),   # Joint 6: Muñeca (rotación)
    ],

    # Umbral para detectar mano abierta/cerrada (distancia normalizada)
    "grip_open_threshold": 0.08,
    "grip_close_threshold": 0.05,

    # Nombres de los joints del NiryoOne en CoppeliaSim
    # ⚠️ IMPORTANTE: Si tu modelo tiene nombres diferentes, cámbialos aquí
    "joint_paths": [
        '/NiryoOne/Joint',
        '/NiryoOne/Link/Joint',
        '/NiryoOne/Link/Joint/Link/Joint',
        '/NiryoOne/Link/Joint/Link/Joint/Link/Joint',
        '/NiryoOne/Link/Joint/Link/Joint/Link/Joint/Link/Joint',
        '/NiryoOne/Joint/Link/Joint/Link/Joint/Link/Joint/Link/Joint/Link/Joint',
    ],

    # Path del gripper
    "gripper_path": '/NiryoOne/NiryoLGripper',

    # Nombre de la señal del gripper (usado por el script Lua del gripper)
    # El gripper NiryoLGripper se controla con señales Int32, NO con setJointTargetPosition
    # Signal '{name}_close' = 1 → cierra | clear signal → abre
    "gripper_signal_name": 'NiryoLGripper',
}


# ═════════════════════════════════════════════════════════════════════════════
# MÓDULO 1: CONEXIÓN CON COPPELIASIM
# ═════════════════════════════════════════════════════════════════════════════

class CoppeliaSimController:
    """
    Maneja toda la comunicación con CoppeliaSim a través de ZeroMQ.
    
    Responsabilidades:
    - Conectar y desconectar del simulador
    - Obtener handles de los joints del NiryoOne
    - Enviar posiciones objetivo a cada joint
    - Controlar el gripper
    """

    def __init__(self, config: dict):
        self.config = config
        self.client = None
        self.sim = None
        self.joint_handles = []
        self.gripper_handle = None
        self.gripper_signal = None  # Nombre de la señal para controlar el gripper
        self.gripper_closed = False  # Estado actual del gripper
        self.connected = False
        self._last_positions = [0.0] * 6  # Caché de posiciones enviadas

    def connect(self) -> bool:
        """
        Establece la conexión con CoppeliaSim.
        
        Returns:
            True si la conexión fue exitosa, False en caso contrario.
        """
        print("\n" + "═" * 60)
        print("  MÓDULO 1: Conectando con CoppeliaSim")
        print("═" * 60)

        try:
            from coppeliasim_zmqremoteapi_client import RemoteAPIClient
            print(f"  ▶ Intentando conectar a {self.config['host']}:{self.config['port']}...")
            
            self.client = RemoteAPIClient(
                host=self.config['host'],
                port=self.config['port']
            )
            self.sim = self.client.getObject('sim')
            
            # Verificar que la simulación está corriendo
            sim_state = self.sim.getSimulationState()
            if sim_state == self.sim.simulation_stopped:
                print("  ⚠ La simulación está detenida. Iniciándola...")
                self.sim.startSimulation()
                time.sleep(1.0)  # Esperar a que inicialice

            print("  ✓ Conexión establecida con CoppeliaSim")
            self.connected = True
            return self._load_joints()

        except ImportError:
            print("  ✗ ERROR: No se encontró 'coppeliasim_zmqremoteapi_client'")
            print("    Instala con: pip install coppeliasim-zmqremoteapi-client")
            return False
        except Exception as e:
            print(f"  ✗ ERROR al conectar: {e}")
            print("    Verifica que CoppeliaSim esté abierto y con la escena cargada")
            return False

    def _load_joints(self) -> bool:
        """
        Carga los handles de los joints del NiryoOne.
        Verifica que cada joint exista antes de agregarlo.
        
        Returns:
            True si se encontraron todos los joints necesarios.
        """
        print("\n  ▶ Buscando joints del NiryoOne...")
        self.joint_handles = []
        
        for path in self.config['joint_paths']:
            try:
                handle = self.sim.getObject(path)
                self.joint_handles.append(handle)
                print(f"  ✓ Joint encontrado: {path}")
            except Exception as e:
                print(f"  ✗ Joint NO encontrado: {path}")
                print(f"    Error: {e}")

        # Intentar cargar el gripper (opcional)
        if self.config.get('gripper_path'):
            try:
                self.gripper_handle = self.sim.getObject(self.config['gripper_path'])
                # Obtener el nombre real del gripper para construir la señal
                gripper_alias = self.config.get('gripper_signal_name')
                if gripper_alias:
                    self.gripper_signal = gripper_alias + '_close'
                else:
                    # Intentar obtener el alias automáticamente
                    gripper_alias = self.sim.getObjectAlias(self.gripper_handle, 4)
                    self.gripper_signal = gripper_alias + '_close'
                print(f"  ✓ Gripper encontrado: {self.config['gripper_path']}")
                print(f"  ✓ Señal de control: {self.gripper_signal}")
            except Exception as e:
                print(f"  ⚠ Gripper no encontrado en: {self.config['gripper_path']}")
                print(f"    Error: {e}")
                print("    El control de garra estará deshabilitado")

        joints_found = len(self.joint_handles)
        print(f"\n  → Joints cargados: {joints_found}/{len(self.config['joint_paths'])}")

        if joints_found < 3:
            print("  ✗ ERROR: Se necesitan al menos 3 joints para operar")
            return False
        
        if joints_found < 6:
            print(f"  ⚠ Operando con {joints_found} joints (modo parcial)")
        
        return True

    def set_joint_positions(self, angles_rad: list):
        """
        Envía posiciones objetivo a todos los joints.
        Aplica límites físicos antes de enviar.
        
        Args:
            angles_rad: Lista de ángulos en radianes para cada joint.
        """
        if not self.connected or not self.joint_handles:
            return

        limits = self.config['joint_limits']
        
        for i, (handle, angle) in enumerate(zip(self.joint_handles, angles_rad)):
            # Aplicar límites físicos
            if i < len(limits):
                angle = np.clip(angle, limits[i][0], limits[i][1])
            
            try:
                self.sim.setJointTargetPosition(handle, float(angle))
                self._last_positions[i] = angle
            except Exception as e:
                print(f"  ⚠ Error en joint {i}: {e}")

    def set_gripper(self, open_fraction: float):
        """
        Controla el gripper del robot usando señales Int32.
        
        El gripper NiryoLGripper de CoppeliaSim se controla mediante
        señales, NO con setJointTargetPosition:
          - setInt32Signal('NiryoLGripper_close', 1)  → CIERRA el gripper
          - clearInt32Signal('NiryoLGripper_close')    → ABRE el gripper
        
        Args:
            open_fraction: 0.0 = cerrado, 1.0 = abierto
        """
        if self.gripper_signal is None:
            return
        
        try:
            # Umbral con histéresis para evitar parpadeo
            if open_fraction < 0.4 and not self.gripper_closed:
                # Cerrar gripper
                self.sim.setInt32Signal(self.gripper_signal, 1)
                self.gripper_closed = True
            elif open_fraction > 0.6 and self.gripper_closed:
                # Abrir gripper
                self.sim.clearInt32Signal(self.gripper_signal)
                self.gripper_closed = False
        except Exception as e:
            print(f"  ⚠ Error en gripper: {e}")

    def move_to_neutral(self, duration: float = 2.0):
        """Mueve el brazo a posición neutra de forma suave."""
        print("  ▶ Moviendo a posición neutra...")
        steps = int(duration / 0.05)
        
        try:
            current = [self.sim.getJointPosition(h) for h in self.joint_handles]
        except Exception:
            current = [0.0] * len(self.joint_handles)
        
        target = [0.0] * len(self.joint_handles)
        
        for step in range(steps):
            alpha = (step + 1) / steps
            interpolated = [c + (t - c) * alpha for c, t in zip(current, target)]
            self.set_joint_positions(interpolated)
            time.sleep(duration / steps)
        
        print("  ✓ Posición neutra alcanzada")

    def disconnect(self):
        """Desconecta de CoppeliaSim de forma segura."""
        if self.connected:
            try:
                self.move_to_neutral(duration=2.0)
                self.sim.stopSimulation()
                print("\n  ✓ CoppeliaSim desconectado correctamente")
            except Exception as e:
                print(f"\n  ⚠ Error al desconectar: {e}")
            finally:
                self.connected = False


# ═════════════════════════════════════════════════════════════════════════════
# MÓDULO 2: CAPTURA Y DETECCIÓN DE MANO
# ═════════════════════════════════════════════════════════════════════════════

class HandDetector:
    """
    Detecta y rastrea la mano usando MediaPipe Hands.
    
    Landmarks de MediaPipe (21 puntos):
        0: Muñeca
        1-4: Pulgar (base → punta)
        5-8: Índice (base → punta)
        9-12: Medio (base → punta)
        13-16: Anular (base → punta)
        17-20: Meñique (base → punta)
    
    Coordenadas: normalizadas [0,1] donde (0,0) es esquina sup-izq
    """

    def __init__(self, config: dict):
        self.config = config
        self.mp_hands = mp.solutions.hands
        self.mp_draw = mp.solutions.drawing_utils
        self.mp_styles = mp.solutions.drawing_styles
        
        # Inicializar detector MediaPipe
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,       # Modo video (más rápido)
            max_num_hands=1,               # Solo seguimos 1 mano
            min_detection_confidence=0.7,  # Confianza mínima de detección
            min_tracking_confidence=0.6,   # Confianza mínima de seguimiento
            model_complexity=0,            # 0=rápido, 1=preciso
        )
        
        print("\n" + "═" * 60)
        print("  MÓDULO 2: MediaPipe Hands inicializado")
        print("  → max_hands: 1 | detection_conf: 0.7 | tracking_conf: 0.6")
        print("═" * 60)

    def detect(self, frame_bgr: np.ndarray) -> tuple:
        """
        Procesa un frame y detecta la mano.
        
        Args:
            frame_bgr: Frame en formato BGR de OpenCV.
        
        Returns:
            Tupla (landmarks_dict | None, frame_anotado)
            landmarks_dict contiene puntos clave normalizados [0,1]
        """
        # MediaPipe requiere RGB
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        frame_rgb.flags.writeable = False  # Optimización de memoria
        
        results = self.hands.process(frame_rgb)
        
        frame_rgb.flags.writeable = True
        frame_annotated = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        
        if not results.multi_hand_landmarks:
            return None, frame_annotated
        
        # Tomar solo la primera mano detectada
        hand_landmarks = results.multi_hand_landmarks[0]
        
        # Dibujar landmarks con estilo personalizado
        self._draw_hand(frame_annotated, hand_landmarks)
        
        # Extraer coordenadas clave
        landmarks = self._extract_landmarks(hand_landmarks)
        
        return landmarks, frame_annotated

    def _extract_landmarks(self, hand_landmarks) -> dict:
        """
        Extrae los landmarks más relevantes en coordenadas normalizadas.
        
        Returns:
            Diccionario con puntos clave de la mano.
        """
        lm = hand_landmarks.landmark
        
        return {
            # Puntos de control principales
            'wrist':       (lm[0].x, lm[0].y, lm[0].z),
            'thumb_tip':   (lm[4].x, lm[4].y, lm[4].z),
            'thumb_ip':    (lm[3].x, lm[3].y, lm[3].z),
            'index_mcp':   (lm[5].x, lm[5].y, lm[5].z),
            'index_tip':   (lm[8].x, lm[8].y, lm[8].z),
            'middle_tip':  (lm[12].x, lm[12].y, lm[12].z),
            'ring_tip':    (lm[16].x, lm[16].y, lm[16].z),
            'pinky_tip':   (lm[20].x, lm[20].y, lm[20].z),
            'palm_center': (lm[9].x, lm[9].y, lm[9].z),  # Base dedo medio
            
            # Landmarks completos para análisis adicional
            'all': [(lm[i].x, lm[i].y, lm[i].z) for i in range(21)],
        }

    def _draw_hand(self, frame: np.ndarray, hand_landmarks):
        """Dibuja los landmarks con estilo visual mejorado."""
        h, w = frame.shape[:2]
        
        # Conexiones estándar de MediaPipe
        self.mp_draw.draw_landmarks(
            frame,
            hand_landmarks,
            self.mp_hands.HAND_CONNECTIONS,
            self.mp_styles.get_default_hand_landmarks_style(),
            self.mp_styles.get_default_hand_connections_style(),
        )
        
        # Resaltar punto de muñeca (referencia de movimiento)
        wrist = hand_landmarks.landmark[0]
        cx, cy = int(wrist.x * w), int(wrist.y * h)
        cv2.circle(frame, (cx, cy), 12, (0, 255, 100), -1)
        cv2.circle(frame, (cx, cy), 14, (255, 255, 255), 2)
        
        # Resaltar punta del índice (control de eje X)
        idx_tip = hand_landmarks.landmark[8]
        ix, iy = int(idx_tip.x * w), int(idx_tip.y * h)
        cv2.circle(frame, (ix, iy), 8, (0, 100, 255), -1)

    def close(self):
        """Libera recursos de MediaPipe."""
        self.hands.close()


# ═════════════════════════════════════════════════════════════════════════════
# MÓDULO 3 Y 4: INTERPRETACIÓN DE MOVIMIENTO Y LÍMITES
# ═════════════════════════════════════════════════════════════════════════════

class MovementInterpreter:
    """
    Convierte landmarks de la mano en ángulos para los joints del robot.
    
    ESTRATEGIA DE MAPEO:
    ┌─────────────────────────────────────────────────────────┐
    │  PROBLEMA: La mano humana tiene ~27 DOF                 │
    │  El NiryoOne tiene 6 DOF                                │
    │                                                         │
    │  SOLUCIÓN: Mapear los movimientos más significativos:   │
    │                                                         │
    │  Mano → Robot                                           │
    │  ────────────────────────────────────────────────────── │
    │  X de muñeca     → Joint 1 (Base, rotación horizontal) │
    │  Y de muñeca     → Joint 2 (Hombro, elevación)         │
    │  Z de muñeca     → Joint 3 (Codo, profundidad)         │
    │  Inclinación X   → Joint 4 (Antebrazo)                 │
    │  Inclinación Y   → Joint 5 (Muñeca flexión)            │
    │  Rotación palma  → Joint 6 (Muñeca rotación)           │
    │  Distancia p-i   → Gripper (abrir/cerrar)              │
    └─────────────────────────────────────────────────────────┘
    """

    def __init__(self, config: dict):
        self.config = config
        self.alpha = config['smoothing_alpha']  # Factor suavizado exponencial
        self.buffer_size = config['median_buffer_size']
        
        # Estado del suavizado exponencial
        self._smoothed_joints = [0.0] * 6
        self._smoothed_grip = 0.5
        
        # Buffer para filtro de mediana
        self._joint_buffers = [deque(maxlen=self.buffer_size) for _ in range(6)]
        
        # Estado de calibración
        self.calibrated = False
        self.neutral_wrist = (0.5, 0.5, 0.0)   # Centro de cámara por defecto
        self.neutral_palm_normal = (0.0, 0.0, 1.0)
        
        print("\n" + "═" * 60)
        print("  MÓDULO 3: Intérprete de movimiento inicializado")
        print(f"  → Suavizado alpha: {self.alpha}")
        print(f"  → Buffer mediana: {self.buffer_size} frames")
        print("═" * 60)

    def calibrate(self, landmarks: dict):
        """
        Registra la posición neutra de la mano para calibración.
        El usuario debe tener la mano en posición natural/relajada.
        
        Args:
            landmarks: Landmarks detectados en la posición neutra.
        """
        self.neutral_wrist = landmarks['wrist']
        self.neutral_palm_normal = self._compute_palm_normal(landmarks)
        self.calibrated = True
        print(f"\n  ✓ Calibración completada")
        print(f"    Muñeca neutral: x={self.neutral_wrist[0]:.3f}, "
              f"y={self.neutral_wrist[1]:.3f}, z={self.neutral_wrist[2]:.3f}")

    def interpret(self, landmarks: dict) -> tuple:
        """
        Convierte landmarks de mano en ángulos de joints y estado del gripper.
        
        Args:
            landmarks: Diccionario de landmarks de HandDetector.
        
        Returns:
            Tupla (joint_angles [rad], grip_open [0-1])
        """
        wrist = landmarks['wrist']
        
        # ── Offset desde posición neutral ──────────────────────────────────
        # Si está calibrado, usamos posición relativa a la neutral
        # Si no, usamos posición absoluta centrada en 0.5, 0.5
        if self.calibrated:
            dx = wrist[0] - self.neutral_wrist[0]  # Desplazamiento horizontal
            dy = wrist[1] - self.neutral_wrist[1]  # Desplazamiento vertical
            dz = wrist[2] - self.neutral_wrist[2]  # Profundidad
        else:
            dx = wrist[0] - 0.5   # Centro de pantalla = posición neutra
            dy = wrist[1] - 0.5
            dz = wrist[2]
        
        # ── Calcular inclinación de la palma ───────────────────────────────
        palm_normal = self._compute_palm_normal(landmarks)
        tilt_x = palm_normal[0]  # Inclinación lateral
        tilt_y = palm_normal[1]  # Inclinación frontal
        
        # ── Mapear a ángulos de joints ─────────────────────────────────────
        limits = self.config['joint_limits']
        
        # Joint 1 - BASE: Mueve horizontalmente según X de la muñeca
        # Rango de movimiento de la mano: ±0.4 unidades normalizadas
        # Amplificador 2.5 para usar el rango completo del joint
        j1 = self._map_value(dx, -0.4, 0.4, limits[0][0], limits[0][1])
        
        # Joint 2 - HOMBRO: Movimiento vertical (Y invertida porque OpenCV la invierte)
        # Mano arriba = Y pequeño → robot sube (ángulo negativo = arriba en NiryoOne)
        j2 = self._map_value(-dy, -0.4, 0.4, limits[1][0], limits[1][1])
        
        # Joint 3 - CODO: Profundidad de la mano (Z de MediaPipe es estimación)
        # Mano cerca = robot dobla el codo | Mano lejos = robot extiende
        j3 = self._map_value(dz, -0.15, 0.15, limits[2][0] * 0.6, limits[2][1] * 0.6)
        
        # Joint 4 - ANTEBRAZO: Inclinación lateral de la palma
        j4 = self._map_value(tilt_x, -0.7, 0.7, limits[3][0] * 0.7, limits[3][1] * 0.7)
        
        # Joint 5 - MUÑECA FLEXIÓN: Inclinación frontal de la palma
        j5 = self._map_value(tilt_y, -0.7, 0.7, limits[4][0] * 0.7, limits[4][1] * 0.7)
        
        # Joint 6 - MUÑECA ROTACIÓN: Rotación estimada de la mano
        palm_rotation = self._estimate_palm_rotation(landmarks)
        j6 = self._map_value(palm_rotation, -1.0, 1.0, limits[5][0] * 0.6, limits[5][1] * 0.6)
        
        raw_joints = [j1, j2, j3, j4, j5, j6]
        
        # ── Filtro de mediana (elimina picos de ruido) ─────────────────────
        for i, val in enumerate(raw_joints):
            self._joint_buffers[i].append(val)
        
        median_joints = [
            float(np.median(list(buf))) for buf in self._joint_buffers
        ]
        
        # ── Suavizado exponencial (movimiento fluido) ──────────────────────
        # Formula: smooth = alpha * raw + (1 - alpha) * previous
        # alpha pequeño → más suave (más lento en responder)
        # alpha grande → más reactivo (puede ser brusco)
        for i in range(6):
            self._smoothed_joints[i] = (
                self.alpha * median_joints[i] +
                (1 - self.alpha) * self._smoothed_joints[i]
            )
        
        # ── Gripper ────────────────────────────────────────────────────────
        grip_dist = self._compute_grip_distance(landmarks)
        # Normalizar: 0 = cerrado, 1 = abierto
        grip_open = np.clip(
            (grip_dist - self.config['grip_close_threshold']) /
            (self.config['grip_open_threshold'] - self.config['grip_close_threshold']),
            0.0, 1.0
        )
        self._smoothed_grip = (
            self.alpha * grip_open + (1 - self.alpha) * self._smoothed_grip
        )
        
        return list(self._smoothed_joints), float(self._smoothed_grip)

    # ── Funciones auxiliares ───────────────────────────────────────────────

    @staticmethod
    def _map_value(val: float, in_min: float, in_max: float,
                   out_min: float, out_max: float) -> float:
        """Mapea un valor de un rango a otro, con clampeo."""
        val = np.clip(val, in_min, in_max)
        return out_min + (val - in_min) / (in_max - in_min) * (out_max - out_min)

    @staticmethod
    def _compute_palm_normal(landmarks: dict) -> tuple:
        """
        Calcula el vector normal de la palma usando tres puntos:
        - Muñeca (0)
        - Base del índice (5)
        - Base del meñique (17)
        
        Este vector indica hacia dónde "mira" la palma.
        """
        all_lm = landmarks['all']
        wrist = np.array(all_lm[0])
        index_base = np.array(all_lm[5])
        pinky_base = np.array(all_lm[17])
        
        v1 = index_base - wrist
        v2 = pinky_base - wrist
        normal = np.cross(v1, v2)
        
        norm_mag = np.linalg.norm(normal)
        if norm_mag > 1e-6:
            normal = normal / norm_mag
        
        return tuple(normal)

    @staticmethod
    def _estimate_palm_rotation(landmarks: dict) -> float:
        """
        Estima la rotación de la palma en el plano XY.
        Usando el ángulo del vector muñeca → base del dedo medio.
        
        Returns:
            Ángulo normalizado en [-1, 1]
        """
        all_lm = landmarks['all']
        wrist = np.array([all_lm[0][0], all_lm[0][1]])
        mid_base = np.array([all_lm[9][0], all_lm[9][1]])
        
        vec = mid_base - wrist
        angle = math.atan2(vec[1], vec[0])  # Ángulo en radianes
        
        # Normalizar de [-pi, pi] a [-1, 1]
        return angle / math.pi

    @staticmethod
    def _compute_grip_distance(landmarks: dict) -> float:
        """
        Calcula la distancia normalizada entre pulgar e índice.
        Usado para detectar apertura/cierre de la garra.
        
        Returns:
            Distancia [0, ~0.3] — valores pequeños = mano cerrada
        """
        thumb = np.array(landmarks['thumb_tip'][:2])
        index = np.array(landmarks['index_tip'][:2])
        return float(np.linalg.norm(thumb - index))

    @staticmethod
    def is_hand_open(landmarks: dict, threshold: float = 0.07) -> bool:
        """
        Detecta si la mano está abierta comparando distancias dedo-muñeca.
        
        Returns:
            True si la mano está abierta
        """
        all_lm = landmarks['all']
        wrist = np.array(all_lm[0][:2])
        
        # Distancias de puntas de dedos a muñeca
        fingertips = [4, 8, 12, 16, 20]
        distances = [
            np.linalg.norm(np.array(all_lm[tip][:2]) - wrist)
            for tip in fingertips
        ]
        
        avg_distance = np.mean(distances)
        return avg_distance > threshold


# ═════════════════════════════════════════════════════════════════════════════
# MÓDULO 5 Y 6: CONTROL DEL ROBOT Y DETECCIÓN DE GESTOS
# ═════════════════════════════════════════════════════════════════════════════

class GestureDetector:
    """
    Detecta gestos específicos de la mano para comandos especiales.
    
    Gestos implementados:
    - OPEN: Mano abierta (todos los dedos extendidos)
    - CLOSED: Puño cerrado (todos los dedos flexionados)
    - POINT: Solo índice extendido
    - PEACE: Índice y medio extendidos
    """

    @staticmethod
    def _is_finger_extended(landmarks: dict, finger_tip: int, finger_pip: int) -> bool:
        """
        Determina si un dedo está extendido comparando punta vs articulación media.
        """
        all_lm = landmarks['all']
        tip = all_lm[finger_tip]
        pip = all_lm[finger_pip]
        wrist = all_lm[0]
        
        # Distancias a la muñeca
        dist_tip = math.sqrt((tip[0] - wrist[0])**2 + (tip[1] - wrist[1])**2)
        dist_pip = math.sqrt((pip[0] - wrist[0])**2 + (pip[1] - wrist[1])**2)
        
        return dist_tip > dist_pip * 1.1  # Punta más lejos que la articulación

    @classmethod
    def detect_gesture(cls, landmarks: dict) -> str:
        """
        Detecta el gesto actual de la mano.
        
        Returns:
            String del gesto: 'OPEN', 'CLOSED', 'POINT', 'PEACE', 'UNKNOWN'
        """
        # Dedos: (tip_idx, pip_idx)
        fingers = {
            'index':  (8, 6),
            'middle': (12, 10),
            'ring':   (16, 14),
            'pinky':  (20, 18),
        }
        
        extended = {
            name: cls._is_finger_extended(landmarks, tip, pip)
            for name, (tip, pip) in fingers.items()
        }
        
        n_extended = sum(extended.values())
        
        if n_extended >= 4:
            return 'OPEN'
        elif n_extended == 0:
            return 'CLOSED'
        elif extended['index'] and not extended['middle'] and not extended['ring']:
            return 'POINT'
        elif extended['index'] and extended['middle'] and not extended['ring']:
            return 'PEACE'
        else:
            return 'UNKNOWN'


# ═════════════════════════════════════════════════════════════════════════════
# MÓDULO 7: HUD (Heads-Up Display) – Visualización en pantalla
# ═════════════════════════════════════════════════════════════════════════════

class HUD:
    """
    Dibuja información de debug y estado directamente en el frame de la cámara.
    """

    COLORS = {
        'green':  (50, 220, 50),
        'red':    (50, 50, 220),
        'blue':   (220, 100, 50),
        'yellow': (50, 220, 220),
        'white':  (255, 255, 255),
        'black':  (0, 0, 0),
        'orange': (30, 160, 255),
        'cyan':   (220, 200, 50),
    }

    def draw(self, frame: np.ndarray, state: dict) -> np.ndarray:
        """
        Dibuja todos los elementos del HUD en el frame.
        
        Args:
            frame: Frame de OpenCV a anotar.
            state: Diccionario con el estado actual del sistema.
        
        Returns:
            Frame con HUD dibujado.
        """
        h, w = frame.shape[:2]
        
        # Fondo semi-transparente para el panel izquierdo
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (260, h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.4, frame, 0.6, 0, frame)
        
        y = 25
        
        # ── Título ─────────────────────────────────────────────────────────
        cv2.putText(frame, "ROBOT HAND CONTROL", (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    self.COLORS['cyan'], 2)
        y += 25
        
        # ── Estado de conexión ─────────────────────────────────────────────
        conn_color = self.COLORS['green'] if state.get('connected') else self.COLORS['red']
        conn_text = "CoppeliaSim: CONECTADO" if state.get('connected') else "CoppeliaSim: DESCONECTADO"
        cv2.putText(frame, conn_text, (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, conn_color, 1)
        y += 20
        
        # ── Estado de mano ─────────────────────────────────────────────────
        hand_color = self.COLORS['green'] if state.get('hand_detected') else self.COLORS['orange']
        hand_text = "Mano: DETECTADA" if state.get('hand_detected') else "Mano: NO DETECTADA"
        cv2.putText(frame, hand_text, (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, hand_color, 1)
        y += 20
        
        # ── Calibración ────────────────────────────────────────────────────
        cal_color = self.COLORS['green'] if state.get('calibrated') else self.COLORS['yellow']
        cal_text = "Calibrado: SI" if state.get('calibrated') else "Calibrado: NO (presiona C)"
        cv2.putText(frame, cal_text, (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, cal_color, 1)
        y += 25
        
        # ── Gesto detectado ────────────────────────────────────────────────
        gesture = state.get('gesture', 'N/A')
        gesture_colors = {
            'OPEN': self.COLORS['green'],
            'CLOSED': self.COLORS['red'],
            'POINT': self.COLORS['blue'],
            'PEACE': self.COLORS['yellow'],
        }
        g_color = gesture_colors.get(gesture, self.COLORS['white'])
        cv2.putText(frame, f"Gesto: {gesture}", (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, g_color, 1)
        y += 20
        
        # ── Gripper ────────────────────────────────────────────────────────
        grip = state.get('grip_open', 0.5)
        grip_text = f"Gripper: {'ABIERTO' if grip > 0.5 else 'CERRADO'} ({grip:.2f})"
        cv2.putText(frame, grip_text, (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, self.COLORS['white'], 1)
        y += 25
        
        # ── Ángulos de joints ──────────────────────────────────────────────
        cv2.putText(frame, "── JOINTS (rad) ──", (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.COLORS['cyan'], 1)
        y += 18
        
        joints = state.get('joints', [0.0] * 6)
        joint_names = ['J1 Base', 'J2 Hombro', 'J3 Codo',
                       'J4 Antebrazo', 'J5 Muñeca', 'J6 Rot']
        
        for i, (name, angle) in enumerate(zip(joint_names, joints)):
            # Barra de progreso del joint
            limit = self.config_limits[i] if hasattr(self, 'config_limits') else (-3.14, 3.14)
            progress = (angle - limit[0]) / (limit[1] - limit[0])
            bar_w = int(progress * 80)
            bar_x = 145
            
            cv2.rectangle(frame, (bar_x, y - 10), (bar_x + 80, y - 2),
                          (60, 60, 60), -1)
            cv2.rectangle(frame, (bar_x, y - 10), (bar_x + bar_w, y - 2),
                          self.COLORS['green'], -1)
            
            cv2.putText(frame, f"{name}: {angle:+.2f}", (10, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, self.COLORS['white'], 1)
            y += 17
        
        # ── FPS ────────────────────────────────────────────────────────────
        fps = state.get('fps', 0)
        fps_color = self.COLORS['green'] if fps > 20 else self.COLORS['yellow']
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, h - 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, fps_color, 1)
        
        # ── Controles ──────────────────────────────────────────────────────
        cv2.putText(frame, "Q=Salir | C=Calibrar | R=Reset",
                    (10, h - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.38,
                    self.COLORS['white'], 1)
        
        # ── Cruz de referencia en el centro de la imagen ───────────────────
        cx, cy = w // 2, h // 2
        cv2.line(frame, (cx - 15, cy), (cx + 15, cy), (100, 100, 100), 1)
        cv2.line(frame, (cx, cy - 15), (cx, cy + 15), (100, 100, 100), 1)
        
        return frame

    def set_joint_limits(self, limits: list):
        """Registra los límites de joints para la barra de progreso."""
        self.config_limits = limits


# ═════════════════════════════════════════════════════════════════════════════
# MÓDULO 8: SISTEMA PRINCIPAL – ORQUESTACIÓN
# ═════════════════════════════════════════════════════════════════════════════

class HandRobotSystem:
    """
    Orquesta todos los módulos del sistema.
    
    Flujo de datos por frame:
    1. Capturar frame de cámara
    2. Detectar landmarks de mano
    3. Interpretar movimiento → ángulos de joints
    4. Enviar ángulos a CoppeliaSim
    5. Detectar gestos → controlar gripper
    6. Actualizar HUD y mostrar en pantalla
    """

    def __init__(self):
        self.config = CONFIG
        self.running = False
        
        # Inicializar módulos
        self.robot = CoppeliaSimController(self.config)
        self.detector = HandDetector(self.config)
        self.interpreter = MovementInterpreter(self.config)
        self.gesture_detector = GestureDetector()
        self.hud = HUD()
        self.hud.set_joint_limits(self.config['joint_limits'])
        
        # Estado del sistema
        self.state = {
            'connected': False,
            'hand_detected': False,
            'calibrated': False,
            'gesture': 'UNKNOWN',
            'joints': [0.0] * 6,
            'grip_open': 0.5,
            'fps': 0.0,
        }
        
        # Métricas de rendimiento
        self._fps_buffer = deque(maxlen=30)
        self._last_frame_time = time.time()
        
        # Timer para mensajes de "mano no detectada"
        self._no_hand_start = None
        self._no_hand_logged = False

    def setup(self) -> bool:
        """
        Inicializa todos los componentes del sistema.
        
        Returns:
            True si todo está listo para operar.
        """
        print("\n" + "═" * 60)
        print("  SISTEMA DE CONTROL ROBÓTICO POR GESTOS")
        print("  NiryoOne + CoppeliaSim + MediaPipe")
        print("═" * 60)
        
        # Conectar con CoppeliaSim
        robot_ok = self.robot.connect()
        self.state['connected'] = robot_ok
        
        if not robot_ok:
            print("\n  ⚠ Continuando en MODO DEMO (sin robot)")
            print("    El sistema funcionará pero no moverá el brazo")
        
        # Verificar cámara
        print("\n" + "═" * 60)
        print("  MÓDULO 2: Inicializando cámara")
        print("═" * 60)
        
        self.cap = cv2.VideoCapture(self.config['camera_index'])
        
        if not self.cap.isOpened():
            print(f"  ✗ ERROR: No se pudo abrir la cámara {self.config['camera_index']}")
            return False
        
        # Configurar resolución
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config['frame_width'])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config['frame_height'])
        self.cap.set(cv2.CAP_PROP_FPS, self.config['target_fps'])
        
        # Reducir buffer para menor latencia
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        actual_w = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_h = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
        
        print(f"  ✓ Cámara abierta: {int(actual_w)}x{int(actual_h)} @ {actual_fps}fps")
        
        return True

    def _update_fps(self):
        """Calcula FPS usando media móvil."""
        now = time.time()
        dt = now - self._last_frame_time
        self._last_frame_time = now
        
        if dt > 0:
            self._fps_buffer.append(1.0 / dt)
            self.state['fps'] = np.mean(self._fps_buffer)

    def _handle_no_hand(self):
        """
        Maneja el caso cuando no se detecta mano.
        Registra cuánto tiempo lleva sin detectarse y aplica estrategia.
        """
        if self._no_hand_start is None:
            self._no_hand_start = time.time()
            self._no_hand_logged = False
        
        elapsed = time.time() - self._no_hand_start
        
        # Después de 1 segundo sin mano, loguear
        if elapsed > 1.0 and not self._no_hand_logged:
            print("  ⚠ Sin detección de mano (robot en posición de espera)")
            self._no_hand_logged = True
        
        # El robot mantiene su última posición (no enviar comandos nuevos)
        # Esto evita que el brazo caiga o haga movimientos erráticos

    def _reset_no_hand_timer(self):
        """Reinicia el timer de mano no detectada."""
        if self._no_hand_start is not None:
            if (time.time() - self._no_hand_start) > 1.0:
                print("  ✓ Mano detectada nuevamente")
        self._no_hand_start = None
        self._no_hand_logged = False

    def run(self):
        """
        Loop principal del sistema.
        Ejecuta el ciclo de percepción-interpretación-control a máxima velocidad.
        """
        print("\n" + "═" * 60)
        print("  MÓDULO 8: INICIANDO LOOP PRINCIPAL")
        print("═" * 60)
        print("\n  Instrucciones:")
        print("  • C = Calibrar posición neutra")
        print("  • R = Reset robot a posición neutra")
        print("  • Q = Salir del sistema")
        print("\n  Mostrando ventana de cámara...\n")
        
        self.running = True
        frame_count = 0
        
        try:
            while self.running:
                # ── Captura de frame ───────────────────────────────────────
                ret, frame = self.cap.read()
                if not ret:
                    print("  ⚠ Error al leer frame de cámara")
                    time.sleep(0.01)
                    continue
                
                # Espejo horizontal para control más intuitivo
                frame = cv2.flip(frame, 1)
                frame_count += 1
                
                # ── Detección de mano ──────────────────────────────────────
                landmarks, frame_annotated = self.detector.detect(frame)
                
                self.state['hand_detected'] = landmarks is not None
                self.state['calibrated'] = self.interpreter.calibrated
                
                if landmarks is not None:
                    self._reset_no_hand_timer()
                    
                    # ── Interpretación de movimiento ───────────────────────
                    joint_angles, grip_open = self.interpreter.interpret(landmarks)
                    
                    self.state['joints'] = joint_angles
                    self.state['grip_open'] = grip_open
                    
                    # ── Detección de gesto ─────────────────────────────────
                    gesture = self.gesture_detector.detect_gesture(landmarks)
                    self.state['gesture'] = gesture
                    
                    # ── Control del robot ──────────────────────────────────
                    if self.state['connected']:
                        self.robot.set_joint_positions(joint_angles)
                        self.robot.set_gripper(grip_open)
                    
                    # Debug en consola cada 30 frames
                    if frame_count % 30 == 0:
                        angles_str = ' | '.join(f'{a:+.2f}' for a in joint_angles)
                        print(f"  [J]: {angles_str} | Grip: {grip_open:.2f} | {gesture}")
                
                else:
                    # Sin mano: mantener posición
                    self._handle_no_hand()
                    self.state['gesture'] = 'N/A'
                
                # ── Actualizar HUD ─────────────────────────────────────────
                self._update_fps()
                frame_annotated = self.hud.draw(frame_annotated, self.state)
                
                # ── Mostrar frame ──────────────────────────────────────────
                cv2.imshow('Hand Robot Control | NiryoOne', frame_annotated)
                
                # ── Captura de teclado ─────────────────────────────────────
                key = cv2.waitKey(1) & 0xFF
                
                if key == ord('q') or key == 27:  # Q o ESC = salir
                    print("\n  ▶ Saliendo del sistema...")
                    self.running = False
                
                elif key == ord('c'):  # C = calibrar
                    if landmarks is not None:
                        print("\n  ▶ Calibrando posición neutra...")
                        self.interpreter.calibrate(landmarks)
                    else:
                        print("  ⚠ No hay mano visible para calibrar")
                
                elif key == ord('r'):  # R = reset robot
                    print("\n  ▶ Reseteando robot a posición neutra...")
                    if self.state['connected']:
                        self.robot.move_to_neutral(duration=2.0)
                    # Reset del intérprete
                    self.interpreter._smoothed_joints = [0.0] * 6
        
        except KeyboardInterrupt:
            print("\n  ▶ Interrumpido por el usuario")
        
        finally:
            self.cleanup()

    def cleanup(self):
        """Limpieza ordenada de todos los recursos."""
        print("\n  ▶ Limpiando recursos...")
        
        self.running = False
        
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
            print("  ✓ Cámara liberada")
        
        cv2.destroyAllWindows()
        print("  ✓ Ventanas cerradas")
        
        if hasattr(self, 'detector'):
            self.detector.close()
            print("  ✓ MediaPipe liberado")
        
        if hasattr(self, 'robot') and self.robot.connected:
            self.robot.disconnect()
        
        print("\n  Sistema cerrado correctamente.")


# ═════════════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ═════════════════════════════════════════════════════════════════════════════

def main():
    """Función principal del sistema."""
    system = HandRobotSystem()
    
    if not system.setup():
        print("\n✗ Error en la inicialización. Verifica los requisitos.")
        sys.exit(1)
    
    system.run()


if __name__ == '__main__':
    main()


# ═════════════════════════════════════════════════════════════════════════════
# GUÍA DE EJECUCIÓN
# ═════════════════════════════════════════════════════════════════════════════
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  GUÍA PASO A PASO PARA EJECUTAR EL SISTEMA                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

PASO 1 – Instalar dependencias
──────────────────────────────
    pip install coppeliasim-zmqremoteapi-client opencv-python mediapipe numpy

PASO 2 – Abrir CoppeliaSim
───────────────────────────
    • Abrir CoppeliaSim 4.x o superior
    • Cargar la escena con el modelo NiryoOne
    • Verificar que los nombres de joints coinciden con CONFIG['joint_paths']
    • Presionar el botón PLAY (▶) para iniciar la simulación

PASO 3 – Ejecutar el script
────────────────────────────
    python hand_robot_control.py

PASO 4 – Calibración inicial (RECOMENDADO)
───────────────────────────────────────────
    • Coloca la mano frente a la cámara en posición neutra/relajada
    • Presiona 'C' para registrar la posición de referencia
    • Esto mejora mucho el control ya que los movimientos serán relativos

PASO 5 – Controlar el robot
────────────────────────────
    • Mueve la muñeca IZQUIERDA/DERECHA → Joint 1 (base rota)
    • Mueve la muñeca ARRIBA/ABAJO → Joint 2 (hombro sube/baja)
    • Acerca/aleja la mano → Joint 3 (codo se dobla/estira)
    • Inclina la palma LATERALMENTE → Joint 4 (antebrazo rota)
    • Inclina la palma HACIA ADELANTE/ATRÁS → Joint 5 (muñeca flexiona)
    • Rota la mano → Joint 6 (rotación de muñeca)
    • Junta/separa pulgar e índice → Gripper (abrir/cerrar)

TECLAS:
    Q o ESC → Salir (el robot vuelve a posición neutra)
    C       → Calibrar posición neutra de la mano
    R       → Reset: mover robot a posición neutra

══════════════════════════════════════════════════════════════════════════════

SOLUCIÓN DE PROBLEMAS
─────────────────────
• "No se encontró joint": Los nombres de joints en tu escena pueden diferir.
  Abre el árbol de objetos en CoppeliaSim y actualiza CONFIG['joint_paths'].

• "No se pudo conectar": Verifica que CoppeliaSim está abierto y la 
  simulación está en estado PLAY. Verifica el puerto (default: 23000).

• "Cámara no disponible": Cambia CONFIG['camera_index'] a 1, 2, etc.

• Movimiento brusco: Reduce CONFIG['smoothing_alpha'] (ej: 0.1)
  Movimiento lento: Aumenta CONFIG['smoothing_alpha'] (ej: 0.4)

• Robot se mueve poco: El rango de movimiento de mano es pequeño,
  el mapeo amplifica automáticamente. Aumenta el factor en _map_value.

CAMBIAR NOMBRES DE JOINTS
──────────────────────────
Si tu modelo NiryoOne usa nombres diferentes:
1. En CoppeliaSim, clic derecho en el joint → "Object properties"
2. Copia el nombre completo con su jerarquía (/Padre/Hijo/Joint)
3. Actualiza CONFIG['joint_paths'] en la sección de configuración

══════════════════════════════════════════════════════════════════════════════
"""