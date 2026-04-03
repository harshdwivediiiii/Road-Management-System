from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2

from yolo_detect import detect_frame


@dataclass
class DetectionEvent:
    """Normalized monitoring event emitted by the monitor."""

    hazard_type: str
    confidence: float
    bbox: List[int]
    timestamp: str
    severity: str
    image_path: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    def to_dict(self) -> Dict[str, object]:
        """Convert the event into a JSON-safe dictionary."""
        return {
            "hazard_type": self.hazard_type,
            "confidence": self.confidence,
            "bbox": self.bbox,
            "timestamp": self.timestamp,
            "severity": self.severity,
            "image_path": self.image_path,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }


class GPSProvider:
    """Small helper for fixed or injected GPS coordinates."""

    def __init__(self, latitude: Optional[float] = None, longitude: Optional[float] = None) -> None:
        self.latitude = latitude
        self.longitude = longitude

    def get_coordinates(self) -> Tuple[Optional[float], Optional[float]]:
        """Return the current coordinates."""
        return self.latitude, self.longitude


class RoadHazardMonitor:
    """Wrapper around the detector for compatibility with existing code."""

    def __init__(self, model_path: str | None = None, confidence_threshold: float = 0.5) -> None:
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold

    def detect(self, frame, gps_provider: Optional[GPSProvider] = None, include_image: bool = False) -> List[DetectionEvent]:
        """Run detection on a frame and return normalized events."""
        _ = include_image
        result = detect_frame(frame, confidence_threshold=self.confidence_threshold)
        if not result["detected"]:
            return []

        latitude, longitude = gps_provider.get_coordinates() if gps_provider else (None, None)
        event = DetectionEvent(
            hazard_type="Pothole",
            confidence=result["confidence"],
            bbox=result["bbox"],
            timestamp=result["timestamp"],
            severity=result["severity"],
            image_path=result["image_path"],
            latitude=latitude,
            longitude=longitude,
        )
        return [event]

    def annotate(self, frame, detections: List[DetectionEvent]):
        """Overlay existing detections on a frame."""
        for event in detections:
            x1, y1, x2, y2 = event.bbox
            cv2.rectangle(frame, (x1, y1), (x2, y2), (56, 189, 248), 2)
            cv2.putText(
                frame,
                f"{event.hazard_type} {int(event.confidence * 100)}%",
                (x1, max(20, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (249, 115, 22),
                2,
            )
        return frame
