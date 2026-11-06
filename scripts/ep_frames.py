#!/usr/bin/env python
"""Look at a LeRobot v3 dataset without a viewer: frame sheets per episode + where the yellow tape starts.

  sheet_<n>.jpg : one row per episode = start / gripper widest open / end frame (5 episodes per sheet)
  printed       : tape centre (px) in each episode's first frame, found by yellow colour in the left part of the
                  image (the basket is on the right). Episodes recorded at different spots should differ by tens of px.

    python scripts/ep_frames.py datasets/so101_tape_basket --out outputs/frames
"""

import argparse
from pathlib import Path

import av
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

W, H = 320, 240


def tape_centre(img: Image.Image, left: float):
    hsv = np.asarray(img.convert("HSV")).astype(int)
    m = (hsv[..., 0] > 25) & (hsv[..., 0] < 50) & (hsv[..., 1] > 90) & (hsv[..., 2] > 120)  # yellow, PIL hue 0-255
    m[:, int(m.shape[1] * left):] = False
    ys, xs = np.nonzero(m)
    return (xs.mean(), ys.mean(), len(xs)) if len(xs) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cam", default="observation.images.front")
    ap.add_argument("--per-sheet", type=int, default=5)
    ap.add_argument("--left", type=float, default=0.45, help="search the tape only in this left fraction of the image")
    args = ap.parse_args()
    root, cam = args.root, args.cam
    args.out.mkdir(parents=True, exist_ok=True)

    ep = pd.concat(pd.read_parquet(p) for p in sorted((root / "meta/episodes").rglob("*.parquet")))
    data = pd.concat(pd.read_parquet(p, columns=["episode_index", "action"]) for p in sorted((root / "data").rglob("*.parquet")))
    fps = 30

    want = {}  # (video file, time) -> list of (episode, column)
    rows = []
    for _, r in ep.sort_values("episode_index").iterrows():
        e = int(r.episode_index)
        vid = root / f"videos/{cam}/chunk-{int(r[f'videos/{cam}/chunk_index']):03d}/file-{int(r[f'videos/{cam}/file_index']):03d}.mp4"
        t0, t1 = float(r[f"videos/{cam}/from_timestamp"]), float(r[f"videos/{cam}/to_timestamp"])
        grip = np.stack(data[data.episode_index == e].action.values)[:, -1]
        ts = [t0 + 0.05, t0 + int(np.argmax(grip)) / fps, t1 - 0.1]
        for j, t in enumerate(ts):
            want.setdefault((vid, t), []).append((e, j))
        rows.append(e)

    frames = {}
    for vid in sorted({v for v, _ in want}):
        times = sorted(t for v, t in want if v == vid)
        with av.open(str(vid)) as c:
            s = c.streams.video[0]
            k = 0
            for f in c.decode(s):
                t = float(f.pts * s.time_base)
                while k < len(times) and t >= times[k] - 1e-3:
                    for e, j in want[(vid, times[k])]:
                        frames[(e, j)] = f.to_image()
                    k += 1
                if k == len(times):
                    break

    print(f"tape centre in the first frame of each episode (image {frames[(rows[0], 0)].size[0]}x{frames[(rows[0], 0)].size[1]} px)")
    for e in rows:
        c = tape_centre(frames[(e, 0)], args.left)
        print(f"ep{e:03d}  " + (f"x={c[0]:4.0f}  y={c[1]:4.0f}  ({c[2]} px)" if c else "tape not found"))

    for n, i in enumerate(range(0, len(rows), args.per_sheet)):
        eps = rows[i:i + args.per_sheet]
        sheet = Image.new("RGB", (W * 3, H * len(eps)), "white")
        d = ImageDraw.Draw(sheet)
        for y, e in enumerate(eps):
            for j, label in enumerate(["start", "grip open", "end"]):
                sheet.paste(frames[(e, j)].resize((W, H)), (j * W, y * H))
                d.text((j * W + 5, y * H + 5), f"ep{e} {label}", fill="yellow")
        sheet.save(args.out / f"sheet_{n}.jpg", quality=85)
    print(f"sheets: {args.out}/sheet_0..{n}.jpg  (rows = episodes, columns = start / gripper widest open / end)")


if __name__ == "__main__":
    main()
