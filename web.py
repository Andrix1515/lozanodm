import time
from flask import Flask, jsonify, render_template, request
from robot.coppelia import NiryoOneRobot

app = Flask(__name__, static_folder="static", template_folder="templates")
robot = NiryoOneRobot()


def ensure_robot_connection() -> tuple[bool, str]:
    if robot.connected:
        return True, ""

    connected = robot.connect()
    if not connected:
        return False, robot.last_error or "No se pudo conectar al robot."
    return True, ""


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status", methods=["GET"])
def status():
    connected, error = ensure_robot_connection()
    if not connected:
        return jsonify({"connected": False, "error": error}), 500

    positions = robot.get_joint_positions()
    return jsonify({
        "connected": True,
        "joint_positions": positions,
        "gripper_closed": robot.gripper_closed,
        "last_error": robot.last_error,
    })


@app.route("/api/joints", methods=["POST"])
def set_joints():
    data = request.get_json(silent=True) or {}
    angles = data.get("angles")
    duration = float(data.get("duration", 1.0))

    if not isinstance(angles, list) or len(angles) != 6:
        return jsonify({"error": "Se requieren 6 ángulos en radianes."}), 400

    connected, error = ensure_robot_connection()
    if not connected:
        return jsonify({"error": error}), 500

    if robot.move_to([float(v) for v in angles], duration=duration):
        return jsonify({"success": True})
    return jsonify({"error": robot.last_error or "No se pudo mover el robot."}), 500


@app.route("/api/adjust", methods=["POST"])
def adjust_joints():
    data = request.get_json(silent=True) or {}
    deltas = data.get("deltas")

    if not isinstance(deltas, list) or len(deltas) != 6:
        return jsonify({"error": "Se requieren 6 deltas en radianes."}), 400

    connected, error = ensure_robot_connection()
    if not connected:
        return jsonify({"error": error}), 500

    if robot.adjust_joints([float(v) for v in deltas]):
        return jsonify({"success": True})
    return jsonify({"error": robot.last_error or "No se pudo ajustar las articulaciones."}), 500


@app.route("/api/gripper", methods=["POST"])
def gripper():
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    if action not in ("open", "close"):
        return jsonify({"error": "Acción inválida. Use 'open' o 'close'."}), 400

    connected, error = ensure_robot_connection()
    if not connected:
        return jsonify({"error": error}), 500

    success = robot.open_gripper() if action == "open" else robot.close_gripper()
    if success:
        return jsonify({"success": True, "gripper_closed": robot.gripper_closed})
    return jsonify({"error": robot.last_error or "No se pudo cambiar la pinza."}), 500


@app.route("/api/home", methods=["POST"])
def home():
    connected, error = ensure_robot_connection()
    if not connected:
        return jsonify({"error": error}), 500

    if robot.go_home():
        return jsonify({"success": True})
    return jsonify({"error": robot.last_error or "No se pudo ir a HOME."}), 500


if __name__ == "__main__":
    print("Iniciando servidor web para control del robot...")
    connected, error = ensure_robot_connection()
    if not connected:
        print("ERROR:", error)
        raise SystemExit(1)

    app.run(host="0.0.0.0", port=5000, debug=False)
