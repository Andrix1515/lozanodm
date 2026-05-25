"""
Control del NiryoOne en CoppeliaSim con la mano:
  - Cuadrícula 3×3 en pantalla
  - Posición de la mano = joystick de articulaciones
  - Puño cerrado = gripper cerrado
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2

from robot.coppelia import NiryoOneRobot
from vision.hand_control import HandJoystickApp


def main():
    print("=" * 50)
    print("  NiryoOne — Control por mano (CoppeliaSim)")
    print("=" * 50)

    robot = NiryoOneRobot()
    if not robot.connect():
        print("\nPasos si falla la conexion:")
        print("  1. Abre CoppeliaSim")
        print("  2. Carga la escena con el modelo NiryoOne")
        print("  3. Ejecuta de nuevo: python main.py")
        print("  (Prueba que simulacion_completa.py funcione primero)")
        return

    app = HandJoystickApp(robot)
    if not app.start_camera():
        print("[ERROR] No se pudo abrir la cámara.")
        robot.disconnect()
        return

    print("\nVentana abierta. Coloca la mano sobre la cuadrícula 3×3.")
    print("  Puño cerrado  → cierra la pinza")
    print("  Mano abierta  → mueve el brazo según la celda")
    print("  [H] Home      [Q] Salir\n")

    try:
        while app.running:
            frame = app.process_frame()
            cv2.imshow(app.WINDOW_TITLE, frame)
            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), ord("Q")):
                break
            if key in (ord("h"), ord("H")) and robot.connected:
                robot.go_home()
                app.status = "Posición HOME"

    except KeyboardInterrupt:
        pass
    finally:
        app.stop()
        robot.disconnect()
        print("Programa finalizado.")


if __name__ == "__main__":
    main()
