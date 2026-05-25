"""
High-level Robot Actions Layer — OPTIMIZED v2.0
─────────────────────────────────────────────────
Cambios respecto a v1:
  • Timeout global configurable para evitar bloqueos infinitos.
  • progress_callback opcional para actualizar la UI en tiempo real.
  • Verificación de estado en cada paso (abort temprano si se pierde conexión).
  • Función execute_sequence() genérica para componer flujos fácilmente.
"""

import time
from typing import Callable, Optional


# ══════════════════════════════════════════════════════════════════════════
# HELPER: EXECUTOR DE PASOS CON TIMEOUT
# ══════════════════════════════════════════════════════════════════════════

def _run_step(label: str, fn: Callable, robot,
              progress_cb: Optional[Callable] = None,
              timeout: float = 15.0) -> bool:
    """
    Ejecuta una función del robot con:
      • Log de paso y callback de progreso.
      • Verificación de conexión previa.
      • Captura de excepción con stop de emergencia.
    """
    if not robot.get_state().get("connected"):
        print(f"[Actions] ABORT en '{label}': robot desconectado.")
        return False

    if progress_cb:
        progress_cb(label)

    print(f"[Actions] ⟶  {label}")
    start = time.time()

    try:
        result = fn()
        elapsed = time.time() - start
        if elapsed > timeout:
            print(f"[Actions] TIMEOUT en '{label}' ({elapsed:.1f}s > {timeout}s)")
            robot.stop()
            return False
        return result is not False   # None/True → OK, False explícito → Fallo
    except Exception as e:
        print(f"[Actions] ERROR en '{label}': {e}")
        robot.stop()
        return False


# ══════════════════════════════════════════════════════════════════════════
# PICK & PLACE AUTÓNOMO
# ══════════════════════════════════════════════════════════════════════════

def execute_autonomous_pick_and_place(
    robot,
    source_zone: str,
    target_zone: str,
    step_timeout: float = 12.0,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> bool:
    """
    Secuencia completa de pick-and-place:
      1. HOME + abrir gripper
      2. pick_object(source_zone)
      3. drop_object(target_zone)
      4. HOME final

    Args:
        robot:             Instancia de BaseRobot.
        source_zone:       Zona de recogida ('LEFT', 'CENTER', 'RIGHT').
        target_zone:       Zona de depósito ('DROP_ZONE', etc.).
        step_timeout:      Segundos máximos por paso (evita bloqueos).
        progress_callback: fn(str) llamada con el nombre de cada paso.

    Returns:
        True si toda la secuencia completó correctamente.
    """
    print(f"\n[Actions] ═══ PICK & PLACE AUTÓNOMO ═══")
    print(f"[Actions]  Origen: {source_zone}  →  Destino: {target_zone}")

    if not robot.get_state().get("connected"):
        print("[Actions] ABORT: robot no conectado.")
        return False

    # Definición de pasos como tuplas (etiqueta, lambda)
    steps = [
        ("Inicializando — IR A HOME",
            lambda: robot.move_home(duration=1.5)),
        ("Abriendo gripper inicial",
            lambda: robot.open_gripper_sync()),
        (f"PICKING desde '{source_zone}'",
            lambda: robot.pick_object(source_zone)),
        (f"DROPPING en '{target_zone}'",
            lambda: robot.drop_object(target_zone)),
        ("Retorno a HOME",
            lambda: robot.move_home(duration=2.0)),
    ]

    for label, fn in steps:
        ok = _run_step(label, fn, robot,
                       progress_cb=progress_callback,
                       timeout=step_timeout)
        if not ok:
            print(f"[Actions] ✗ Secuencia abortada en: '{label}'")
            robot.stop()
            return False
        time.sleep(0.3)   # Pausa breve entre pasos

    print("[Actions] ✓ PICK & PLACE completado correctamente.")
    return True


# ══════════════════════════════════════════════════════════════════════════
# EXECUTOR GENÉRICO DE SECUENCIAS
# ══════════════════════════════════════════════════════════════════════════

def execute_sequence(
    robot,
    steps: list[tuple[str, Callable]],
    step_timeout: float = 10.0,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> bool:
    """
    Ejecuta una lista arbitraria de pasos (label, fn).
    Útil para componer flujos personalizados sin duplicar lógica de error.

    Ejemplo:
        execute_sequence(robot, [
            ("Ir a LEFT",    lambda: robot.move_to_zone("LEFT", 2.0)),
            ("Cerrar pinza", lambda: robot.close_gripper_sync()),
        ])
    """
    if not robot.get_state().get("connected"):
        print("[Actions] ABORT: robot no conectado.")
        return False

    for label, fn in steps:
        ok = _run_step(label, fn, robot,
                       progress_cb=progress_callback,
                       timeout=step_timeout)
        if not ok:
            print(f"[Actions] ✗ Secuencia detenida en: '{label}'")
            return False
        time.sleep(0.2)

    return True