"""
Conexión y control del NiryoOne en CoppeliaSim (ASÍNCRONO).
Mantiene alta respuesta de la cámara moviendo las llamadas síncronas de red a un hilo secundario.
"""

import logging
import math
import time
import threading
from typing import Optional

from coppeliasim_zmqremoteapi_client import RemoteAPIClient

import config
from utils.kinematics import clamp_joint_angles, is_near_singularity

logger = logging.getLogger(__name__)


class NiryoOneRobotWorker(threading.Thread):
    """
    Hilo de trabajo secundario para enviar posiciones e interactuar con CoppeliaSim.
    Evita latencias de red en el hilo de procesamiento de cámara.
    """
    def __init__(self, parent):
        super().__init__(daemon=True)
        self.parent = parent
        self.stop_event = threading.Event()
        self.new_command_event = threading.Event()
        self.init_event = threading.Event()
        self.connected = False
        
        self.client = None
        self.sim = None
        self.joint_handles = []
        self.gripper_signal = None
        self.gripper_closed = False
        
        # Estado compartido protegido por candado
        self.lock = threading.Lock()
        self.target_joints = None
        self.target_gripper = None
        self.current_joints = [0.0] * 6

    def _try_connect(self):
        last_exception = None
        for port in config.REMOTE_API_PORTS:
            try:
                client = RemoteAPIClient(host=config.REMOTE_API_HOST, port=port)
                sim = client.require("sim")
                print(f"[Robot] Conectado a CoppeliaSim en {config.REMOTE_API_HOST}:{port}")
                return client, sim
            except Exception as exc:
                last_exception = exc
                print(f"[Robot] Falló la conexión en {config.REMOTE_API_HOST}:{port}: {exc}")
                continue
        raise RuntimeError(
            f"No se pudo conectar a CoppeliaSim ZMQ Remote API en {config.REMOTE_API_HOST}:{config.REMOTE_API_PORTS}."
            f" Último error: {last_exception}"
        )

    def _find_joint_handles(self):
        handles = []
        for path in config.JOINT_PATHS:
            try:
                handle = self.sim.getObject(path)
            except Exception:
                handle = -1
            if isinstance(handle, int) and handle != -1 and handle not in handles:
                handles.append(handle)
                if len(handles) == 6:
                    break
        if len(handles) < 6:
            raise RuntimeError("No se detectaron 6 joints NiryoOne válidos en la escena.")
        return handles

    def run(self):
        try:
            self.client, self.sim = self._try_connect()
            
            # Cargar joints
            self.joint_handles = self._find_joint_handles()
            
            # Detectar pinza
            try:
                connection_handle = self.sim.getObject(config.GRIPPER_CONNECTION_PATH)
                gripper_child = self.sim.getObjectChild(connection_handle, 0)
                if gripper_child != -1:
                    gripper_alias = self.sim.getObjectAlias(gripper_child, 4)
                    self.gripper_signal = f"{gripper_alias}_close"
            except Exception:
                pass
                
            # Iniciar simulación si no está iniciada
            try:
                self.sim.startSimulation()
            except Exception:
                pass
                
            if len(self.joint_handles) >= 6:
                self.connected = True
        except Exception as e:
            self.parent.last_error = str(e)
            self.connected = False
            
        self.init_event.set()
        
        if not self.connected:
            return
            
        # Lectura inicial de posiciones reales
        try:
            initial = [self.sim.getJointPosition(j) for j in self.joint_handles]
            if len(initial) == 6:
                with self.lock:
                    self.current_joints = initial
        except Exception:
            pass

        while not self.stop_event.is_set():
            # Esperar nuevos comandos o procesar con timeout bajo para keepalive
            self.new_command_event.wait(timeout=0.015)
            self.new_command_event.clear()
            
            with self.lock:
                joints = self.target_joints
                gripper = self.target_gripper
                self.target_joints = None
                self.target_gripper = None
                
            # 1. Aplicar comandos de joints
            if joints is not None:
                try:
                    for handle, angle in zip(self.joint_handles, joints):
                        self.sim.setJointTargetPosition(handle, float(angle))
                except Exception as e:
                    self.parent.last_error = str(e)
                    
            # 2. Aplicar comandos de gripper
            if gripper is not None and self.gripper_signal is not None:
                try:
                    if gripper:
                        self.sim.setInt32Signal(self.gripper_signal, 1)
                        self.gripper_closed = True
                    else:
                        self.sim.clearInt32Signal(self.gripper_signal)
                        self.gripper_closed = False
                except Exception as e:
                    self.parent.last_error = str(e)
                    
            # 3. Leer posiciones del simulador en segundo plano (para la caché del joystick)
            try:
                current = [self.sim.getJointPosition(j) for j in self.joint_handles]
                if len(current) == 6:
                    with self.lock:
                        self.current_joints = current
            except Exception:
                pass


