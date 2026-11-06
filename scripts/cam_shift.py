#!/usr/bin/env python
"""Did the camera move between recording sessions? (in our recording it moved ~35 px between two sessions)

For each session folder: median of the episodes' first frames (static scene), edge image of the table/basket area,
phase correlation against the oldest session -> image shift in px. A few px = same view; tens of px = camera moved.

    python scripts/cam_shift.py datasets/incoming   # folder holding the session folders (<name>_<YYYYMMDD_HHMMSS>)
"""

import sys
from pathlib import Path

import av
import numpy as np
import pandas as pd

CAM = "observation.images.front"


def first_frames_median(root: Path) -> np.ndarray:
    ep = pd.read_parquet(sorted((root / "meta/episodes").rglob("*.parquet"))[0])
    starts = list(ep[f"videos/{CAM}/from_timestamp"] + 0.05)
    out = {}
    with av.open(str(root / f"videos/{CAM}/chunk-000/file-000.mp4")) as c:
        s = c.streams.video[0]
        for f in c.decode(s):
            t = float(f.pts * s.time_base)
            for i, w in enumerate(starts):
                if i not in out and t >= w - 1e-3:
                    out[i] = np.asarray(f.to_image().convert("L")).astype(float)
            if len(out) == len(starts):
                break
    return np.median(np.stack(list(out.values())), 0)


def edges(g: np.ndarray) -> np.ndarray:
    h = g.shape[0]
    gy, gx = np.gradient(g)
    e = np.hypot(gx, gy)[int(h * 0.21):int(h * 0.875)]  # skip people in the back and the laptop at the bottom
    e = e - e.mean()
    return e * np.hanning(e.shape[0])[:, None] * np.hanning(e.shape[1])[None]


def shift(a: np.ndarray, b: np.ndarray):
    F = np.fft.fft2(a) * np.conj(np.fft.fft2(b))
    r = np.fft.ifft2(F / (np.abs(F) + 1e-9)).real
    dy, dx = np.unravel_index(np.argmax(r), r.shape)
    dy = dy - r.shape[0] if dy > r.shape[0] // 2 else dy
    dx = dx - r.shape[1] if dx > r.shape[1] // 2 else dx
    return -dx, -dy


def main():
    roots = sorted((p.parent.parent for p in Path(sys.argv[1]).glob("*/meta/info.json")), key=lambda p: p.name.split("_", 1)[-1])
    med = {r.name: first_frames_median(r) for r in roots}
    ref = roots[0].name
    print(f"image shift vs {ref} (px, +x right, +y down; image {med[ref].shape[1]}x{med[ref].shape[0]})")
    for r in roots:
        dx, dy = shift(edges(med[ref]), edges(med[r.name]))
        flag = "  <- camera moved?" if max(abs(dx), abs(dy)) > 15 else ""
        print(f"{r.name:26s} dx={dx:4d} dy={dy:4d}  brightness={med[r.name].mean():5.1f}{flag}")


if __name__ == "__main__":
    main()
