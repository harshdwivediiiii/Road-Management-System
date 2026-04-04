app = Flask(__name__)

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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

import base64
import numpy as np
import cv2
from yolo_detect import detect_frame


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
            # Decode the base64 image coming from the browser canvas
            _, encoded = image_b64.split(",", 1) if "," in image_b64 else ("", image_b64)
            data = base64.b64decode(encoded)
            np_arr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            
            # Detect using YOLO
            result = detect_frame(frame)
            
            if result.get("detected"):
                # Save the report with dummy coordinates as per the original script
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
    def start_camera():
        """Render a Google Meet-style browser camera interface."""
        return f"""
        <!doctype html>
        <html>
        <head>
            <title>RoadWatch AI - Live Camera Session</title>
            <style>
                body {{
                    margin: 0; background: #0b0f1a; color: #f8fafc;
                    font-family: 'IBM Plex Mono', 'Courier New', monospace;
                    display: flex; flex-direction: column; align-items: center; 
                    min-height: 100vh; overflow-x: hidden;
                }}
                .header {{
                    width: 100%; padding: 20px; background: #111827;
                    display: flex; justify-content: space-between; align-items: center;
                    border-bottom: 1px solid #1f2937; box-sizing: border-box;
                }}
                h2 {{ color: #22c55e; margin: 0; font-size: 20px; }}
                .controls {{ display: flex; gap: 10px; align-items: center; }}
                select {{
                    padding: 10px; border-radius: 8px; border: 1px solid #374151; 
                    background: #1f2937; color: #f8fafc; font-family: inherit;
                }}
                select:focus {{ outline: none; border-color: #38bdf8; }}
                .btn {{
                    background: #ef4444; color: #fff; padding: 10px 20px;
                    border-radius: 999px; border: none; font-weight: 700; 
                    cursor: pointer; text-decoration: none; transition: 0.2s;
                }}
                .btn:hover {{ background: #dc2626; }}
                .main-stage {{
                    flex: 1; display: flex; justify-content: center; align-items: center;
                    width: 100%; padding: 20px; box-sizing: border-box; position: relative;
                }}
                .video-wrapper {{
                    position: relative; display: inline-block;
                    max-width: 100%; border-radius: 16px; overflow: hidden;
                    box-shadow: 0 12px 40px rgba(0,0,0,0.5); border: 1px solid #1f2937;
                    background: #000;
                }}
                video {{ 
                    display: block; max-width: 100%; max-height: 75vh;
                }}
                canvas {{ 
                    position: absolute; top: 0; left: 0; 
                    width: 100%; height: 100%; pointer-events: none; 
                }}
                .status-overlay {{
                    position: absolute; top: 20px; left: 20px; 
                    background: rgba(17, 24, 39, 0.8); padding: 8px 16px;
                    border-radius: 8px; font-weight: bold; font-size: 14px;
                    border: 1px solid #374151; color: #38bdf8; z-index: 10;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>RoadWatch AI Live Share</h2>
                <div class="controls">
                    <label>Camera Source:</label>
                    <select id="camera-select"></select>
                    <a href="/dashboard/" class="btn">End Session</a>
                </div>
            </div>
            
            <div class="main-stage">
                <div class="video-wrapper">
                    <video id="videoElement" autoplay playsinline></video>
                    <canvas id="overlayCanvas"></canvas>
                    <div class="status-overlay" id="statusText">Initializing Camera...</div>
                </div>
            </div>

            <!-- Hidden canvas for capturing frames -->
            <canvas id="captureCanvas" style="display:none;"></canvas>

            <script>
                const video = document.getElementById('videoElement');
                const overlay = document.getElementById('overlayCanvas');
                const captureCanvas = document.getElementById('captureCanvas');
                const ctx = overlay.getContext('2d');
                const capCtx = captureCanvas.getContext('2d');
                const cameraSelect = document.getElementById('camera-select');
                const statusText = document.getElementById('statusText');
                
                let currentStream = null;
                let detectionInterval = null;

                // Enumerate and populate cameras (Like Google Meet)
                async function initCameras() {{
                    try {{
                        // Request initial permission carefully
                        await navigator.mediaDevices.getUserMedia({{ video: true }});
                        const devices = await navigator.mediaDevices.enumerateDevices();
                        const videoDevices = devices.filter(d => d.kind === 'videoinput');
                        
                        cameraSelect.innerHTML = '';
                        videoDevices.forEach((device, index) => {{
                            const option = document.createElement('option');
                            option.value = device.deviceId;
                            option.text = device.label || `Camera ${{index + 1}} (Phone Link / Built-in)`;
                            cameraSelect.appendChild(option);
                        }});

                        if(videoDevices.length > 0) {{
                            startStream(videoDevices[0].deviceId);
                        }} else {{
                            statusText.textContent = "No cameras detected.";
                            statusText.style.color = "#ef4444";
                        }}
                    }} catch (err) {{
                        console.error('Camera access error:', err);
                        statusText.textContent = "Camera access denied or unavailable.";
                        statusText.style.color = "#ef4444";
                    }}
                }}

                async function startStream(deviceId) {{
                    if (currentStream) {{
                        currentStream.getTracks().forEach(track => track.stop());
                    }}
                    
                    try {{
                        const constraints = {{
                            video: deviceId ? {{ deviceId: {{ exact: deviceId }} }} : true
                        }};
                        currentStream = await navigator.mediaDevices.getUserMedia(constraints);
                        video.srcObject = currentStream;
                        statusText.textContent = "Live Stream Active";
                        statusText.style.color = "#22c55e";
                        
                        // Setup detection loop once video metadata loads
                        video.onloadedmetadata = () => {{
                            overlay.width = video.videoWidth;
                            overlay.height = video.videoHeight;
                            captureCanvas.width = video.videoWidth;
                            captureCanvas.height = video.videoHeight;
                            
                            if(detectionInterval) clearInterval(detectionInterval);
                            detectionInterval = setInterval(processFrame, 1500); // 1.5s interval
                        }};
                    }} catch (err) {{
                        console.error('Error starting video stream:', err);
                        statusText.textContent = "Failed to start camera.";
                        statusText.style.color = "#ef4444";
                    }}
                }}

                cameraSelect.addEventListener('change', (e) => {{
                    startStream(e.target.value);
                }});

                // Capture and send frame for YOLO detection
                async function processFrame() {{
                    if(video.readyState !== video.HAVE_ENOUGH_DATA) return;
                    
                    // Draw current video frame to hidden canvas
                    capCtx.drawImage(video, 0, 0, captureCanvas.width, captureCanvas.height);
                    const base64Image = captureCanvas.toDataURL('image/jpeg', 0.8);
                    
                    try {{
                        const response = await fetch('/api/detect_frame', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify({{ image: base64Image }})
                        }});
                        
                        const result = await response.json();
                        
                        // Clear previous drawings
                        ctx.clearRect(0, 0, overlay.width, overlay.height);
                        
                        if(result.detected && result.bbox) {{
                            const [x1, y1, x2, y2] = result.bbox;
                            
                            // Draw Bounding Box
                            ctx.strokeStyle = '#22c55e';
                            ctx.lineWidth = 4;
                            ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
                            
                            // Draw Label
                            ctx.fillStyle = '#22c55e';
                            ctx.font = '24px "IBM Plex Mono", monospace';
                            ctx.fillText(`${{result.hazard_type}} (${{result.confidence.toFixed(2)}})`, x1, Math.max(24, y1 - 10));
                            
                            // Flash status
                            statusText.textContent = `DETECTED: ${{result.hazard_type}}!`;
                            statusText.style.color = "#ef4444";
                            setTimeout(() => {{ 
                                statusText.textContent = "Live Stream Active"; 
                                statusText.style.color = "#22c55e";
                            }}, 1000);
                        }}
                    }} catch (err) {{
                        console.error('Detection request failed:', err);
                    }}
                }}

                // Start
                initCameras();
            </script>
        </body>
        </html>
        """


    @app.get("/")
    def index() -> Any:
        return redirect("/dashboard/")


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.FLASK_PORT, debug=False)