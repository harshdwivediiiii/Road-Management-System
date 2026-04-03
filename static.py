"""
Seed MongoDB with static pothole data from constant/data.json.

Reads the MONGO_URI from .env (same connection string the app uses),
loads records from data.json, normalises severity to Title Case so
dashboard charts render correctly, and fills in missing fields
(lat, lng, confidence, image_path) that the dashboard / storage layer expects.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

# ── Load environment variables ───────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "roadhazards")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "potholes")

# ── Connect to MongoDB ──────────────────────────────────────────────
client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
collection = db[MONGO_COLLECTION]

# ── Load JSON data ──────────────────────────────────────────────────
data_path = ROOT_DIR / "constant" / "data.json"
with open(data_path, "r", encoding="utf-8") as f:
    raw_data = json.load(f)


def _extract_lat_lng(maps_link: str):
    """Parse lat,lng from a Google Maps URL like ...?q=28.61,77.20"""
    match = re.search(r"[?&]q=([-\d.]+),([-\d.]+)", maps_link)
    if match:
        return float(match.group(1)), float(match.group(2))
    return 0.0, 0.0


# ── Normalise and enrich each record ────────────────────────────────
records = []
for item in raw_data:
    lat, lng = _extract_lat_lng(item.get("maps_link", ""))

    records.append({
        "hazard_type": item.get("hazard_type", "Pothole"),
        "zone":        item.get("zone", "General"),
        "address":     item.get("address", ""),
        # Title Case severity — dashboard expects "High", "Medium", "Low"
        "severity":    item.get("severity", "Medium").title(),
        "status":      item.get("status", "Pending"),
        "maps_link":   item.get("maps_link", ""),
        "timestamp":   item.get("timestamp", datetime.now().isoformat()),
        # Fields expected by dashboard / storage but missing in data.json
        "lat":         lat,
        "lng":         lng,
        "confidence":  0.75,
        "image_path":  "static/images/dummy.jpg",
    })

# ── Clean and Insert ────────────────────────────────────────────────
collection.delete_many({})
result = collection.insert_many(records)
print(f"{len(result.inserted_ids)} records inserted successfully into {MONGO_DB}.{MONGO_COLLECTION}")