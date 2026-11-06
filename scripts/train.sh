#!/bin/bash
# Training on a Linux GPU PC: check recordings -> merge sessions -> episode stats -> ACT chunk 30/50/100 in the background.
# Run it with the LeRobot 0.6.1 environment active. Folder arguments and settings are relative to the repo root.
#
#   scripts/train.sh                 everything. Recordings go in datasets/incoming/ (one folder per recording session)
#   scripts/train.sh check [folder]  check + episode stats only, no merge / training (test recording: datasets/pilot)
#   scripts/train.sh status          progress of the training runs
#
# Settings (env): INCOMING=datasets/incoming DATASET=datasets/so101_tape_basket OUT=outputs
#   CHUNKS="30 50 100" STEPS=100000 BATCH=8 SAVE_FREQ=10000 FPS=30
#   GPUS="0 1 2" picks GPUs by hand (default: GPUs with <1 GB used and <10% busy, runs share them if there are fewer)
# Training is started with setsid nohup: closing the terminal / SSH does not stop it.
# Our demo model: 15 episodes, STEPS=50000 -> outputs/act_c100/checkpoints/050000 (about 35 min on one A100).
set -euo pipefail
SELF=$(readlink -f "$0")
cd "$(dirname "$SELF")/.."
command -v lerobot-train > /dev/null || { echo "[FAIL] lerobot-train not found - activate the LeRobot 0.6.1 environment first"; exit 1; }

INCOMING=${INCOMING:-datasets/incoming}
DATASET=${DATASET:-datasets/so101_tape_basket}
OUT=${OUT:-outputs}
REPORT=${REPORT:-$OUT/dataset_check_$(date +%F).md}
CHUNKS=${CHUNKS:-"30 50 100"}
STEPS=${STEPS:-100000}
BATCH=${BATCH:-8}
SAVE_FREQ=${SAVE_FREQ:-10000}
NUM_WORKERS=${NUM_WORKERS:-8}
FPS=${FPS:-30}
SCRIPTS=scripts
mkdir -p "$OUT"

find_datasets() {  # folders under $1 holding meta/info.json, sorted (session folders are named by time)
    find "$1" -maxdepth 4 -path '*/meta/info.json' -printf '%h\n' 2>/dev/null | sed 's#/meta$##' | sort
}

no_dataset() {
    echo "[FAIL] no dataset under $1 (looked for */meta/info.json)"
    if compgen -G "$1/*.zip" > /dev/null; then echo "       found a .zip - unzip it there first"; fi
    echo "       upload the whole recording folder (meta/ data/ videos/) into $1/"
    exit 1
}

status() {
    local found=0
    for log in $(ls "$OUT"/act_c*.log 2>/dev/null | sort -V); do
        found=1
        local name state last prog ckpt
        name=$(basename "$log" .log)
        if pgrep -f -- "--output_dir=$OUT/$name " > /dev/null; then state=running
        elif grep -q "End of training" "$log"; then state=done
        else state="STOPPED - see $log"; fi
        last=$(tr '\r' '\n' < "$log" | grep 'ot_train.py.*step:' | tail -1 | grep -oE ' (step|loss|l1_loss):[^ ]+' | tr -d '\n' || true)
        prog=$(tr '\r' '\n' < "$log" | grep -oE '[0-9]+/[0-9]+ \[[^]]*\]' | tail -1 || true)
        ckpt=$(ls "$OUT/$name/checkpoints" 2>/dev/null | grep -v last | tr '\n' ' ' || true)
        echo "$name  $state  ${last:-starting}  $prog"
        echo "    checkpoints: ${ckpt:-none yet}"
    done
    [ $found = 1 ] || echo "no runs yet ($OUT/act_c*.log)"
    nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader
}

check_and_stats() {  # check_dataset.py on all given folders, ep_stats.py on each if the check passed
    if ! python $SCRIPTS/check_dataset.py --fps "$FPS" "$@"; then
        echo "[FAIL] dataset check failed - fix the upload and run again (nothing was merged or trained)"
        return 1
    fi
    for d in "$@"; do
        echo; echo "== episode stats: $d"
        python $SCRIPTS/ep_stats.py "$d"
    done
}

cmd=${1:-train}
case $cmd in
    status) status; exit ;;
    check|train) ;;
    *) sed -n '2,13p' "$SELF"; exit 1 ;;
esac

# everything below is also written to the report
echo -e "\n## $(date '+%F %T') train.sh ${*:-train}\n\n\`\`\`text" >> "$REPORT"
exec > >(tee -a "$REPORT") 2>&1
TEE_PID=$!
trap 'exec >&- 2>&-; wait $TEE_PID; echo "\`\`\`" >> "$REPORT"' EXIT
echo "report: $REPORT"

