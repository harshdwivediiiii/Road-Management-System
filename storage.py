from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from uuid import uuid4

try:
    from bson import ObjectId
except ImportError:  # pragma: no cover - optional dependency fallback
    ObjectId = None

try:
    from pymongo import MongoClient
    from pymongo.collection import Collection
    from pymongo.errors import PyMongoError
except ImportError:  # pragma: no cover - optional dependency fallback
    MongoClient = None
    Collection = Any

    class PyMongoError(Exception):
        """Fallback exception used when pymongo is unavailable."""

from config import Config


_mongo_client: MongoClient | None = None
_collection: Collection | None = None
_memory_store: List[Dict[str, Any]] = []


def mongo_available() -> bool:
    """Return whether MongoDB is reachable."""
    global _mongo_client
    try:
        if MongoClient is None:
            return False
        if _mongo_client is None:
            _mongo_client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=1500)
        _mongo_client.admin.command("ping")
        return True
    except PyMongoError as exc:
        print(f"[DB][WARN] MongoDB unavailable, using in-memory fallback: {exc}")
        return False


def get_db_status() -> str:
    """Return a human-readable database status."""
    return "connected" if mongo_available() else "fallback"


def get_collection() -> Collection:
    """Return a singleton MongoDB collection handle."""
    global _mongo_client, _collection
    if _collection is None and mongo_available():
        _collection = _mongo_client[Config.MONGO_DB][Config.MONGO_COLLECTION]
        _collection.create_index("timestamp")
        _collection.create_index("status")
        _collection.create_index("zone")
        _collection.create_index("severity")
    return _collection


