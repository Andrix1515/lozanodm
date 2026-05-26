from coppeliasim_zmqremoteapi_client import RemoteAPIClient
import time
import math

def main():
    print("==================================================")
    print("  Simulacion Completa: NiryoOne + Gripper Dinamico ")
    print("==================================================")

    # 1. Conectar con CoppeliaSim
    try:
        client = RemoteAPIClient()
        sim = client.getObject('sim')
        print("[OK] Conectado a CoppeliaSim con exito.")
    except Exception as e:
        print(f"[ERROR] No se pudo conectar a CoppeliaSim: {e}")
        return

    # 2. Obtener los 6 joints del brazo
    print("\n=== Obteniendo los joints del brazo ===")
    joint_names = config.JOINT_PATHS
    
    joint_handles = []
    for name in joint_names:
        try:
            joint = sim.getObject(name)
            joint_handles.append(joint)
            print(f"  [OK] Joint encontrado: {name}")
        except Exception as e:
            print(f"  [ERROR] No se encontro {name}: {e}")

    if len(joint_handles) < 6:
        print("\n[ERROR] No se encontraron los 6 joints principales del brazo.")
        return

    # 3. Detectar dinamicamente la senal de la pinza (Gripper)
    print("\n=== Detectando Gripper dinamicamente ===")
    gripper_signal = None
    try:
        connection_handle = sim.getObject('/NiryoOne/connection')
        gripper_child = sim.getObjectChild(connection_handle, 0)
        
        if gripper_child != -1:
            gripper_alias = sim.getObjectAlias(gripper_child, 4) # 4 = alias corto sin ruta
            gripper_signal = f"{gripper_alias}_close"
            print(f"  [OK] Gripper acoplado detectado!: {gripper_alias}")
            print(f"  [OK] Senal de control resuelta: '{gripper_signal}'")
        else:
            print("  [WARN] No se detecto ninguna pinza acoplada fisicamente en '/NiryoOne/connection'.")
            print("  El control de garra estara deshabilitado durante esta ejecucion.")
    except Exception as e:
        print(f"  [ERROR] Error al buscar el gripper: {e}")
        print("  El control de garra estara deshabilitado.")

    # --- Funciones de control de movimiento ---

    def get_joint_positions():
        return [sim.getJointPosition(joint) for joint in joint_handles]

    def move_to(target_angles, duration=3.0, steps=60):
        start_angles = get_joint_positions()
        for step in range(steps):
            alpha = (step + 1) / steps
            for joint, start, end in zip(joint_handles, start_angles, target_angles):
                sim.setJointTargetPosition(joint, start + (end - start) * alpha)
            time.sleep(duration / steps)

    def control_gripper(close_gripper):
        """
        Controla la apertura o cierre del gripper mediante señales Int32.
        close_gripper = True -> Cierra la pinza (señal = 1)
        close_gripper = False -> Abre la pinza (elimina la señal)
        """
        if not gripper_signal:
            print("  [Gripper] Control deshabilitado (no se encontro la senal).")
            return
            
        try:
            if close_gripper:
                print(f"  [Gripper] Cerrando pinza (Enviando senal '{gripper_signal}' = 1)...")
                sim.setInt32Signal(gripper_signal, 1)
            else:
                print(f"  [Gripper] Abriendo pinza (Limpiando senal '{gripper_signal}')...")
                sim.clearInt32Signal(gripper_signal)
        except Exception as e:
            print(f"  [Gripper] Error al controlar la pinza: {e}")

    # --- Ejecucion de la simulacion ---
    print("\n=== Iniciando Simulacion ===")
    sim.startSimulation()

    try:
        # 1. Asegurar que la pinza empiece abierta
        control_gripper(close_gripper=False)
        time.sleep(1.0)

        # 2. Mover a posicion de trabajo elevada
        print("\nMoviendo a posicion de trabajo...")
        working_pose = [
            30 * math.pi / 180,
            -45 * math.pi / 180,
            20 * math.pi / 180,
            -10 * math.pi / 180,
            45 * math.pi / 180,
            10 * math.pi / 180,
        ]
        move_to(working_pose, duration=3.0)

        # 3. Extender y bajar ligeramente hacia el "objeto"
        print("\nExtender y bajar hacia el objeto...")
        reach_pose = [
            40 * math.pi / 180,
            -55 * math.pi / 180,
            10 * math.pi / 180,
            -20 * math.pi / 180,
            40 * math.pi / 180,
            15 * math.pi / 180,
        ]
        move_to(reach_pose, duration=2.5)
        time.sleep(0.5)

        # 4. Cerrar el gripper para "sujetar" el objeto
        print("\nObjetivo alcanzado!")
        control_gripper(close_gripper=True)
        time.sleep(2.0) # Esperar a que se cierre físicamente

        # 5. Elevar el brazo con el objeto sujetado
        print("\nElevando y rotando con el objeto...")
        elevated_pose = [
            20 * math.pi / 180,
            -35 * math.pi / 180,
            35 * math.pi / 180,
            -5 * math.pi / 180,
            50 * math.pi / 180,
            -20 * math.pi / 180,
        ]
        move_to(elevated_pose, duration=3.0)
        time.sleep(0.5)

        # 6. Trasladar el brazo a la posicion final de descarga
        print("\nMoviendo a posicion de descarga...")
        final_pose = [
            0 * math.pi / 180,
            -40 * math.pi / 180,
            25 * math.pi / 180,
            -15 * math.pi / 180,
            30 * math.pi / 180,
            5 * math.pi / 180,
        ]
        move_to(final_pose, duration=3.0)
        time.sleep(0.5)

        # 7. Abrir el gripper para "soltar" el objeto
        print("\nSoltando el objeto...")
        control_gripper(close_gripper=False)
        time.sleep(2.0) # Esperar a que se abra físicamente

        # 8. Volver a la posicion neutra final
        print("\nVolviendo a posicion inicial (reposo)...")
        neutral_pose = [0, 0, 0, 0, 0, 0]
        move_to(neutral_pose, duration=3.5)

        print("\n[OK] Simulacion de pick & place completada exitosamente!")

    except Exception as e:
        print(f"\n[ERROR] Ocurrio un problema durante la simulacion: {e}")

    finally:
        # Detener la simulación al finalizar
        time.sleep(1.0)
        sim.stopSimulation()
        print("Simulacion finalizada y detenida.")

if __name__ == '__main__':
    main()
