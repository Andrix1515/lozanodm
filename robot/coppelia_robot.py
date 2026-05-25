"""
CoppeliaSim Robot Adapter — OPTIMIZED v2.2  (ZMQ thread-safe, no-lag)
──────────────────────────────────────────────────────────────────────
PROBLEMA RAÍZ RESUELTO:
  ZeroMQ NO es thread-safe. Todos los sockets ZMQ deben usarse desde
  el mismo hilo que los creó.

SOLUCIÓN — patrón Command Queue con cancelación:
  • Un único hilo worker (_zmq_worker) posee el socket ZMQ y ejecuta
    TODAS las operaciones sim.* en secuencia.
  • Mecanismo de flush: cuando llega un nuevo comando de movimiento,
    se vacía la cola de comandos pendientes y se cancela la
    interpolación en curso, evitando acumulación de comandos.
  • get_state() lee solo variables Python cacheadas (nunca toca ZMQ).
"""

import time
import math
import queue
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from robot.base_robot import BaseRobot
import config


# ── Descriptor de comando para la cola ────────────────────────────────────
@dataclass
class _Cmd:
    fn:      Callable          # función a ejecutar (recibe sim como 1er arg)
    args:    tuple  = field(default_factory=tuple)
    kwargs:  dict   = field(default_factory=dict)
    result:  list   = field(default_factory=list)   # [value] cuando termina
    done:    threading.Event = field(default_factory=threading.Event)
    blocking: bool = False     # Si True, el llamante espera done
    is_movement: bool = False  # Si True, es un comando de movimiento largo


