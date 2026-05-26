import json
import math
import os
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

import cv2
from flask import Flask, Response, jsonify, render_template, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging
from logging.handlers import RotatingFileHandler

ROOT_DIR = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT_DIR / "logs"
MACROS_DIR = ROOT_DIR / "macros"

LOG_DIR.mkdir(parents=True, exist_ok=True)
MACROS_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, template_folder="templates")
CORS(app)
limiter = Limiter(key_func=get_remote_address, app=app, default_limits=["200 per minute"])

logger = logging.getLogger("robot_api")

if not logger.handlers:
    level_name = os.environ.get("FLASK_ENV", "production").lower()
    log_level = logging.DEBUG if level_name == "development" else logging.INFO
    logger.setLevel(log_level)
    handler = RotatingFileHandler(
        LOG_DIR / "robot.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False


class CommandLogger:
    """Registro circular de comandos ejecutados."""

    def __init__(self, maxlen: int = 200):
        self._entries: Deque[Dict[str, Any]] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def log(
        self,
        action: str,
        result: str,
        duration_ms: int,
        **kwargs: Any,
    ) -> None:
        entry: Dict[str, Any] = {
            "ts": datetime.now().strftime("%H:%M:%S"),
            "action": action,
            "result": result,
            "duration_ms": duration_ms,
        }
        entry.update(kwargs)
        with self._lock:
            self._entries.append(entry)
        logger.debug("Command logged: %s", entry)

    def get(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._entries)[-limit:]


class ServerState:
    """Estado compartido del servidor para la API y el dashboard."""

    def __init__(self):
        self._lock = threading.Lock()
        self.start_time = time.time()
        self.connected = False
        self.mode = "GESTURE"
        self.gesture = ""
        self.gripper = "OPEN"
        self.fps = 0.0
        self.joints = {f"joint{i}": 0.0 for i in range(1, 7)}
        self.last_command = ""
        self.recording = False
        self.recorded_actions: List[Dict[str, Any]] = []
        self.camera_lock = threading.Lock()
        self.frame = None

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            uptime = int(time.time() - self.start_time)
            return {
                "connected": self.connected,
                "mode": self.mode,
                "gesture": self.gesture,
                "gripper": self.gripper,
                "fps": self.fps,
                "joints": dict(self.joints),
                "last_command": self.last_command,
                "uptime_seconds": uptime,
            }

    def update(self, **kwargs: Any) -> None:
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)

    def set_frame(self, frame: Any) -> None:
        with self.camera_lock:
            self.frame = frame.copy() if frame is not None else None

    def get_frame(self) -> Optional[Any]:
        with self.camera_lock:
            return self.frame.copy() if self.frame is not None else None


def _ensure_json_request() -> Dict[str, Any]:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("Se requiere JSON válido en el cuerpo de la solicitud.")
    return data


def _execute_robot_command(robot: Any, command: Dict[str, Any]) -> Dict[str, Any]:
    action = command.get("action")
    if not isinstance(action, str):
        raise ValueError("Campo 'action' requerido.")

    start = time.perf_counter()
    result = "ok"
    details: Dict[str, Any] = {}

    if action == "move_to":
        angles = command.get("angles")
        duration = float(command.get("duration", 1.0))
        if not isinstance(angles, list) or len(angles) != 6:
            raise ValueError("move_to requiere una lista de 6 ángulos.")
        success = robot.move_to([float(v) for v in angles], duration=duration)
        if not success:
            result = "error"
            details["error"] = getattr(robot, "last_error", "Error desconocido")

    elif action == "adjust":
        deltas = command.get("deltas")
        if not isinstance(deltas, list) or len(deltas) != 6:
            raise ValueError("adjust requiere una lista de 6 deltas.")
        success = robot.adjust_joints([float(v) for v in deltas])
        if not success:
            result = "error"
            details["error"] = getattr(robot, "last_error", "Error desconocido")

    elif action == "open_gripper":
        success = robot.open_gripper()
        if not success:
            result = "error"
            details["error"] = getattr(robot, "last_error", "Error desconocido")

    elif action == "close_gripper":
        success = robot.close_gripper()
        if not success:
            result = "error"
            details["error"] = getattr(robot, "last_error", "Error desconocido")

    elif action == "go_home":
        success = robot.go_home()
        if not success:
            result = "error"
            details["error"] = getattr(robot, "last_error", "Error desconocido")

    else:
        raise ValueError(f"Acción desconocida: {action}")

    duration_ms = int((time.perf_counter() - start) * 1000)
    return {"action": action, "result": result, "duration_ms": duration_ms, **details}


def _save_macro(name: str, actions: List[Dict[str, Any]]) -> None:
    macro_file = MACROS_DIR / f"{name}.json"
    payload = {
        "name": name,
        "saved_at": datetime.utcnow().isoformat() + "Z",
        "actions": actions,
    }
    with macro_file.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    logger.info("Macro %s guardada en %s", name, macro_file)


