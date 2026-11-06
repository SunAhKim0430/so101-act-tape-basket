#!/usr/bin/env python
r"""Dataset check - run on the training PC on copied recordings, before merging and training.

Checks one or more LeRobot v3 dataset folders (each one holds meta/, data/, videos/):
  - every file training reads is there (meta, data parquet, every mp4 the episodes point to)
  - fps / cameras as planned (30 fps, not wrist-only)
  - several folders (recording sessions) can be merged: same fps, robot_type and features
  - the first and last frame of every episode decode at their recorded timestamps (catches half-uploaded mp4s)

Exits 1 if anything would stop merging or training. Warnings alone exit 0.

    python check_dataset.py datasets/incoming/*                   # recording sessions to merge
    python check_dataset.py datasets/incoming/pos1_20261106_183919
    python check_dataset.py --fps 10 datasets/old_10fps_recording
"""

import argparse
import json
import logging
import os
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"  # a missing file must fail here, not trigger a download from the Hub

import pandas as pd  # noqa: E402
from lerobot.datasets.feature_utils import features_equal_for_merge  # noqa: E402
from lerobot.datasets.lerobot_dataset import LeRobotDataset  # noqa: E402

REQUIRED = ["meta/info.json", "meta/stats.json", "meta/tasks.parquet"]


def check_one(root: Path, fps: int, errors: list, warns: list) -> dict | None:
    def fail(msg):
        errors.append(f"{root}: {msg}")
        print(f"   [FAIL] {msg}")

    def warn(msg):
        warns.append(msg)
        print(f"   [WARN] {msg}")

    missing = [p for p in REQUIRED if not (root / p).is_file()]
    for pattern in ["meta/episodes/chunk-*/file-*.parquet", "data/chunk-*/file-*.parquet"]:
        if not list(root.glob(pattern)):
            missing.append(pattern)
    if missing:
        fail(f"missing {missing} - upload the whole recording folder, not only videos/")
        return None

    info = json.loads((root / "meta/info.json").read_text())
    cams = [k for k, v in info["features"].items() if v["dtype"] == "video"]
    if info.get("codebase_version") != "v3.0":
        fail(f"dataset format {info.get('codebase_version')}, LeRobot 0.6.1 reads v3.0 - record with lerobot 0.6.1")
        return None
    if info["fps"] != fps:
        fail(f"fps={info['fps']}, plan is {fps} (--dataset.fps={fps} when recording)")
    if not cams:
        fail("no camera (video) feature")
    elif all(c.endswith(".wrist") for c in cams):
        warn("wrist camera only - our first attempt failed partly because the basket is not visible from the wrist")
    if (root / "images").exists():
        warn("images/ folder left over (a recording stopped before its video was encoded). Not used for training")

    # files the episodes point to (one dataset can have several data / mp4 files once they pass 100 / 200 MB)
    ep = pd.concat(pd.read_parquet(f) for f in sorted(root.glob("meta/episodes/chunk-*/file-*.parquet")))
    needed = {info["data_path"].format(chunk_index=c, file_index=f) for c, f in zip(ep["data/chunk_index"], ep["data/file_index"])}
    for cam in cams:
        needed |= {
            info["video_path"].format(video_key=cam, chunk_index=c, file_index=f)
            for c, f in zip(ep[f"videos/{cam}/chunk_index"], ep[f"videos/{cam}/file_index"])
        }
    absent = sorted(p for p in needed if not (root / p).is_file())
    if absent:
        fail(f"missing {len(absent)} file(s): {absent[:5]}")
        return None

    try:
        ds = LeRobotDataset(f"local/{root.name}", root=root)
    except Exception as e:  # corrupt parquet / json, half-uploaded meta
        fail(f"cannot load: {type(e).__name__}: {str(e)[:300]}")
        return None

    lengths, starts, ends = list(ep["length"]), list(ep["dataset_from_index"]), list(ep["dataset_to_index"])
    tasks = list(ds.meta.tasks.index)
    print(
        f"   fps={info['fps']}  cameras={[c.removeprefix('observation.images.') for c in cams]}  "
        f"episodes={len(lengths)}  frames={sum(lengths)}  length {min(lengths) / info['fps']:.1f}~{max(lengths) / info['fps']:.1f}s"
    )
    print(f"   task: {tasks}")
    at_max = sum(n == max(lengths) for n in lengths)
    if len(lengths) >= 3 and at_max / len(lengths) > 0.5:
        warn(
            f"{at_max}/{len(lengths)} episodes are exactly {max(lengths) / info['fps']:.0f}s = the episode_time_s limit "
            "-> 'n' was probably not pressed at the end of the task (idle frames get learned too)"
        )

    bad = []
    for i, (start, end) in enumerate(zip(starts, ends)):
        for idx in (start, end - 1):
            try:
                ds[idx]
            except Exception as e:
                bad.append(f"episode {i} frame {idx}: {type(e).__name__}: {str(e)[:200]}")
    if bad:
        fail(f"{len(bad)} frame(s) failed to decode (half-uploaded or broken mp4?)")
        for b in bad[:3]:
            print(f"          {b}")
    else:
        print(f"   [OK] files, decode {2 * len(lengths)} frames (first + last of every episode)")

    return {"root": root, "fps": info["fps"], "robot_type": info["robot_type"], "features": info["features"],
            "tasks": tasks, "episodes": len(lengths), "frames": sum(lengths)}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("roots", type=Path, nargs="+", help="dataset folder(s), each containing meta/ data/ videos/")
    parser.add_argument("--fps", type=int, default=30, help="expected fps (this project: 30)")
    args = parser.parse_args()
    logging.disable(logging.WARNING)  # LeRobotDataset logs every load

    errors, warns, results = [], [], []
    for root in args.roots:
        print(f"== {root}")
        r = check_one(root, args.fps, errors, warns)
        if r:
            results.append(r)
    n_warns = len(warns)

    if len(results) > 1:
        first = results[0]
        for r in results[1:]:
            for key in ("fps", "robot_type"):
                if r[key] != first[key]:
                    errors.append(f"cannot merge: {r['root']} {key}={r[key]}, {first['root']} {key}={first[key]}")
            if not features_equal_for_merge(first["features"], r["features"]):
                diff = sorted(set(first["features"]) ^ set(r["features"])) or "shape/names differ"
                errors.append(f"cannot merge: {r['root']} features differ from {first['root']}: {diff}")
        tasks = sorted({t for r in results for t in r["tasks"]})
        if len(tasks) > 1:
            warns.append(f"different task strings across folders: {tasks}")

    print(f"\n{len(results)}/{len(args.roots)} folder(s) readable, "
          f"{sum(r['episodes'] for r in results)} episodes, {sum(r['frames'] for r in results)} frames")
    if n_warns:
        print(f"[WARN] {n_warns} warning(s) above")
    for w in warns[n_warns:]:
        print(f"[WARN] {w}")
    for e in errors:
        print(f"[FAIL] {e}")
    print("[OK] ready to merge / train" if not errors else f"[FAIL] {len(errors)} problem(s) - fix before training")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
