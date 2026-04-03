from __future__ import annotations

import argparse
import time
from typing import Any

import cv2

from config import Config
from reporter import create_and_save_report
from yolo_detect import detect_frame, ensure_output_dir


DEFAULT_LAT = 12.9716
DEFAULT_LNG = 77.5946


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser for the camera utility."""
    parser = argparse.ArgumentParser(description="RoadWatch AI live camera monitor")
    parser.add_argument("--source", default="0", help="Camera index or path to a video file")
    return parser


def open_source(source: str) -> cv2.VideoCapture:
    """Open a webcam index or video file source."""
    try:
        capture_source: Any = int(source)
    except ValueError:
        capture_source = source
    return cv2.VideoCapture(capture_source)


def run_camera(source: str = "0") -> None:
    """Run live monitoring over webcam or a video file."""
    ensure_output_dir()
    capture = open_source(source)
    if not capture.isOpened():
        print(f"[CAMERA][ERROR] Unable to open source: {source}")
        return

    frame_index = 0
    detection_count = 0
    processed_count = 0
    stats_started = time.time()

    while True:
        success, frame = capture.read()
        if not success or frame is None:
            print("[CAMERA] End of stream or unable to read frame.")
            break

        annotated_frame = frame.copy()
        if frame_index % Config.DETECTION_INTERVAL == 0:
            processed_count += 1
            result = detect_frame(frame)
            annotated_frame = result["annotated_frame"]
            if result["detected"]:
                detection_count += 1
                report = create_and_save_report(
                    lat=DEFAULT_LAT,
                    lng=DEFAULT_LNG,
                    image_path=result["image_path"],
                    severity=result["severity"],
                    confidence=result["confidence"],
                )
                print(f"[CAMERA][DETECTION] Saved report {report.get('_id', 'n/a')} at {report['address']}")

        cv2.imshow("RoadWatch AI Live Feed", annotated_frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            print("[CAMERA] Quit requested.")
            break

        elapsed = time.time() - stats_started
        if elapsed >= 30:
            print(
                f"[CAMERA][STATS] frames={frame_index + 1} processed={processed_count} detections={detection_count}"
            )
            stats_started = time.time()

        frame_index += 1

    capture.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    args = build_parser().parse_args()
    run_camera(args.source)
