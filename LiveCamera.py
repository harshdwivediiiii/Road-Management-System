from __future__ import annotations

import argparse
import time

import cv2

from config import Config
from reporter import create_and_save_report
from yolo_detect import detect_frame


def run_live_monitor(source: str | int = 0) -> None:
    """Run live monitoring from a webcam index or video file path."""
    capture = cv2.VideoCapture(source)
    
    if isinstance(source, str) and source.startswith("http"):
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 3)
        
    if not capture.isOpened():
        print(f"[CAMERA][ERROR] Unable to open source: {source}")
        return

    processed_frames = 0
    detection_count = 0
    start_time = time.time()
    last_stats_time = start_time

    while True:
        ok, frame = capture.read()
        if not ok or frame is None:
            print("[CAMERA] Stream ended or frame unavailable.")
            break

        processed_frames += 1
        display_frame = frame.copy()

        if processed_frames % Config.DETECTION_INTERVAL == 0:
            result = detect_frame(frame)
            if result["detected"]:
                detection_count += 1
                annotated = cv2.imread(result["image_path"])
                if annotated is not None:
                    display_frame = annotated
                report = create_and_save_report(
                    lat=12.9716,
                    lng=77.5946,
                    image_path=result["image_path"],
                    severity=result["severity"],
                    confidence=result["confidence"],
                )
                print(
                    f"[CAMERA][DETECTED] {report['hazard_type']} at {report['address']} "
                    f"({report['confidence']:.2f})"
                )

        cv2.imshow("RoadWatch AI Live Feed", display_frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), ord("Q")):
            print("[CAMERA] Stop requested by user.")
            break

        now = time.time()
        if now - last_stats_time >= 30:
            elapsed = max(now - start_time, 1)
            fps = processed_frames / elapsed
            print(
                f"[CAMERA][STATS] frames={processed_frames} detections={detection_count} "
                f"avg_fps={fps:.2f}"
            )
            last_stats_time = now

    capture.release()
    cv2.destroyAllWindows()


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the live camera script."""
    parser = argparse.ArgumentParser(description="RoadWatch AI live camera monitor")
    parser.add_argument("--source", default="0", help='Webcam index like "0" or video file path.')
    return parser.parse_args()


def normalize_source(raw_source: str) -> str | int:
    """Convert numeric source strings to webcam indices, or format IP addresses."""
    raw_source = raw_source.strip()
    if raw_source.isdigit():
        return int(raw_source)
    if not raw_source.startswith("http") and ("." in raw_source or ":" in raw_source) and ("/" not in raw_source and "\\" not in raw_source):
        # Format raw IP:PORT from CLI to the proper IP Webcam video URL
        return f"http://{raw_source}/video"
    return raw_source


if __name__ == "__main__":
    args = parse_args()
    run_live_monitor(normalize_source(args.source))