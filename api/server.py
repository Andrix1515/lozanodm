"""
Flask REST API Server Layer.
Provides endpoints for remote control, system monitoring, and future web interface integration.
Runs inside a background daemon thread to maintain concurrent operations.
"""

from flask import Flask, jsonify, request
import threading
from control.actions import execute_autonomous_pick_and_place
import config
import logging

app = Flask(__name__)

# Mute standard Flask console log spam to keep terminal logs pristine
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Global variables shared with the orchestrator
_robot = None
_vision = None

def init_server(robot_adapter, vision_system):
    """
    Passes references of active robot and vision instances to the API endpoints.
    """
    global _robot, _vision
    _robot = robot_adapter
    _vision = vision_system

@app.route('/api/state', methods=['GET'])
def get_state():
    """
    Queries and returns active telemetry, including joint angles and active mode.
    """
    if not _robot:
        return jsonify({"error": "Robot adapter not initialized"}), 500
        
    state = _robot.get_state()
    vision_active = _vision.hand_detected if _vision else False
    current_mode = _vision.operational_mode if _vision else "API_MANUAL"
    current_gesture = _vision.current_gesture if _vision else "NONE"
    
    return jsonify({
        "status": "success",
        "robot": {
            "adapter": state.get("adapter"),
            "connected": state.get("connected"),
            "joint_positions": state.get("joint_positions"),
            "gripper_closed": state.get("gripper_closed"),
            "current_pose": state.get("current_pose")
        },
        "vision": {
            "hand_detected": vision_active,
            "current_mode": current_mode,
            "current_gesture": current_gesture
        }
    }), 200

@app.route('/api/mode', methods=['POST'])
def change_mode():
    """
    Switches active operational mode ('GESTURE', 'API_MANUAL', 'AUTONOMOUS').
    """
    if not _vision:
        return jsonify({"error": "Vision system not initialized"}), 500
        
    data = request.get_json() or {}
    mode = data.get("mode", "").upper()
    
    if mode not in ["GESTURE", "API_MANUAL", "AUTONOMOUS"]:
        return jsonify({"error": "Invalid mode. Use GESTURE, API_MANUAL, or AUTONOMOUS."}), 400
        
    _vision.operational_mode = mode
    _vision.status_msg = f"Mode switched to: {mode}"
    print(f"[WebAPI] Mode changed to {mode}")
    
    return jsonify({"status": "success", "mode": mode}), 200

@app.route('/api/command', methods=['POST'])
def send_command():
    """
    Triggers discrete high-level commands on the robotic arm.
    """
    if not _robot or not _vision:
        return jsonify({"error": "System not initialized"}), 500
        
    # Check connection
    state = _robot.get_state()
    if not state.get("connected"):
        return jsonify({"error": "Robot adapter is offline"}), 400

    data = request.get_json() or {}
    action = data.get("action", "").lower()
    
    # Check active mode; warn if running gesture control
    if _vision.operational_mode == "GESTURE" and action != "stop":
        return jsonify({"error": "Cannot trigger API commands while GESTURE mode is active. Switch to API_MANUAL."}), 403

    print(f"[WebAPI] REST Command received: '{action}'")
    _vision.status_msg = f"REST Command: {action}"

    try:
        if action == "move_home":
            # Run in thread so the API call doesn't hang the client
            threading.Thread(target=_robot.move_home, kwargs={"duration": 1.5}).start()
            return jsonify({"status": "success", "msg": "Home movement dispatched"}), 200
            
        elif action == "move_to_zone":
            zone = data.get("zone", "").upper()
            threading.Thread(target=_robot.move_to_zone, args=(zone,), kwargs={"duration": 2.0}).start()
            return jsonify({"status": "success", "msg": f"Move to {zone} dispatched"}), 200
            
        elif action == "open_gripper":
            threading.Thread(target=_robot.open_gripper).start()
            return jsonify({"status": "success", "msg": "Open gripper dispatched"}), 200
            
        elif action == "close_gripper":
            threading.Thread(target=_robot.close_gripper).start()
            return jsonify({"status": "success", "msg": "Close gripper dispatched"}), 200
            
        elif action == "pick_place":
            # Set mode to AUTONOMOUS to lock out gesture overrides
            _vision.operational_mode = "AUTONOMOUS"
            source = data.get("source", "LEFT").upper()
            target = data.get("target", "DROP_ZONE").upper()
            
            # Spawn the pick-and-place workflow
            def run_pick_place():
                execute_autonomous_pick_and_place(_robot, source, target)
                # Revert to API manual mode upon completion
                _vision.operational_mode = "API_MANUAL"
                _vision.status_msg = "Autonomous flow done"

            threading.Thread(target=run_pick_place).start()
            return jsonify({"status": "success", "msg": f"Autonomous pick-and-place ({source} -> {target}) started"}), 200
            
        elif action == "stop":
            _robot.stop()
            # If in autonomous flow, abort and set back to API manual
            if _vision.operational_mode == "AUTONOMOUS":
                _vision.operational_mode = "API_MANUAL"
            return jsonify({"status": "success", "msg": "Robot stop triggered"}), 200
            
        else:
            return jsonify({"error": f"Unknown action: '{action}'"}), 400

    except Exception as e:
        return jsonify({"error": f"Internal error during execution: {e}"}), 500

def run_api_server():
    """
    Launches the Flask development server on config port.
    """
    print(f"[WebAPI] Starting Flask REST server on http://{config.API_HOST}:{config.API_PORT} ...")
    app.run(host=config.API_HOST, port=config.API_PORT, debug=False, threaded=True)
