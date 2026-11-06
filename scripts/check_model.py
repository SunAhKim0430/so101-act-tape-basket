#!/usr/bin/env python
r"""Model check - 5_rollout.bat runs this on the robot PC before it connects to the arm.

Reads a trained model folder (a release zip, or the pretrained_model/ folder from training) without loading the weights and checks
that the rollout settings fit it: every file is there, config.bat opens the same cameras the model was trained
with, and n_action_steps <= chunk_size.

    python check_model.py %USERPROFILE%\so101_models\act_so101_tape_15ep_c100_050000 --cameras front --n-action-steps 100
"""

import argparse
import json
from pathlib import Path

FILES = ["config.json", "model.safetensors", "policy_preprocessor.json", "policy_postprocessor.json"]


def safetensors_complete(path: Path) -> bool:
    """A .safetensors file states its own length in its header: a shorter file is a download that did not finish."""
    try:
        with open(path, "rb") as f:
            n = int.from_bytes(f.read(8), "little")
            header = json.loads(f.read(n))
        end = max((v["data_offsets"][1] for k, v in header.items() if k != "__metadata__"), default=0)
        return path.stat().st_size == 8 + n + end
    except (OSError, ValueError, KeyError, TypeError):
        return False


def show_folder(folder: Path):
    if not folder.is_dir():
        print(f"  {folder} does not exist")
        return
    items = sorted(folder.rglob("*"))
    for p in items[:20]:
        size = f"{p.stat().st_size / 1e6:8.1f} MB" if p.is_file() else "  folder"
        print(f"  {size}  {p.relative_to(folder)}")
    if len(items) > 20:
        print(f"  ... {len(items) - 20} more")
    if not items:
        print("  (empty - the download did not finish, or the files went to another folder)")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("model", type=Path, help="pretrained_model folder")
    parser.add_argument("--cameras", default="front", help="camera names the rollout opens, comma-separated (config.bat)")
    parser.add_argument("--n-action-steps", type=int, required=True)
    parser.add_argument("--fps", type=int, default=30)
    args = parser.parse_args()

    missing = [f for f in FILES if not (args.model / f).is_file()]
    if missing:
        print(f"[FAIL] {args.model}: missing {missing} - copy the whole pretrained_model folder")
        print("  what is in that folder:")
        show_folder(args.model)
        print("  VSCode Download puts the folder INSIDE the folder you pick: pick %USERPROFILE%\\so101_models itself")
        raise SystemExit(1)

    # normalizer files named in the processor configs, and every .safetensors fully downloaded
    weights = ["model.safetensors"]
    for proc in ["policy_preprocessor.json", "policy_postprocessor.json"]:
        weights += [s["state_file"] for s in json.loads((args.model / proc).read_text())["steps"] if s.get("state_file")]
    bad = [w for w in weights if not (args.model / w).is_file() or not safetensors_complete(args.model / w)]
    if bad:
        print(f"[FAIL] {args.model}: missing or cut short {bad} - the download did not finish, download it again")
        show_folder(args.model)
        raise SystemExit(1)

    cfg = json.loads((args.model / "config.json").read_text())
    train_file = args.model / "train_config.json"
    train = json.loads(train_file.read_text()) if train_file.is_file() else {}
    chunk = cfg["chunk_size"]
    model_cams = sorted(k.removeprefix("observation.images.") for k, v in cfg["input_features"].items() if v["type"] == "VISUAL")
    rollout_cams = sorted(c for c in args.cameras.split(",") if c)
    n = args.n_action_steps

    print(f"model   : {cfg['type']}, chunk_size {chunk} = {chunk / args.fps:.1f}s, job {train.get('job_name')}, "
          f"data {train.get('dataset', {}).get('root')}")
    print(f"cameras : model {model_cams}, config.bat {rollout_cams}")
    print(f"actions : n_action_steps {n} -> new prediction every {n / args.fps:.1f}s")

    errors = []
    if model_cams != rollout_cams:
        errors.append(f"cameras differ: the model needs {model_cams} - set FRONT_CAM / WRIST_CAM in config.bat as when recording")
    if not 1 <= n <= chunk:
        errors.append(f"n_action_steps must be 1..{chunk} (chunk_size of this model)")
    for e in errors:
        print(f"[FAIL] {e}")
    if errors:
        raise SystemExit(1)
    print("[OK] model fits the rollout settings")


if __name__ == "__main__":
    main()