if [ "$cmd" = check ]; then
    mapfile -t SRC < <(find_datasets "${2:-$INCOMING}")
    [ ${#SRC[@]} -gt 0 ] || no_dataset "${2:-$INCOMING}"
    check_and_stats "${SRC[@]}"
    exit
fi

# dataset: merge the uploaded sessions into $DATASET (uploads stay untouched in $INCOMING)
if [ -f "$DATASET/meta/info.json" ]; then
    echo "[INFO] $DATASET already exists -> training on it (delete it to rebuild from $INCOMING)"
else
    mapfile -t SRC < <(find_datasets "$INCOMING")
    [ ${#SRC[@]} -gt 0 ] || no_dataset "$INCOMING"
    echo "===== 1. check ${#SRC[@]} uploaded folder(s)"
    python $SCRIPTS/check_dataset.py --fps "$FPS" "${SRC[@]}" || {
        echo "[FAIL] dataset check failed - fix the upload and run again (nothing was merged or trained)"; exit 1; }

    echo; echo "===== 2. merge -> $DATASET"
    [ ! -e "$DATASET" ] || { echo "[FAIL] $DATASET exists but has no meta/info.json - move or delete it first"; exit 1; }
    roots=$(printf '%s\n' "${SRC[@]}" | python -c 'import json, sys; print(json.dumps(sys.stdin.read().split("\n")[:-1]))')
    ids=$(python -c "import json; print(json.dumps([f'local/src{i}' for i in range(${#SRC[@]})]))")
    mkdir -p "$OUT"
    if ! lerobot-edit-dataset --new_repo_id "local/$(basename "$DATASET")" --new_root "$DATASET" \
            --operation.type merge --operation.repo_ids "$ids" --operation.roots "$roots" > "$OUT/merge.log" 2>&1; then
        tail -20 "$OUT/merge.log"; echo "[FAIL] merge failed, full log: $OUT/merge.log"
        echo "       delete the half-written $DATASET before running again"; exit 1
    fi
    grep -o 'Episodes: .*' "$OUT/merge.log"
fi

echo; echo "===== 3. check $DATASET + episode stats"
check_and_stats "$DATASET" || exit 1

# training: one run per chunk size, on free GPUs
echo; echo "===== 4. train ACT (chunk ${CHUNKS// /, }), $STEPS steps, batch $BATCH, checkpoint every $SAVE_FREQ"
if [ -n "${GPUS:-}" ]; then
    read -ra G <<< "$GPUS"
else
    mapfile -t G < <(nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader,nounits |
        awk -F', *' '$2 < 1000 && $3 < 10 {print $1}')
fi
[ ${#G[@]} -gt 0 ] || { echo "[FAIL] no free GPU - check nvidia-smi and set GPUS=\"<index> ...\""; exit 1; }
fps=$(python -c "import json; print(json.load(open('$DATASET/meta/info.json'))['fps'])")

mkdir -p "$OUT"
declare -A PIDS=()
i=0
for c in $CHUNKS; do
    name=act_c$c
    if [ -e "$OUT/$name" ]; then
        echo "[SKIP] $OUT/$name already exists (lerobot-train never overwrites) - delete or rename it to train again"
        continue
    fi
    gpu=${G[$((i % ${#G[@]}))]}
    i=$((i + 1))
    CUDA_VISIBLE_DEVICES=$gpu setsid nohup lerobot-train \
        --dataset.repo_id="local/$(basename "$DATASET")" --dataset.root="$DATASET" \
        --policy.type=act --policy.chunk_size="$c" --policy.n_action_steps="$c" \
        --policy.push_to_hub=false --policy.device=cuda \
        --batch_size="$BATCH" --steps="$STEPS" --save_freq="$SAVE_FREQ" --num_workers="$NUM_WORKERS" \
        --output_dir="$OUT/$name" --job_name="$name" --wandb.enable=false \
        > "$OUT/$name.log" 2>&1 < /dev/null &
    PIDS[$name]=$!
    echo "  $name  chunk $c = $(awk "BEGIN {printf \"%.1f\", $c / $fps}")s  GPU $gpu  pid $!  log $OUT/$name.log"
done
[ ${#PIDS[@]} -gt 0 ] || exit 0

# the first training steps show whether the config / data loading works (the first step comes after ~10 s)
echo "waiting for the first training steps..."
failed=0
for _ in $(seq 60); do
    pending=0
    for name in "${!PIDS[@]}"; do
        if grep -q -e 'step:' -e 'End of training' "$OUT/$name.log"; then continue; fi  # short runs end before the first log line
        if ! kill -0 "${PIDS[$name]}" 2>/dev/null; then
            tail -15 "$OUT/$name.log"; echo "[FAIL] $name stopped, full log: $OUT/$name.log"
            unset "PIDS[$name]"; failed=1; continue
        fi
        pending=1
    done
    [ $pending = 0 ] && break
    sleep 5
done
for name in "${!PIDS[@]}"; do
    grep -q -e 'step:' -e 'End of training' "$OUT/$name.log" && echo "[OK] $name training" || echo "[WARN] $name still starting - check: $0 status"
done
[ ${#PIDS[@]} -gt 0 ] && cat <<EOF

Reference: on one A100 per run, 50k steps took ~35 min and 100k steps ~70 min (1 camera, 30 fps).
  progress  : $0 status
  live log  : tail -f $OUT/$(printf '%s\n' "${!PIDS[@]}" | sort -V | head -1).log
  checkpoint: $OUT/act_c<chunk>/checkpoints/<step>/pretrained_model   (copy this folder to the robot PC)
EOF
exit $failed
