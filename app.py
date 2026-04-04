from __future__ import annotations

from typing import Any, Dict

from flask import Flask, jsonify, redirect, render_template, request
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

import base64
import numpy as np
import cv2
from yolo_detect import detect_frame


# ══════════════════════════════════════════════════════════════════════
# Camera Page — Jinja2 Template (GoI / Digital India theme)
# Stored as a Python string, rendered via render_template_string.
# No separate HTML file needed.
# ══════════════════════════════════════════════════════════════════════

# ── Camera page context — all Python, no HTML escaping needed ────────
CAMERA_COLORS = {
    "bg":           "#F4F6F9",
    "text":         "#374151",
    "saffron":      "#FF9933",
    "india_green":  "#138808",
    "header_bg":    "#1B2A4A",
    "panel_border": "#D1D5DB",
    "red":          "#DC2626",
    "blue":         "#2563EB",
}


def _camera_context() -> dict:
    """Python dict that drives every variable in the camera template."""
    return {
        "title":           "RoadWatch AI — Live Surveillance Session",
        "subtitle":        "Live Surveillance Module · Digital India",
        "feed_label":       "SURVEILLANCE FEED",
        "dashboard_url":    "/dashboard/",
        "detect_url":       "/api/detect_frame",
        "detect_interval":  1500,
        "footer_left":      "ROADWATCH AI  ·  NATIONAL ROAD INFRASTRUCTURE PORTAL",
        "footer_right":     "POWERED BY YOLO v11 · OPENCV · MONGODB",
        "c":                CAMERA_COLORS,
    }


# ══════════════════════════════════════════════════════════════════════
# Flask Application Factory
# ══════════════════════════════════════════════════════════════════════


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

    @app.post("/api/detect_frame")
    def api_detect_frame() -> Any:
        payload = request.get_json(silent=True) or {}
        image_b64 = payload.get("image", "")
        if not image_b64:
            return jsonify({"error": "No image provided"}), 400

        try:
            _, encoded = image_b64.split(",", 1) if "," in image_b64 else ("", image_b64)
            data = base64.b64decode(encoded)
            np_arr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            result = detect_frame(frame)

            if result.get("detected"):
                report = create_and_save_report(
                    lat=12.9716,
                    lng=77.5946,
                    image_path=result["image_path"],
                    severity=result.get("severity", "Medium"),
                    confidence=result.get("confidence", 0.0),
                )
                return jsonify({
                    "detected": True,
                    "hazard_type": report['hazard_type'],
                    "confidence": result['confidence'],
                    "bbox": result['bbox']
                })
            else:
                return jsonify({"detected": False})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.get("/camera/start")
    def start_camera() -> Any:
        """Render the GoI-themed live surveillance interface."""
        return render_template("camera.html", **_camera_context())

    @app.get("/")
    def index() -> Any:
        return redirect("/dashboard/")


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)