class NiryoOneRobot:
    """Cliente asíncrono para el control del NiryoOne."""

    def __init__(self):
        self._worker = None
        self.connected = False
        self.simulation_running = False
        self.gripper_closed = False
        self.last_error = ""

    def connect(self) -> bool:
        print("\n[Robot] Conectando con CoppeliaSim (ZMQ Remote API asíncrono)...")
        self.last_error = ""

        self._worker = NiryoOneRobotWorker(self)
        self._worker.start()
        
        # Esperar inicialización (máximo 5 segundos)
        success = self._worker.init_event.wait(timeout=5.0)
        if not success or not self._worker.connected:
            print("[ERROR] No se pudo conectar a CoppeliaSim en segundo plano.")
            if self.last_error:
                print(f"[ERROR] Detalle: {self.last_error}")
            self.connected = False
            return False
            
        self.connected = True
        self.simulation_running = True
        self.gripper_closed = self._worker.gripper_closed
        print("[OK] Hilo de robot conectado y listo.\n")
        return True

    def disconnect(self):
        if self._worker and self.connected:
            try:
                self._worker.stop_event.set()
                self._worker.sim.stopSimulation()
                print("[Robot] Simulación detenida.")
            except Exception:
                pass
        self.connected = False
        self.simulation_running = False
        self._worker = None

    def _joint_angles_degrees(self, angles: list[float]) -> dict[str, float]:
        return {f"joint{i + 1}": math.degrees(angle) for i, angle in enumerate(angles)}

    def _joint_angles_radians(self, joint_angles: dict[str, float]) -> list[float]:
        return [math.radians(joint_angles[f"joint{i + 1}"]) for i in range(6)]

    def _validate_target_angles(self, target_angles: list[float]) -> list[float] | None:
        angle_map = self._joint_angles_degrees(target_angles)
        clamped_map = clamp_joint_angles(angle_map)
        near_singularity, message = is_near_singularity(clamped_map)
        if near_singularity:
            logger.warning("Singularidad detectada: %s", message)
            logger.warning("Se cancela el movimiento y se retorna a HOME seguro.")
            return None
        return self._joint_angles_radians(clamped_map)

    def get_joint_positions(self) -> list[float]:
        """Consulta la posición desde el caché local en memoria (ultra-rápido)."""
        if not self.connected or not self._worker:
            return []
        with self._worker.lock:
            return list(self._worker.current_joints)

    def set_joint_positions(self, angles: list[float]) -> bool:
        if not self.connected or not self._worker or len(angles) != 6:
            return False
        validated = self._validate_target_angles(angles)
        if validated is None:
            return self.go_home()
            
        with self._worker.lock:
            self._worker.target_joints = validated
        self._worker.new_command_event.set()
        return True

    def move_to(self, target_angles: list[float], duration: float = 1.0, steps: int = 30) -> bool:
        """Movimiento interpolado (usado en Home / Calibración)."""
        if not self.connected or len(target_angles) != 6:
            return False

        validated = self._validate_target_angles(target_angles)
        if validated is None:
            return self.go_home()

        try:
            start_angles = self.get_joint_positions()
            if len(start_angles) != 6:
                return False
            for step in range(steps):
                alpha = (step + 1) / steps
                interpolated = [start + (end - start) * alpha for start, end in zip(start_angles, validated)]
                
                with self._worker.lock:
                    self._worker.target_joints = interpolated
                self._worker.new_command_event.set()
                time.sleep(duration / steps)
            return True
        except Exception as e:
            self.last_error = str(e)
            print(f"[Robot] Error move_to: {e}")
            return False

    def adjust_joints(self, deltas: list[float]) -> bool:
        """Joystick: lee la postura actual del caché e incrementa deltas de forma instantánea."""
        current = self.get_joint_positions()
        if len(current) != 6:
            return False
        target = [c + d for c, d in zip(current, deltas)]
        return self.set_joint_positions(target)

    def open_gripper(self) -> bool:
        return self._control_gripper(False)

    def close_gripper(self) -> bool:
        return self._control_gripper(True)

    def _control_gripper(self, close: bool) -> bool:
        if not self.connected or not self._worker:
            return False
        with self._worker.lock:
            self._worker.target_gripper = close
        self._worker.new_command_event.set()
        self.gripper_closed = close
        return True

    def go_home(self) -> bool:
        """Mueve el robot a la configuración HOME segura definida en config.JOINT_HOME."""
        return self.move_to(list(config.JOINT_HOME.values()), duration=2.0, steps=40)