class CoppeliaRobotAdapter(BaseRobot):
    """
    Adapter para CoppeliaSim — NiryoOne.
    Thread-safe: todas las llamadas ZMQ ocurren dentro de _zmq_worker.
    """

    def __init__(self):
        # ── Estado interno (solo escrito por _zmq_worker) ──────────────────
        self._sim           = None
        self._client        = None
        self._joint_handles = []
        self._gripper_signal= None

        # ── Estado cacheado (leído desde cualquier hilo, escrito por worker) 
        self.connected      = False
        self.gripper_closed = False
        self.current_pose   = "UNKNOWN"
        self._cached_joints = [0.0] * 6   # Cache de posiciones articulares
        self._is_moving     = False

        # ── Cancelación de interpolación ──────────────────────────────────
        self._cancel_interpolation = threading.Event()

        # ── Cola de comandos ZMQ ──────────────────────────────────────────
        self._cmd_queue = queue.Queue()
        self._worker    = threading.Thread(
            target=self._zmq_worker, name="ZMQ-Worker", daemon=True
        )
        self._worker.start()

    # ═══════════════════════════════════════════════════════════════════════
    # COLA DE COMANDOS — API INTERNA
    # ═══════════════════════════════════════════════════════════════════════

    def _enqueue(self, fn: Callable, *args, blocking=False,
                 is_movement=False, **kwargs) -> Any:
        """
        Encola una función para ejecutarse en el hilo ZMQ.
        Si blocking=True, espera el resultado.
        Si is_movement=True, primero vacía la cola y cancela interpolación activa.
        """
        if is_movement:
            self._flush_queue()

        cmd = _Cmd(fn=fn, args=args, kwargs=kwargs, blocking=blocking,
                   is_movement=is_movement)
        self._cmd_queue.put(cmd)
        if blocking:
            cmd.done.wait()
            return cmd.result[0] if cmd.result else None
        return None

    def _flush_queue(self):
        """
        Vacía la cola de comandos pendientes y cancela la interpolación
        en curso. Esto evita la acumulación de movimientos obsoletos.
        """
        # Señalar cancelación de interpolación en curso
        self._cancel_interpolation.set()

        # Drenar la cola de comandos pendientes
        dropped = 0
        while True:
            try:
                old_cmd = self._cmd_queue.get_nowait()
                # Desbloquear a cualquiera que espere este comando
                old_cmd.result.append(None)
                old_cmd.done.set()
                self._cmd_queue.task_done()
                dropped += 1
            except queue.Empty:
                break

        if dropped > 0:
            print(f"[ZMQ-Worker] Cola vaciada: {dropped} comandos descartados.")

    def _zmq_worker(self):
        """
        Hilo dedicado: único propietario del socket ZMQ.
        Procesa comandos de la cola de forma secuencial.
        """
        while True:
            try:
                cmd: _Cmd = self._cmd_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            # Limpiar flag de cancelación antes de ejecutar nuevo comando
            if cmd.is_movement:
                self._cancel_interpolation.clear()

            try:
                result = cmd.fn(self._sim, *cmd.args, **cmd.kwargs)
                cmd.result.append(result)
            except Exception as e:
                print(f"[ZMQ-Worker] Error ejecutando comando: {e}")
                cmd.result.append(None)
            finally:
                cmd.done.set()
                self._cmd_queue.task_done()

    # ═══════════════════════════════════════════════════════════════════════
    # CONEXIÓN (bloqueante — se llama una vez al inicio)
    # ═══════════════════════════════════════════════════════════════════════

    def connect(self) -> bool:
        print(f"[Coppelia] Conectando a {config.HOST}:{config.PORT}...")
        return self._enqueue(self._do_connect, blocking=True)

    def _do_connect(self, _sim_ignored) -> bool:
        """Ejecutado en _zmq_worker. Crea el cliente ZMQ y configura el brazo."""
        try:
            from coppeliasim_zmqremoteapi_client import RemoteAPIClient
            self._client = RemoteAPIClient(host=config.HOST, port=config.PORT)
            self._sim    = self._client.getObject('sim')

            if self._sim.getSimulationState() == self._sim.simulation_stopped:
                print("[Coppelia] Iniciando simulación...")
                self._sim.startSimulation()
                time.sleep(1.0)

            # Cargar joints
            self._joint_handles = []
            for path in config.JOINT_PATHS:
                try:
                    self._joint_handles.append(self._sim.getObject(path))
                except Exception as je:
                    print(f"[Coppelia] Joint '{path}' no encontrado: {je}")

            if len(self._joint_handles) < 6:
                print(f"[Coppelia] ERROR: {len(self._joint_handles)}/6 joints.")
                return False

            self._gripper_signal = self._probe_gripper_internal()
            self.connected = True
            print("[Coppelia] Conexión exitosa.")
            self._do_move_home(None, duration=1.5)
            return True

        except Exception as e:
            print(f"[Coppelia] Fallo de conexión: {e}")
            self.connected = False
            return False

    def _probe_gripper_internal(self) -> Optional[str]:
        """Llamado desde _zmq_worker durante connect."""
        try:
            conn  = self._sim.getObject('/NiryoOne/connection')
            child = self._sim.getObjectChild(conn, 0)
            if child != -1:
                alias  = self._sim.getObjectAlias(child, 4)
                signal = f"{alias}_close"
                print(f"[Coppelia] Gripper → señal: '{signal}'")
                return signal
            self._sim.getObject(config.GRIPPER_PATH)
            signal = f"{config.GRIPPER_SIGNAL_NAME}_close"
            print(f"[Coppelia] Gripper fallback → señal: '{signal}'")
            return signal
        except Exception as e:
            print(f"[Coppelia] Sin gripper: {e}")
            return None

    def disconnect(self):
        self._enqueue(self._do_disconnect, blocking=True)

    def _do_disconnect(self, _sim) -> None:
        if not self.connected:
            return
        try:
            self._do_move_home(None, duration=1.5)
            self._sim.stopSimulation()
            print("[Coppelia] Simulación detenida.")
        except Exception as e:
            print(f"[Coppelia] Error al desconectar: {e}")
        finally:
            self.connected = False
            self._sim      = None
            self._client   = None

    # ═══════════════════════════════════════════════════════════════════════
    # HELPERS INTERNOS (ejecutados en _zmq_worker)
    # ═══════════════════════════════════════════════════════════════════════

    def _read_joints(self) -> list:
        """Lee posiciones articulares y actualiza cache. Solo desde worker."""
        try:
            positions = [self._sim.getJointPosition(j) for j in self._joint_handles]
            self._cached_joints = positions
            return positions
        except Exception:
            return list(self._cached_joints)

    def _do_interpolate(self, _sim, target_angles: list,
                        duration: float = 3.0, steps: int = 60) -> bool:
        """
        Interpolación suave con easing cúbico. Ejecutado en worker.
        Se cancela si _cancel_interpolation está activo (nuevo comando llegó).
        """
        if not self.connected or not self._sim:
            return False

        # Clamp de límites
        clamped = []
        for i, tgt in enumerate(target_angles):
            if i < len(config.JOINT_LIMITS_6DOF):
                lo, hi = config.JOINT_LIMITS_6DOF[i]
                tgt = max(lo, min(hi, tgt))
            clamped.append(tgt)

        try:
            self._is_moving = True
            starts = self._read_joints()
            dt = duration / steps

            for step in range(steps):
                # ── Verificar cancelación en cada paso ──────────────────
                if self._cancel_interpolation.is_set():
                    print("[Coppelia] Interpolación cancelada por nuevo comando.")
                    return False

                alpha = (step + 1) / steps
                t = alpha * alpha * (3 - 2 * alpha)  # ease in-out cúbico
                for joint, start, target in zip(self._joint_handles, starts, clamped):
                    self._sim.setJointTargetPosition(
                        joint, float(start + (target - start) * t)
                    )
                time.sleep(dt)

            self._read_joints()  # actualizar cache al finalizar
            return True

        except Exception as e:
            print(f"[Coppelia] Error en interpolación: {e}")
            return False
        finally:
            self._is_moving = False

    def _do_gripper(self, _sim, close: bool, wait: float = 0.3) -> None:
        """Acción de gripper. Ejecutado en worker (ZMQ seguro)."""
        if not self.connected or not self._sim or not self._gripper_signal:
            return
        try:
            if close:
                self._sim.setInt32Signal(self._gripper_signal, 1)
            else:
                self._sim.clearInt32Signal(self._gripper_signal)
            self.gripper_closed = close
            if wait > 0:
                time.sleep(wait)
        except Exception as e:
            print(f"[Coppelia] Error gripper: {e}")

    def _do_move_home(self, _sim, duration: float = 2.0) -> bool:
        print("[Coppelia] → HOME")
        target  = config.PRESET_POSITIONS_6DOF["HOME"]
        success = self._do_interpolate(None, target, duration=duration)
        if success:
            self.current_pose = "HOME"
        return success

    def _do_move_zone(self, _sim, zone: str, duration: float = 3.0) -> bool:
        if zone not in config.PRESET_POSITIONS_6DOF:
            print(f"[Coppelia] Zona '{zone}' no configurada.")
            return False
        print(f"[Coppelia] → {zone}")
        target  = config.PRESET_POSITIONS_6DOF[zone]
        success = self._do_interpolate(None, target, duration=duration)
        if success:
            self.current_pose = zone
        return success

    def _do_stop(self, _sim) -> None:
        if not self.connected or not self._sim:
            return
        print("[Coppelia] STOP — manteniendo posición.")
        current = self._read_joints()
        for joint, pos in zip(self._joint_handles, current):
            self._sim.setJointTargetPosition(joint, float(pos))

    def _do_adjust_joints(self, _sim, deltas: list, duration: float = 0.2) -> bool:
        if not self.connected or not self._sim:
            return False
        current = self._read_joints()
        target = list(current)
        for i, delta in enumerate(deltas):
            if i < len(target):
                target[i] += delta
        return self._do_interpolate(None, target, duration=duration)

    # ═══════════════════════════════════════════════════════════════════════
    # API PÚBLICA — thread-safe (encolan en _zmq_worker)
    # ═══════════════════════════════════════════════════════════════════════

    def move_home(self, duration: float = 2.0) -> bool:
        return self._enqueue(self._do_move_home, duration=duration,
                             blocking=True, is_movement=True)

    def move_to_zone(self, zone_name: str, duration: float = 3.0) -> bool:
        zone = zone_name.upper()
        return self._enqueue(self._do_move_zone, zone, duration=duration,
                             blocking=True, is_movement=True)

    def adjust_joints(self, deltas: list, duration: float = 0.2) -> bool:
        return self._enqueue(self._do_adjust_joints, deltas, duration=duration,
                             blocking=False, is_movement=True)

    def stop(self):
        # Flush + encolar stop inmediato
        self._enqueue(self._do_stop, is_movement=True)

    def open_gripper(self) -> bool:
        # No-bloqueante, sin wait largo
        self._enqueue(self._do_gripper, False, 0.15)
        return True

    def close_gripper(self) -> bool:
        self._enqueue(self._do_gripper, True, 0.15)
        return True

    def open_gripper_sync(self, wait: float = 0.8) -> bool:
        """Versión bloqueante para secuencias autónomas."""
        self._enqueue(self._do_gripper, False, wait, blocking=True)
        return True

    def close_gripper_sync(self, wait: float = 0.8) -> bool:
        self._enqueue(self._do_gripper, True, wait, blocking=True)
        return True

    # ── Pick & Place ───────────────────────────────────────────────────────

    def pick_object(self, zone_name: str) -> bool:
        return self._enqueue(self._do_pick, zone_name, blocking=True)

    def _do_pick(self, _sim, zone_name: str) -> bool:
        print(f"[Coppelia] PICK desde '{zone_name}'")
        if not self._do_move_zone(None, zone_name, duration=2.5): return False
        self._do_gripper(None, False, 0.8)

        current = self._read_joints()
        lower   = list(current)
        lower[1] -= math.radians(10)
        lower[2] -= math.radians(10)
        if not self._do_interpolate(None, lower, duration=1.0): return False

        self._do_gripper(None, True, 0.8)
        if not self._do_move_zone(None, zone_name, duration=1.5): return False
        return True

    def drop_object(self, zone_name: str) -> bool:
        return self._enqueue(self._do_drop, zone_name, blocking=True)

    def _do_drop(self, _sim, zone_name: str) -> bool:
        print(f"[Coppelia] DROP en '{zone_name}'")
        if not self._do_move_zone(None, zone_name, duration=2.5): return False

        current = self._read_joints()
        lower   = list(current)
        lower[1] -= math.radians(8)
        if not self._do_interpolate(None, lower, duration=1.0): return False

        self._do_gripper(None, False, 0.8)
        self._do_move_zone(None, zone_name, duration=1.5)
        self._do_move_home(None, duration=2.0)
        return True

    # ═══════════════════════════════════════════════════════════════════════
    # TELEMETRÍA (solo variables cacheadas — NUNCA toca ZMQ)
    # ═══════════════════════════════════════════════════════════════════════

    def get_state(self) -> dict:
        """
        Seguro para llamar desde CUALQUIER hilo.
        Lee solo variables Python; nunca llama a self._sim.*
        """
        return {
            "adapter":         "CoppeliaSim",
            "connected":       self.connected,
            "joint_positions": list(self._cached_joints),
            "gripper_closed":  self.gripper_closed,
            "current_pose":    self.current_pose,
            "is_moving":       self._is_moving,
        }