def _load_macro(name: str) -> Dict[str, Any]:
    macro_file = MACROS_DIR / f"{name}.json"
    if not macro_file.exists():
        raise FileNotFoundError(f"Macro no encontrada: {name}")
    with macro_file.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _play_macro(name: str, robot: Any) -> None:
    try:
        macro = _load_macro(name)
        for entry in macro.get("actions", []):
            if entry.get("action") == "wait":
                delay = float(entry.get("params", {}).get("seconds", 0.0))
                time.sleep(delay)
                continue
            _execute_robot_command(robot, entry)
            time.sleep(float(entry.get("params", {}).get("delay", 0.1)))
        logger.info("Macro %s reproducida con éxito.", name)
    except Exception as error:
        logger.exception("Error reproduciendo macro %s: %s", name, error)


server_state = ServerState()
command_logger = CommandLogger()
robot_controller: Optional[Any] = None


def register_robot(robot: Any) -> None:
    global robot_controller
    robot_controller = robot
    server_state.update(connected=bool(getattr(robot, "connected", False)))


def set_camera_frame(frame: Any) -> None:
    server_state.set_frame(frame)


def update_robot_status(
    connected: Optional[bool] = None,
    mode: Optional[str] = None,
    gesture: Optional[str] = None,
    gripper: Optional[str] = None,
    fps: Optional[float] = None,
    joints: Optional[Dict[str, float]] = None,
    last_command: Optional[str] = None,
) -> None:
    update_args: Dict[str, Any] = {}
    if connected is not None:
        update_args["connected"] = connected
    if mode is not None:
        update_args["mode"] = mode
    if gesture is not None:
        update_args["gesture"] = gesture
    if gripper is not None:
        update_args["gripper"] = gripper
    if fps is not None:
        update_args["fps"] = fps
    if joints is not None:
        update_args["joints"] = joints
    if last_command is not None:
        update_args["last_command"] = last_command
    server_state.update(**update_args)


def _generate_frames() -> bytes:
    while True:
        frame = server_state.get_frame()
        if frame is not None:
            resized = cv2.resize(frame, (640, 480))
            ret, jpeg = cv2.imencode(".jpg", resized, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if ret:
                yield b"--frame\r\n"
                yield b"Content-Type: image/jpeg\r\n\r\n"
                yield jpeg.tobytes()
                yield b"\r\n"
        time.sleep(0.03)


@app.route("/")
def dashboard() -> Any:
    return render_template("dashboard.html")


@app.route("/video_feed")
def video_feed() -> Response:
    return Response(
        _generate_frames(),
        mimetype="multipart/x-mixed-replace;boundary=frame",
    )


@app.route("/api/state", methods=["GET"])
def api_state() -> Any:
    state = server_state.snapshot()
    if robot_controller is not None:
        try:
            joint_radians = robot_controller.get_joint_positions()
            state["joints"] = {
                f"joint{i + 1}": math.degrees(value)
                for i, value in enumerate(joint_radians)
            }
        except Exception:
            pass
    return jsonify(state)


@app.route("/api/log", methods=["GET"])
def api_log() -> Any:
    limit = request.args.get("limit", "50")
    try:
        limit_value = max(1, min(200, int(limit)))
    except ValueError:
        limit_value = 50
    return jsonify(command_logger.get(limit_value))


@app.route("/api/command", methods=["POST"])
@limiter.limit("20 per second")
def api_command() -> Any:
    if robot_controller is None:
        return jsonify({"error": "Robot no inicializado"}), 500
    try:
        payload = _ensure_json_request()
        result = _execute_robot_command(robot_controller, payload)
        action = result.get("action", "unknown")
        server_state.update(last_command=action)
        command_logger.log(
            action=action,
            result=result.get("result", "error"),
            duration_ms=result.get("duration_ms", 0),
            zone=payload.get("zone"),
        )
        if server_state.recording:
            server_state.recorded_actions.append(payload)
        return jsonify(result)
    except ValueError as error:
        logger.warning("Comando inválido: %s", error)
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        logger.exception("Error al ejecutar comando: %s", error)
        return jsonify({"error": str(error)}), 500


@app.route("/api/macro/start_record", methods=["POST"])
def api_start_macro_record() -> Any:
    if server_state.recording:
        return jsonify({"error": "Ya se está grabando una macro."}), 400
    server_state.recorded_actions = []
    server_state.recording = True
    logger.info("Inicio de grabación de macro.")
    return jsonify({"recording": True})


@app.route("/api/macro/stop_record", methods=["POST"])
def api_stop_macro_record() -> Any:
    if not server_state.recording:
        return jsonify({"error": "No hay grabación en curso."}), 400
    payload = _ensure_json_request()
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "Se requiere el nombre de la macro."}), 400
    server_state.recording = False
    _save_macro(name, server_state.recorded_actions)
    server_state.recorded_actions = []
    return jsonify({"saved": name})


@app.route("/api/macros", methods=["GET"])
def api_list_macros() -> Any:
    files = sorted(MACROS_DIR.glob("*.json"))
    return jsonify([file.stem for file in files])


@app.route("/api/macro/play", methods=["POST"])
def api_play_macro() -> Any:
    if robot_controller is None:
        return jsonify({"error": "Robot no inicializado"}), 500
    payload = _ensure_json_request()
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "Se requiere el nombre de la macro."}), 400
    thread = threading.Thread(target=_play_macro, args=(name, robot_controller), daemon=True)
    thread.start()
    logger.info("Reproduciendo macro %s en segundo plano.", name)
    return jsonify({"playing": name})


if __name__ == "__main__":
    logger.info("Iniciando servidor Flask en api/server.py")
    app.run(host="0.0.0.0", port=5000, debug=False)