def serialize_document(document: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Mongo specific values into JSON-safe types."""
    payload = dict(document)
    if "_id" in payload:
        payload["_id"] = str(payload["_id"])
    return payload


def save_pothole(report: dict) -> str:
    """Save one pothole report. Return inserted ID as string."""
    try:
        collection = get_collection()
        if collection is None:
            payload = dict(report)
            payload["_id"] = str(ObjectId()) if ObjectId is not None else str(uuid4())
            _memory_store.append(payload)
            return payload["_id"]
        result = collection.insert_one(dict(report))
        return str(result.inserted_id)
    except PyMongoError as exc:
        print(f"[DB][ERROR] Failed to save pothole: {exc}")
        raise


def get_all_potholes(limit: int = 50) -> list:
    """Return latest N potholes sorted by timestamp descending."""
    try:
        collection = get_collection()
        if collection is None:
            items = sorted(_memory_store, key=lambda item: item.get("timestamp", ""), reverse=True)
            return [serialize_document(item) for item in items[:limit]]
        cursor = collection.find().sort("timestamp", -1).limit(limit)
        return [serialize_document(item) for item in cursor]
    except PyMongoError as exc:
        print(f"[DB][ERROR] Failed to fetch potholes: {exc}")
        return []


def get_counts() -> dict:
    """Return {total, pending, fixed, in_progress, high_severity}."""
    try:
        collection = get_collection()
        if collection is None:
            return {
                "total": len(_memory_store),
                "pending": sum(1 for item in _memory_store if item.get("status") == "Pending"),
                "fixed": sum(1 for item in _memory_store if item.get("status") == "Fixed"),
                "in_progress": sum(1 for item in _memory_store if item.get("status") == "In Progress"),
                "high_severity": sum(1 for item in _memory_store if item.get("severity") == "High"),
            }
        return {
            "total": collection.count_documents({}),
            "pending": collection.count_documents({"status": "Pending"}),
            "fixed": collection.count_documents({"status": "Fixed"}),
            "in_progress": collection.count_documents({"status": "In Progress"}),
            "high_severity": collection.count_documents({"severity": "High"}),
        }
    except PyMongoError as exc:
        print(f"[DB][ERROR] Failed to compute counts: {exc}")
        return {"total": 0, "pending": 0, "fixed": 0, "in_progress": 0, "high_severity": 0}


def get_hourly_counts(hours: int = 8) -> list:
    """Return [{hour: '10:00', count: 5}, ...] for last N hours."""
    try:
        collection = get_collection()
        now = datetime.now()
        start = now - timedelta(hours=hours - 1)
        buckets: List[Dict[str, Any]] = []
        for hour_offset in range(hours):
            slot = start + timedelta(hours=hour_offset)
            next_slot = slot + timedelta(hours=1)
            if collection is None:
                count = sum(
                    1
                    for item in _memory_store
                    if slot.isoformat() <= str(item.get("timestamp", "")) < next_slot.isoformat()
                )
            else:
                count = collection.count_documents(
                    {
                        "timestamp": {
                            "$gte": slot.isoformat(),
                            "$lt": next_slot.isoformat(),
                        }
                    }
                )
            buckets.append({"hour": slot.strftime("%H:00"), "count": count})
        return buckets
    except PyMongoError as exc:
        print(f"[DB][ERROR] Failed to compute hourly counts: {exc}")
        return []


def get_zone_counts() -> list:
    """Return [{zone: 'MG Road', count: 12}, ...] sorted by count."""
    try:
        collection = get_collection()
        if collection is None:
            summary: Dict[str, Dict[str, Any]] = {}
            for item in _memory_store:
                zone = item.get("zone") or "Unknown Zone"
                entry = summary.setdefault(zone, {"zone": zone, "count": 0, "fixed": 0})
                entry["count"] += 1
                if item.get("status") == "Fixed":
                    entry["fixed"] += 1
            zones = list(summary.values())
            zones.sort(key=lambda item: item["count"], reverse=True)
            for zone in zones:
                zone["resolved_percent"] = round((zone["fixed"] / zone["count"]) * 100, 2) if zone["count"] else 0.0
            return zones
        pipeline = [
            {"$group": {"_id": "$zone", "count": {"$sum": 1}, "fixed": {"$sum": {"$cond": [{"$eq": ["$status", "Fixed"]}, 1, 0]}}}},
            {"$sort": {"count": -1}},
        ]
        zones = []
        for row in collection.aggregate(pipeline):
            zone_name = row["_id"] or "Unknown Zone"
            zones.append(
                {
                    "zone": zone_name,
                    "count": row["count"],
                    "fixed": row.get("fixed", 0),
                    "resolved_percent": round((row.get("fixed", 0) / row["count"]) * 100, 2) if row["count"] else 0.0,
                }
            )
        return zones
    except PyMongoError as exc:
        print(f"[DB][ERROR] Failed to compute zone counts: {exc}")
        return []


def get_status_counts() -> dict:
    """Return {Pending: N, Fixed: N, In Progress: N}."""
    try:
        collection = get_collection()
        if collection is None:
            return {
                "Pending": sum(1 for item in _memory_store if item.get("status") == "Pending"),
                "Fixed": sum(1 for item in _memory_store if item.get("status") == "Fixed"),
                "In Progress": sum(1 for item in _memory_store if item.get("status") == "In Progress"),
            }
        return {
            "Pending": collection.count_documents({"status": "Pending"}),
            "Fixed": collection.count_documents({"status": "Fixed"}),
            "In Progress": collection.count_documents({"status": "In Progress"}),
        }
    except PyMongoError as exc:
        print(f"[DB][ERROR] Failed to compute status counts: {exc}")
        return {"Pending": 0, "Fixed": 0, "In Progress": 0}


def get_severity_counts() -> dict:
    """Return {High: N, Medium: N, Low: N}."""
    try:
        collection = get_collection()
        if collection is None:
            return {
                "High": sum(1 for item in _memory_store if item.get("severity") == "High"),
                "Medium": sum(1 for item in _memory_store if item.get("severity") == "Medium"),
                "Low": sum(1 for item in _memory_store if item.get("severity") == "Low"),
            }
        return {
            "High": collection.count_documents({"severity": "High"}),
            "Medium": collection.count_documents({"severity": "Medium"}),
            "Low": collection.count_documents({"severity": "Low"}),
        }
    except PyMongoError as exc:
        print(f"[DB][ERROR] Failed to compute severity counts: {exc}")
        return {"High": 0, "Medium": 0, "Low": 0}


def mark_as_fixed(pothole_id: str) -> bool:
    """Update status to Fixed. Return True if successful."""
    try:
        collection = get_collection()
        if collection is None:
            for item in _memory_store:
                if item.get("_id") == pothole_id:
                    item["status"] = "Fixed"
                    item["updated_at"] = datetime.now().isoformat()
                    return True
            return False
        if ObjectId is None:
            return False
        result = collection.update_one(
            {"_id": ObjectId(pothole_id)},
            {"$set": {"status": "Fixed", "updated_at": datetime.now().isoformat()}},
        )
        return result.modified_count > 0
    except (PyMongoError, ValueError) as exc:
        print(f"[DB][ERROR] Failed to mark pothole fixed: {exc}")
        return False


def seed_dummy_data(count: int = 25):
    """If collection is empty, insert dummy pothole records for testing."""
    try:
        collection = get_collection()
        if collection is None and _memory_store:
            return
        if collection is not None and collection.count_documents({}) > 0:
            return

        now = datetime.now()
        docs = []
        zones = ["MG Road", "Indiranagar", "Whitefield", "Electronic City", "Koramangala"]
        severities = ["High", "Medium", "Low"]
        statuses = ["Pending", "In Progress", "Fixed"]
        for idx in range(count):
            timestamp = (now - timedelta(minutes=idx * 17)).isoformat()
            zone = zones[idx % len(zones)]
            severity = severities[idx % len(severities)]
            status = statuses[idx % len(statuses)]
            docs.append(
                {
                    "hazard_type": "Pothole",
                    "zone": zone,
                    "address": f"{zone} Main Road, Bengaluru",
                    "maps_link": f"https://www.google.com/maps/search/?api=1&query=12.97{idx},77.59{idx}",
                    "image_path": "",
                    "status": status,
                    "severity": severity,
                    "confidence": round(0.55 + (idx % 4) * 0.1, 2),
                    "timestamp": timestamp,
                    "lat": 12.9716,
                    "lng": 77.5946,
                }
            )
        if collection is None:
            for item in docs:
                item["_id"] = str(ObjectId()) if ObjectId is not None else str(uuid4())
                _memory_store.append(item)
        else:
            collection.insert_many(docs)
        print(f"[DB] Seeded {count} dummy pothole records.")
    except PyMongoError as exc:
        print(f"[DB][ERROR] Failed to seed dummy data: {exc}")
