from __future__ import annotations

import os
from typing import Any, Dict

from flask import Flask, jsonify, request
from dotenv import load_dotenv

load_dotenv()

from google_maps import GoogleMapsClient, build_google_maps_url
from storage import build_report_store


app = Flask(__name__)
store = build_report_store()
maps_client = GoogleMapsClient(os.getenv("GOOGLE_MAPS_API_KEY"))


@app.get("/health")
def health() -> Any:
    return jsonify({"status": "ok", "service": "road-infrastructure-monitoring"})


@app.post("/api/reports")
def create_report() -> Any:
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    reports = payload.get("reports")
    if reports is None:
        reports = [payload]
    if not isinstance(reports, list) or not reports:
        return jsonify({"error": "Request body must be a report object or {\"reports\": [...]}"}), 400

    saved_reports = []
    for report in reports:
        required_fields = ["hazard_type", "confidence", "timestamp"]
        missing = [field for field in required_fields if field not in report]
        if missing:
            return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

        latitude = report.get("latitude")
        longitude = report.get("longitude")
        if latitude is not None and longitude is not None:
            report["google_maps_url"] = build_google_maps_url(latitude, longitude)
            report["location"] = {
                "type": "Point",
                "coordinates": [longitude, latitude],
            }
        try:
            geocode = maps_client.reverse_geocode(latitude, longitude)
        except Exception as exc:
            geocode = {"error": str(exc)}
        if geocode:
            report["geocode"] = geocode

        saved_reports.append(store.insert_report(report))

    if len(saved_reports) == 1:
        return jsonify(saved_reports[0]), 201
    return jsonify({"reports": saved_reports, "count": len(saved_reports)}), 201


@app.get("/api/reports")
def list_reports() -> Any:
    filters = {
        "hazard_type": request.args.get("hazard_type"),
        "severity": request.args.get("severity"),
    }
    limit = int(request.args.get("limit", "100"))
    return jsonify(store.list_reports(filters=filters, limit=limit))


@app.get("/api/zones")
def list_hotspots() -> Any:
    return jsonify(store.summarize_hotspots())


@app.get("/api/maps/reverse-geocode")
def reverse_geocode() -> Any:
    latitude = request.args.get("lat", type=float)
    longitude = request.args.get("lon", type=float)
    if latitude is None or longitude is None:
        return jsonify({"error": "lat and lon query parameters are required"}), 400
    if not maps_client.enabled:
        return jsonify({"error": "GOOGLE_MAPS_API_KEY is not configured"}), 400

    try:
        payload = maps_client.reverse_geocode(latitude, longitude)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502

    return jsonify(
        {
            "latitude": latitude,
            "longitude": longitude,
            "google_maps_url": build_google_maps_url(latitude, longitude),
            "geocode": payload,
        }
    )




@app.get("/")
def index() -> Any:
    return jsonify(
        {
            "name": "Automated Road Infrastructure Monitoring and Reporting",
            "endpoints": {
                "health": "/health",
                "create_report": "/api/reports",
                "list_reports": "/api/reports",
                "hotspots": "/api/zones",
                "reverse_geocode": "/api/maps/reverse-geocode?lat=<value>&lon=<value>",
            },
            "mongo_enabled": bool(os.getenv("MONGODB_URI")),
            "google_maps_enabled": maps_client.enabled,
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
