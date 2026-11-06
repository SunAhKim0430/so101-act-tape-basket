#!/usr/bin/env python
r"""Camera check - run this on the PC the cameras are plugged into.

Opens every camera it finds at the recording settings (640x480 @ 30fps) at the same time, the way
lerobot-record does, measures the real frame rate and saves one snapshot per camera so you can tell
which index is the wrist / front / laptop camera.

    python check_cameras.py
    python check_cameras.py --fourcc MJPG      # try this if fps drops with two cameras
    win\1_check.bat camera                     (Windows)
"""

import argparse
import os
import time
from pathlib import Path

# OpenCV's FFMPEG plugin has its own logger that only reads this variable ("Failed list devices for backend dshow")
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")

from lerobot.cameras.configs import ColorMode  # noqa: E402
from lerobot.cameras.opencv import OpenCVCamera, OpenCVCameraConfig  # noqa: E402

import cv2  # noqa: E402  (after lerobot.cameras.opencv, which sets the Windows MSMF flag before cv2 loads)

cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)  # hide "can't open camera by index" noise while scanning


def scan(max_index: int) -> list[int]:
    found = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            found.append(i)
        cap.release()
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--fourcc", default=None, help="e.g. MJPG (default: camera's choice)")
    parser.add_argument("--seconds", type=float, default=5.0, help="how long to measure the frame rate")
    parser.add_argument("--max-index", type=int, default=10, help="scan camera indexes 0..N-1")
    parser.add_argument("--out", type=Path, default=Path("camera_check"), help="folder for snapshots")
    args = parser.parse_args()

    indexes = scan(args.max_index)
    print(f"cameras found at index: {indexes or 'none'}")
    if not indexes:
        print("[FAIL] no camera found. Check the USB cable, and close other apps using the camera (Zoom, Camera app).")
        return

    cams = {}
    for i in indexes:
        cfg = OpenCVCameraConfig(
            index_or_path=i, width=args.width, height=args.height, fps=args.fps,
            color_mode=ColorMode.BGR, fourcc=args.fourcc,
        )
        cam = OpenCVCamera(cfg)
        try:
            cam.connect()
            cams[i] = cam
        except Exception as e:
            print(f"[FAIL] camera {i}: cannot run at {args.width}x{args.height}@{args.fps}: {e}")

    args.out.mkdir(parents=True, exist_ok=True)
    try:
        # Count new frames from every camera's background thread while all of them run together
        last = {i: None for i in cams}
        counts = {i: 0 for i in cams}
        t_end = time.perf_counter() + args.seconds
        while time.perf_counter() < t_end:
            for i, cam in cams.items():
                if cam.latest_timestamp != last[i]:
                    counts[i] += 1
                    last[i] = cam.latest_timestamp
            time.sleep(0.002)

        print(f"\n{'index':<7}{'fps':>6}{'bright':>8}  snapshot")
        for i, cam in cams.items():
            frame = cam.async_read()
            fps = counts[i] / args.seconds
            path = args.out / f"camera_{i}.jpg"
            cv2.imwrite(str(path), frame)
            print(f"{i:<7}{fps:>6.1f}{frame.mean():>8.0f}  {path.resolve()}")
            if fps < 0.9 * args.fps:
                print(f"  [WARN] camera {i}: {fps:.1f} fps < {args.fps}. Try --fourcc MJPG or another USB port")
            if frame.mean() < 20:
                print(f"  [WARN] camera {i}: image is almost black (lens covered? lights off?)")
            elif frame.std() < 5:
                print(f"  [WARN] camera {i}: image is flat (pointing at a wall or out of focus?)")
    finally:
        for cam in cams.values():
            cam.disconnect()

    print("\nOpen the snapshots to see which index is which camera, then write them into win\\config.bat")
    print("(WRIST_CAM / FRONT_CAM). The laptop's built-in webcam is usually index 0 - don't use it.")


if __name__ == "__main__":
    main()
