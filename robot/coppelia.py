"""
Conexión y control del NiryoOne en CoppeliaSim.
Misma API y flujo que simulacion_completa.py (RemoteAPIClient + startSimulation).
"""

import time
from typing import Optional

from coppeliasim_zmqremoteapi_client import RemoteAPIClient

import config


class NiryoOneRobot:
    """Cliente ZMQ para el NiryoOne — copia fiel de simulacion_completa.py."""

    def __init__(self):
        self._client = None
        self._sim = None
        self._joint_handles: list = []
        self._gripper_signal: Optional[str] = None
        self.connected = False
        self.simulation_running = False
        self.gripper_closed = False
        self.last_error = ""

    def connect(self) -> bool:
        print("\n[Robot] Conectando con CoppeliaSim (ZMQ Remote API)...")
        self.last_error = ""

        # 1. Cliente ZMQ — igual que simulacion_completa.py
        try:
            self._client = RemoteAPIClient()
            self._sim = self._client.getObject("sim")
            print("[OK] Conectado a CoppeliaSim con exito.")
        except Exception as e:
            self.last_error = str(e)
            print(f"[ERROR] No se pudo conectar a CoppeliaSim: {e}")
            print("  -> Abre CoppeliaSim y carga la escena NiryoOne antes de ejecutar main.py")
            return False

        # 2. Obtener los 6 joints
        print("\n=== Obteniendo los joints del brazo ===")
        self._joint_handles = []
        for path in config.JOINT_PATHS:
            try:
                handle = self._sim.getObject(path)
                self._joint_handles.append(handle)
                print(f"  [OK] Joint encontrado: {path}")
            except Exception as e:
                print(f"  [ERROR] No se encontro {path}: {e}")

        if len(self._joint_handles) < 6:
            self.last_error = "Faltan joints del NiryoOne en la escena"
            print("\n[ERROR] No se encontraron los 6 joints principales del brazo.")
            return False

        # 3. Gripper dinámico
        print("\n=== Detectando Gripper dinamicamente ===")
        self._gripper_signal = None
        try:
            connection_handle = self._sim.getObject(config.GRIPPER_CONNECTION_PATH)
            gripper_child = self._sim.getObjectChild(connection_handle, 0)
            if gripper_child != -1:
                gripper_alias = self._sim.getObjectAlias(gripper_child, 4)
                self._gripper_signal = f"{gripper_alias}_close"
                print(f"  [OK] Gripper acoplado detectado!: {gripper_alias}")
                print(f"  [OK] Senal de control resuelta: '{self._gripper_signal}'")
            else:
                print("  [WARN] No hay pinza en '/NiryoOne/connection'.")
        except Exception as e:
            print(f"  [ERROR] Error al buscar el gripper: {e}")

        # 4. Iniciar simulación (obligatorio para que los joints se muevan)
        print("\n=== Iniciando Simulacion ===")
        try:
            self._sim.startSimulation()
            self.simulation_running = True
            print("[OK] Simulacion en marcha.")
        except Exception as e:
            # Si ya estaba corriendo, seguimos
            print(f"  [INFO] startSimulation: {e}")
            self.simulation_running = True

        time.sleep(0.5)

        if self._gripper_signal:
            self.open_gripper()

        self.connected = True
        print("[OK] Robot listo para control por mano.\n")
        return True

    def disconnect(self):
        if self._sim and self.simulation_running:
            try:
                time.sleep(0.3)
                self._sim.stopSimulation()
                print("[Robot] Simulacion detenida.")
            except Exception:
                pass
        self.connected = False
        self.simulation_running = False
        self._client = None
        self._sim = None
        self._joint_handles = []

    def get_joint_positions(self) -> list[float]:
        if not self._sim or not self._joint_handles:
            return []
        try:
            return [self._sim.getJointPosition(j) for j in self._joint_handles]
        except Exception as e:
            self.last_error = str(e)
            return []

    def set_joint_positions(self, angles: list[float]) -> bool:
        if not self.connected or not self._sim or len(angles) != 6:
            return False
        try:
            for joint, angle in zip(self._joint_handles, angles):
                self._sim.setJointTargetPosition(joint, float(angle))
            return True
        except Exception as e:
            self.last_error = str(e)
            print(f"[Robot] Error set_joint_positions: {e}")
            return False

    def move_to(self, target_angles: list[float], duration: float = 1.0, steps: int = 30) -> bool:
        """Movimiento interpolado — igual que simulacion_completa.py."""
        if not self.connected:
            return False
        try:
            start_angles = self.get_joint_positions()
            if len(start_angles) != 6:
                return False
            for step in range(steps):
                alpha = (step + 1) / steps
                for joint, start, end in zip(
                    self._joint_handles, start_angles, target_angles
                ):
                    pos = start + (end - start) * alpha
                    self._sim.setJointTargetPosition(joint, float(pos))
                time.sleep(duration / steps)
            return True
        except Exception as e:
            self.last_error = str(e)
            print(f"[Robot] Error move_to: {e}")
            return False

    def adjust_joints(self, deltas: list[float]) -> bool:
        """Joystick: lee posición actual y aplica delta."""
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
        if not self._gripper_signal or not self._sim:
            return False
        try:
            if close:
                self._sim.setInt32Signal(self._gripper_signal, 1)
            else:
                self._sim.clearInt32Signal(self._gripper_signal)
            self.gripper_closed = close
            return True
        except Exception as e:
            self.last_error = str(e)
            print(f"[Robot] Error gripper: {e}")
            return False

    def go_home(self) -> bool:
        return self.move_to([0.0] * 6, duration=2.0, steps=40)
