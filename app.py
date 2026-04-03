from __future__ import annotations

import argparse
import threading
import time
from pathlib import Path
from typing import Any, Dict

import cv2
from flask import Flask, Response, jsonify, request

from config import Config
from dashboard import init_dashboard
from geotagger import google_maps_ready
from reporter import create_and_save_report
from storage import (
    get_all_potholes,
    get_counts,
    get_db_status,
    get_hourly_counts,
    get_status_counts,
    get_zone_counts,
    mark_as_fixed,
    seed_dummy_data,
)
from yolo_detect import get_model_status


DEFAULT_LAT = 12.9716
DEFAULT_LNG = 77.5946


class LiveCameraManager:
    """Run live camera detection in a background thread owned by app.py."""

    def __init__(self) -> None:
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.frame_lock = threading.Lock()
        self.running = False
        self.source = "0"
        self.frames_seen = 0
        self.frames_processed = 0
        self.detections = 0
        self.last_report_id = ""
        self.latest_frame_bytes = b""

    def _open_source(self, source: str) -> cv2.VideoCapture:
        """Open a webcam index or a video file path."""
        try:
            capture_source: int | str = int(source)
        except ValueError:
            capture_source = source
        return cv2.VideoCapture(capture_source)

    def _loop(self, source: str) -> None:
        """Process the live feed and save detections."""
        self.source = source
        self.frames_seen = 0
        self.frames_processed = 0
        self.detections = 0
        self.last_report_id = ""
        capture = self._open_source(source)
        started_at = time.time()

        if not capture.isOpened():
            print(f"[CAMERA][ERROR] Unable to open source: {source}")
            self.running = False
            return

        self.running = True
        while not self.stop_event.is_set():
            success, frame = capture.read()
            if not success or frame is None:
                print("[CAMERA] End of stream or unable to read frame.")
                break

            annotated_frame = frame.copy()
            if self.frames_seen % Config.DETECTION_INTERVAL == 0:
                from yolo_detect import detect_frame

                self.frames_processed += 1
                result = detect_frame(frame)
                annotated_frame = result["annotated_frame"]
                if result["detected"]:
                    self.detections += 1
                    report = create_and_save_report(
                        lat=DEFAULT_LAT,
                        lng=DEFAULT_LNG,
                        image_path=result["image_path"],
                        severity=result["severity"],
                        confidence=result["confidence"],
                    )
                    self.last_report_id = str(report.get("_id", ""))
                    print(f"[CAMERA][DETECTION] Saved report {self.last_report_id} at {report['address']}")

            success_encode, buffer = cv2.imencode(".jpg", annotated_frame)
            if success_encode:
                with self.frame_lock:
                    self.latest_frame_bytes = buffer.tobytes()

            if time.time() - started_at >= 30:
                print(
                    f"[CAMERA][STATS] frames={self.frames_seen + 1} processed={self.frames_processed} detections={self.detections}"
                )
                started_at = time.time()

            self.frames_seen += 1

        capture.release()
        self.running = False
        self.stop_event.clear()

    def start(self, source: str = "0") -> bool:
        """Start the live camera loop if it is not already running."""
        if self.running:
            return False
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._loop, args=(source,), daemon=True)
        self.thread.start()
        return True

    def stop(self) -> bool:
        """Stop the live camera loop."""
        if not self.running:
            return False
        self.stop_event.set()
        return True

    def status(self) -> Dict[str, Any]:
        """Return the current live camera status."""
        return {
            "running": self.running,
            "source": self.source,
            "frames_seen": self.frames_seen,
            "frames_processed": self.frames_processed,
            "detections": self.detections,
            "last_report_id": self.last_report_id,
        }

    def get_latest_frame(self) -> bytes:
        """Return the latest encoded frame bytes."""
        with self.frame_lock:
            return self.latest_frame_bytes


