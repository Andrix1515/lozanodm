"""
Master Entry Point and Threading Orchestrator.
Initializes the active robot adapter, launches the background API server, and runs the camera loop.
"""

import sys
import os
import time
import threading
import cv2

# Ensure project base path is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from robot.coppelia_robot import CoppeliaRobotAdapter
from robot.arduino_robot import ArduinoRobotAdapter
from ai.vision import VisionSystem
from api.server import init_server, run_api_server
from control.actions import execute_autonomous_pick_and_place

def print_welcome_banner(adapter_name):
    print("==================================================================")
    print("      MODULAR AI ROBOTIC ARM FRAMEWORK - INITIALIZATION           ")
    print("==================================================================")
    print(f"  [System] Target Adapter Type  : {adapter_name.upper()}")
    print(f"  [System] Camera Resolution    : {config.FRAME_WIDTH}x{config.FRAME_HEIGHT}")
    print(f"  [System] Signal Smooth Alpha  : {config.SMOOTHING_ALPHA}")
    print(f"  [System] REST Server Endpoint : http://{config.API_HOST}:{config.API_PORT}")
    print("==================================================================")

def main():
    # 1. Resolve and load the configured Robot Adapter
    adapter_type = config.ROBOT_ADAPTER.lower()
    robot = None
    
    if adapter_type == "coppelia":
        robot = CoppeliaRobotAdapter()
    elif adapter_type == "arduino":
        robot = ArduinoRobotAdapter()
    else:
        print(f"[System] ERROR: Unknown adapter type: '{config.ROBOT_ADAPTER}'. Falling back to Mock Arduino.")
        robot = ArduinoRobotAdapter()

    print_welcome_banner(robot.__class__.__name__)

    # 2. Establish connection to simulation or microcontroller
    print("[System] Connecting to robot adapter...")
    connection_success = robot.connect()
    
    if not connection_success:
        print("[System] WARNING: Robot connection failed. Proceeding in OFFLINE/DEMO mode.")
        print("[System] (Vision loop and Web API will remain fully active for analysis)")

    # 3. Instantiate the AI Vision layer
    vision = VisionSystem(robot)

    # 4. Bind references and start background REST API thread
    init_server(robot, vision)
    server_thread = threading.Thread(target=run_api_server, daemon=True)
    server_thread.start()
    print("[System] Flask Server spawned in background thread successfully.")

    # 5. Initialize camera
    if not vision.start_camera():
        print("[System] CRITICAL ERROR: Failed to open camera device. Aborting main process.")
        robot.disconnect()
        return

    print("\n[System] HUD Window opened. Focus on the CV2 window to use keyboard hotkeys.")
    print("  Hotkey [C] - Calibrate hand center (Perform with hand in natural pose)")
    print("  Hotkey [M] - Switch Mode (GESTURE -> API_MANUAL -> GESTURE)")
    print("  Hotkey [A] - Trigger Test Autonomous Pick & Place (LEFT -> DROP_ZONE)")
    print("  Hotkey [H] - Move Robot Home")
    print("  Hotkey [S] - Immediate Stop / Grip open")
    print("  Hotkey [Q] - Safe Shutdown & Quit\n")

    # 6. High-Frequency OpenCV GUI Thread Loop
    try:
        while vision.running:
            hud_frame = vision.process_frame()
            
            # Show aesthetic overlay
            cv2.imshow("Modular AI Robotic Arm System - Vision HUD", hud_frame)
            
            # Listen to keyboard inputs
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q') or key == ord('Q'):
                print("[System] Safe shutdown requested via key command [Q].")
                vision.status_msg = "Shutting down..."
                break
                
            elif key == ord('c') or key == ord('C'):
                # Calibrate hand gesture center
                vision.calibrate_hand()
                
            elif key == ord('m') or key == ord('M'):
                # Rotate modes: GESTURE -> API_MANUAL -> GESTURE
                if vision.operational_mode == "GESTURE":
                    vision.operational_mode = "API_MANUAL"
                    vision.status_msg = "Switched to API_MANUAL mode"
                else:
                    vision.operational_mode = "GESTURE"
                    vision.status_msg = "Switched to GESTURE mode"
                print(f"[System] Mode manually changed to: {vision.operational_mode}")

            elif key == ord('a') or key == ord('A'):
                # Trigger quick autonomous pick and place workflow
                if robot.get_state().get("connected"):
                    vision.operational_mode = "AUTONOMOUS"
                    vision.status_msg = "Auto Pick-and-Place starting..."
                    
                    def quick_auto_thread():
                        execute_autonomous_pick_and_place(robot, "LEFT", "DROP_ZONE")
                        vision.operational_mode = "API_MANUAL"
                        vision.status_msg = "Auto action finished"
                        
                    threading.Thread(target=quick_auto_thread).start()
                else:
                    vision.status_msg = "Auto failed: Robot is offline"

            elif key == ord('h') or key == ord('H'):
                # Send home
                if robot.get_state().get("connected"):
                    vision.status_msg = "Homeward movement fired"
                    threading.Thread(target=robot.move_home).start()
                    
            elif key == ord('s') or key == ord('S'):
                # Trigger stop
                if robot.get_state().get("connected"):
                    robot.stop()
                    robot.open_gripper()
                    vision.status_msg = "IMMEDIATE STOP TRIGGERED"
                    if vision.operational_mode == "AUTONOMOUS":
                        vision.operational_mode = "API_MANUAL"

    except KeyboardInterrupt:
        print("[System] Keyboard interrupt received.")
    finally:
        # 7. Safe Resource Cleanup
        print("[System] Starting cleanup sequence...")
        vision.stop_camera()
        robot.disconnect()
        print("[System] Safe shutdown complete. Farewell.")


if __name__ == "__main__":
    main()

