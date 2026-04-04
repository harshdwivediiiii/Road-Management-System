from __future__ import annotations

from typing import Any, Dict

from flask import Flask, jsonify, redirect, request

from config import Config
from dashboard import mount_dashboard
from reporter import create_and_save_report
from storage import (
    get_all_potholes,
    get_counts,
    get_hourly_counts,
    get_severity_counts,
    get_status_counts,
    get_zone_counts,
    initialize_storage,
    mark_as_fixed,
    seed_dummy_data,
)
from yolo_detect import get_model_status

import subprocess
import sys
import os


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.secret_key = Config.FLASK_SECRET_KEY

    initialize_storage()
    seed_dummy_data()
    mount_dashboard(app)
    register_routes(app)

    print("RoadWatch AI Starting...")
    print(f"Model loaded: {get_model_status()}")
    print(f"MongoDB {'connected' if Config.DB_CONNECTED else 'fallback-active'}")
    print(
        f"Google Maps API {'ready' if Config.GOOGLE_MAPS_API_KEY else 'not configured'}"
    )
    print(f"Dashboard: http://localhost:{Config.FLASK_PORT}/dashboard/")
    print(f"API Base:  http://localhost:{Config.FLASK_PORT}/api/")
    return app


def register_routes(app: Flask) -> None:
    """Register all API and health routes."""

    @app.post("/api/report")
    def api_report() -> Any:
        payload: Dict[str, Any] = request.get_json(silent=True) or {}
        lat = float(payload.get("lat", 0.0))
        lng = float(payload.get("lng", 0.0))
        image_path = str(payload.get("image_path", "")).strip()
        severity = str(payload.get("severity", "Medium"))
        confidence = float(payload.get("confidence", 0.0))

        if not image_path:
            return jsonify({"error": "image_path is required"}), 400

        report = create_and_save_report(
            lat=lat,
            lng=lng,
            image_path=image_path,
            severity=severity,
            confidence=confidence,
        )
        return jsonify({"status": "saved", "report": report}), 201

    @app.get("/api/potholes")
    def api_potholes() -> Any:
        limit = request.args.get("limit", default=50, type=int)
        potholes = get_all_potholes(limit=limit)
        return jsonify({"count": len(potholes), "potholes": potholes})

    @app.get("/api/stats")
    def api_stats() -> Any:
        counts = get_counts()
        total = counts.get("total", 0)
        fixed = counts.get("fixed", 0)
        fix_rate = round((fixed / total) * 100, 2) if total else 0.0
        return jsonify(
            {
                **counts,
                "fix_rate": fix_rate,
                "hourly": get_hourly_counts(hours=8),
                "zones": get_zone_counts(),
                "status_counts": get_status_counts(),
                "severity_counts": get_severity_counts(),
            }
        )

    @app.post("/api/fix/<pothole_id>")
    def api_fix(pothole_id: str) -> Any:
        updated = mark_as_fixed(pothole_id)
        if not updated:
            return jsonify({"status": "not_found"}), 404
        return jsonify({"status": "updated"})

    @app.get("/api/hotspots")
    def api_hotspots() -> Any:
        zones = get_zone_counts()
        hotspots = [zone for zone in zones if zone.get("count", 0) > 1]
        return jsonify(hotspots)

    @app.get("/api/health")
    def api_health() -> Any:
        return jsonify(
            {
                "status": "ok",
                "db": "connected" if Config.DB_CONNECTED else "fallback",
                "model": get_model_status(),
            }
        )


    # Inside register_routes(app) in app.py
    @app.get("/camera/start")
    def start_camera():
        """
        Spawns the LiveCamera.py script as a separate process.
        """
        try:
            # Get the path to the LiveCamera.py file
            script_path = os.path.join(os.path.dirname(__file__), "LiveCamera.py")

            # Launch the script using the current python interpreter
            # --source 0 uses the default webcam as defined in LiveCamera.py
            subprocess.Popen([sys.executable, script_path, "--source", "0"])

            return "<h3>Camera Starting...</h3><p>Check your taskbar for the 'RoadWatch AI Live Feed' window.</p>"
        except Exception as e:
            return f"Error starting camera: {str(e)}", 500


    @app.get("/")
    def index() -> Any:
        return redirect("/dashboard/")


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.FLASK_PORT, debug=False)