camera_manager = LiveCameraManager()


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = Config.FLASK_SECRET_KEY
    init_dashboard(app)

    @app.post("/api/report")
    def api_report() -> Any:
        """Create and store a pothole report from API input."""
        payload: Dict[str, Any] = request.get_json(silent=True) or {}
        required_fields = ["lat", "lng", "image_path"]
        missing = [field for field in required_fields if field not in payload]
        if missing:
            return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

        report = create_and_save_report(
            lat=float(payload["lat"]),
            lng=float(payload["lng"]),
            image_path=str(payload["image_path"]),
            severity=str(payload.get("severity", "Medium")),
            confidence=float(payload.get("confidence", 0.0)),
        )
        return jsonify({"status": "saved", "report": report}), 201

    @app.get("/api/potholes")
    def api_potholes() -> Any:
        """Return the latest pothole reports."""
        limit = request.args.get("limit", default=50, type=int)
        potholes = get_all_potholes(limit=limit or 50)
        return jsonify({"count": len(potholes), "potholes": potholes})

    @app.get("/api/stats")
    def api_stats() -> Any:
        """Return aggregate pothole statistics for the dashboard."""
        counts = get_counts()
        total = counts.get("total", 0)
        fixed = counts.get("fixed", 0)
        fix_rate = round((fixed / total) * 100, 2) if total else 0.0
        payload = {
            **counts,
            "fix_rate": fix_rate,
            "hourly": get_hourly_counts(),
            "zones": get_zone_counts(),
            "status_counts": get_status_counts(),
        }
        return jsonify(payload)

    @app.post("/api/fix/<pothole_id>")
    def api_fix(pothole_id: str) -> Any:
        """Mark a pothole as fixed."""
        updated = mark_as_fixed(pothole_id)
        if not updated:
            return jsonify({"status": "not_found"}), 404
        return jsonify({"status": "updated"})

    @app.get("/api/hotspots")
    def api_hotspots() -> Any:
        """Return hotspot zones ordered by report count."""
        zones = get_zone_counts()
        return jsonify(zones[:10])

    @app.get("/api/health")
    def api_health() -> Any:
        """Return health information for the full system."""
        return jsonify(
            {
                "status": "ok",
                "db": get_db_status(),
                "model": "loaded" if get_model_status()["loaded"] else "not_loaded",
                "google_maps": "ready" if google_maps_ready() else "fallback",
                "camera": camera_manager.status(),
            }
        )

    @app.get("/camera/feed")
    def camera_feed() -> Response:
        """Stream the latest annotated camera frames to the browser."""
        source = request.args.get("source", "0")
        if not camera_manager.running:
            camera_manager.start(source)

        def generate():
            last_sent = b""
            while True:
                frame = camera_manager.get_latest_frame()
                if not frame:
                    time.sleep(0.05)
                    continue
                if frame == last_sent:
                    time.sleep(0.03)
                    continue
                last_sent = frame
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                )

        return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.get("/camera/view")
    def camera_view() -> Response:
        """Render a browser page for the live camera stream."""
        source = request.args.get("source", "0")
        if not camera_manager.running:
            camera_manager.start(source)

        html = f"""
        <!doctype html>
        <html>
        <head>
            <title>RoadWatch AI Live Camera</title>
            <style>
                body {{
                    margin: 0;
                    background: #0b0f1a;
                    color: #f8fafc;
                    font-family: 'IBM Plex Mono', 'Courier New', monospace;
                    padding: 24px;
                }}
                .wrap {{
                    max-width: 1200px;
                    margin: 0 auto;
                }}
                .top {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 16px;
                }}
                .btn {{
                    background: #22c55e;
                    color: #081018;
                    border: none;
                    border-radius: 999px;
                    padding: 10px 16px;
                    cursor: pointer;
                    font-weight: 700;
                    margin-left: 10px;
                }}
                .btn.stop {{
                    background: #ef4444;
                    color: #fff;
                }}
                .panel {{
                    background: #111827;
                    border-radius: 18px;
                    padding: 16px;
                    border: 1px solid #38bdf822;
                }}
                img {{
                    width: 100%;
                    border-radius: 14px;
                    display: block;
                    background: #000;
                }}
            </style>
        </head>
        <body>
            <div class="wrap">
                <div class="top">
                    <div>
                        <h1 style="margin:0;">ROADWATCH AI LIVE CAMERA</h1>
                        <div style="color:#94a3b8;">Browser stream for webcam or dashcam input</div>
                    </div>
                    <div>
                        <button class="btn" onclick="window.location.reload()">Refresh</button>
                        <button class="btn stop" onclick="fetch('/api/camera/stop', {{method:'POST'}})">Stop Camera</button>
                    </div>
                </div>
                <div class="panel">
                    <img src="/camera/feed?source={source}" alt="Live camera stream" />
                </div>
            </div>
        </body>
        </html>
        """
        return Response(html, mimetype="text/html")

    @app.post("/api/camera/start")
    def api_camera_start() -> Any:
        """Start live camera monitoring from app.py."""
        payload: Dict[str, Any] = request.get_json(silent=True) or {}
        source = str(payload.get("source", "0"))
        started = camera_manager.start(source)
        if not started:
            return jsonify({"status": "already_running", "camera": camera_manager.status()}), 409
        return jsonify({"status": "started", "camera": camera_manager.status()})

    @app.post("/api/camera/stop")
    def api_camera_stop() -> Any:
        """Stop live camera monitoring."""
        stopped = camera_manager.stop()
        if not stopped:
            return jsonify({"status": "not_running", "camera": camera_manager.status()}), 409
        return jsonify({"status": "stopping", "camera": camera_manager.status()})

    @app.get("/api/camera/status")
    def api_camera_status() -> Any:
        """Return live camera runtime details."""
        return jsonify(camera_manager.status())

    @app.get("/")
    def index() -> Any:
        """Return a small landing payload for the service."""
        return jsonify(
            {
                "name": "RoadWatch AI",
                "dashboard": f"http://localhost:{Config.FLASK_PORT}/dashboard/",
                "api_base": f"http://localhost:{Config.FLASK_PORT}/api/",
            }
        )

    return app


app = create_app()


def print_startup_banner() -> None:
    """Print the startup banner requested for the project."""
    model_status = get_model_status()
    print("RoadWatch AI Starting...")
    print(f"Model loaded: {model_status['model_name']}")
    print(f"MongoDB {get_db_status()}")
    print("Google Maps API ready" if google_maps_ready() else "Google Maps API ready (fallback mode)")
    print(f"Dashboard: http://localhost:{Config.FLASK_PORT}/dashboard/")
    print(f"API Base:  http://localhost:{Config.FLASK_PORT}/api/")
    print("Camera Control: POST /api/camera/start  |  POST /api/camera/stop")


def build_parser() -> argparse.ArgumentParser:
    """Build command line options for the unified app entry point."""
    parser = argparse.ArgumentParser(description="RoadWatch AI application server")
    parser.add_argument("--camera", action="store_true", help="Start live camera monitoring with the Flask app")
    parser.add_argument("--source", default="0", help="Camera index or video file path for live monitoring")
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    seed_dummy_data()
    print_startup_banner()
    if args.camera:
        camera_manager.start(args.source)
    app.run(host="0.0.0.0", port=Config.FLASK_PORT, debug=True)
