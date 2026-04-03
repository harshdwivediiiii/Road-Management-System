from __future__ import annotations

from yolo_detect import get_model_status, run_image_test, run_video_test


if __name__ == "__main__":
    status = get_model_status()
    print(f"[YOLO] Model status: {status}")
    run_image_test("Test/1.png")
    run_video_test("Test/Pothole Exp1.mp4")
