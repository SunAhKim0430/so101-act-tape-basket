#!/usr/bin/env python
"""Per-episode quality check for a LeRobot v3 dataset: length, idle head/tail, gripper range, start pose.

Our first (failed) dataset had 65% idle frames. Run it on a test recording before the main recording.

    python ep_stats.py ./datasets/so101_tape_basket
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

MOVE_DEG_PER_S = 10.0  # summed joint motion above this counts as "moving"


def video_spans(root: Path, cam: str | None) -> dict:
    """episode -> where it is in the camera's mp4 (a session's episodes are back to back in one file)"""
    files = sorted((root / "meta" / "episodes").glob("chunk-*/file-*.parquet"))
    if not cam or not files:
        return {}
    ep = pd.concat(pd.read_parquet(f) for f in files)
    cols = [ep[f"videos/{cam}/{k}"] for k in ("file_index", "from_timestamp", "to_timestamp")]
    return {
        i: (f"file-{f:03d} " if f else "") + f"{int(t0 // 60)}:{t0 % 60:04.1f}~{int(t1 // 60)}:{t1 % 60:04.1f}"
        for i, f, t0, t1 in zip(ep["episode_index"], *cols)
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", type=Path, help="dataset folder (the one containing meta/ and data/)")
    args = parser.parse_args()

    info = json.loads((args.root / "meta" / "info.json").read_text())
    fps = info["fps"]
    cams = [k for k, v in info["features"].items() if v["dtype"] == "video"]
    df = pd.concat(pd.read_parquet(f) for f in sorted((args.root / "data").glob("chunk-*/file-*.parquet")))
    print(f"fps={fps}  cameras={cams}  episodes={df['episode_index'].nunique()}  frames={len(df)}")
    spans = video_spans(args.root, cams[0] if cams else None)
    if spans:
        print(f"video  = position in videos/{cams[0]}/chunk-000/file-000.mp4 (all episodes back to back)")

    threshold = MOVE_DEG_PER_S / fps
    total_idle, active_s, bad = 0, [], []
    for ep, g in df.groupby("episode_index"):
        a = np.stack(g["action"].values)
        moving = np.where(np.abs(np.diff(a, axis=0)).sum(1) > threshold)[0]
        if len(moving) == 0:
            total_idle += len(g)
            bad.append(ep)
            print(f"ep{ep:03d} len={len(g) / fps:5.1f}s  video {spans.get(ep, '-')}  NO MOTION")
            continue
        head, tail = moving[0], len(g) - (moving[-1] + 1)
        total_idle += head + tail
        active_s.append((len(g) - head - tail) / fps)
        if (head + tail) / len(g) > 0.3:
            bad.append(ep)
        print(
            f"ep{ep:03d} len={len(g) / fps:5.1f}s  video {spans.get(ep, '-')}  idle head={head / fps:4.1f}s tail={tail / fps:4.1f}s  "
            f"grip=[{a[:, 5].min():.0f},{a[:, 5].max():.0f}]  start={a[0].round(0)}"
        )

    starts = np.stack([np.stack(g["action"].values)[0] for _, g in df.groupby("episode_index")])
    print(f"\nidle fraction : {total_idle / len(df):.0%}  (aim for < 15%)")
    if active_s:
        print(f"active length : median {np.median(active_s):.1f}s  min {min(active_s):.1f}s  max {max(active_s):.1f}s")
    print(f"start pose std: {starts.std(0).round(1)}  (degrees per joint, smaller = more consistent)")
    if bad:
        print(f"check these   : {bad}  (no motion or >30% idle)")


if __name__ == "__main__":
    main()
