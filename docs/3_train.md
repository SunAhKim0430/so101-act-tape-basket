# 3. 학습

NVIDIA GPU가 있는 Linux PC에서 합니다. 우리는 A100을 썼고, 학습 한 개가 GPU 메모리를 약 2GB 씁니다.

## 3-1. 설치

```bash
conda create -y -n lerobot python=3.12
conda activate lerobot
conda install -y ffmpeg -c conda-forge
pip install "lerobot[training]==0.6.1"

git clone https://github.com/SunAhKim0430/so101-act-tape-basket
cd so101-act-tape-basket
mkdir -p datasets/incoming datasets/pilot
```

## 3-2. 실행

녹화 세션 폴더를 `datasets/incoming/`에 넣고 ([2-8](2_record.md#2-8-학습-pc로-옮기기)), 저장소 최상위에서:

```bash
scripts/train.sh check datasets/pilot   # 시험 녹화: 점검 + 통계만 (학습 안 함)
scripts/train.sh                        # 본 녹화: 점검 → 합치기 → 통계 → chunk 30/50/100 학습 3개 시작
scripts/train.sh status                 # 진행 상황 (step, loss, 남은 시간, 저장된 체크포인트)
```

`train.sh`가 하는 일
1. `datasets/incoming/` 아래 녹화 폴더를 모두 찾아 `check_dataset.py`로 점검: 파일 누락, fps, 카메라, 세션끼리 설정 차이, 에피소드마다 첫/마지막 프레임 디코딩. 하나라도 실패하면 여기서 멈춤
2. 세션 폴더들을 `datasets/so101_tape_basket`으로 합침 (`lerobot-edit-dataset` merge, 영상 재인코딩 없음, 원본은 그대로)
3. 합친 데이터 재점검 + `ep_stats.py`
4. 비어 있는 GPU에 chunk 30 / 50 / 100 학습을 하나씩 백그라운드로 시작 (터미널을 닫아도 계속)

학습 명령 자체는 아래와 같습니다 (chunk마다 하나):
```bash
lerobot-train \
  --dataset.repo_id=local/so101_tape_basket --dataset.root=datasets/so101_tape_basket \
  --policy.type=act --policy.chunk_size=100 --policy.n_action_steps=100 \
  --policy.push_to_hub=false --policy.device=cuda \
  --batch_size=8 --steps=50000 --save_freq=10000 --num_workers=8 \
  --output_dir=outputs/act_c100 --job_name=act_c100 --wandb.enable=false
```
나머지는 LeRobot 0.6.1의 ACT 기본값입니다 (ResNet18 ImageNet 가중치, dim 512, 인코더 4층 / 디코더 1층, VAE, kl_weight 10, AdamW lr 1e-5).

## 3-3. 설정 바꾸기 (환경 변수)

| 변수 | 기본값 | 공개 모델 |
|---|---|---|
| `STEPS` | 100000 | 15개 모델 50000, 30개 모델 100000 |
| `CHUNKS` | `"30 50 100"` | 성공한 모델은 100 |
| `BATCH` | 8 | 8 |
| `SAVE_FREQ` | 10000 | 10000 |
| `INCOMING` | `datasets/incoming` | |
| `DATASET` | `datasets/so101_tape_basket` | |
| `OUT` | `outputs` | |
| `GPUS` | 비어 있는 GPU 자동 | 예: `GPUS="0"` → 세 학습이 GPU 0을 같이 씀 |

공개 모델과 같은 조건 (15개, 50k step):
```bash
STEPS=50000 scripts/train.sh
```
여러 번 학습할 때는 이름을 나눕니다:
```bash
DATASET=datasets/tape_15ep OUT=outputs/tape_15ep STEPS=50000 scripts/train.sh
OUT=outputs/tape_15ep scripts/train.sh status
```

## 3-4. 시간과 결과물

| 데이터 | step | 시간 (A100, 세 개 동시) | 마지막 loss (c30 / c50 / c100) |
|---|---|---|---|
| 15개 (10,537프레임) | 50k | 약 35분 | 0.037 / 0.041 / 0.044 |
| 30개 (20,342프레임) | 100k | 약 70분 | 0.029 / 0.030 / 0.033 |

| 결과물 | 위치 |
|---|---|
| 합친 데이터셋 | `datasets/so101_tape_basket/` |
| 학습 로그 | `outputs/act_c30.log`, `act_c50.log`, `act_c100.log` |
| 점검 기록 | `outputs/dataset_check_<날짜>.md` |
| 체크포인트 | `outputs/act_c<chunk>/checkpoints/<step>/` (10k step마다, 하나에 약 600MB) |
| **로봇 PC로 가져갈 것** | `outputs/act_c<chunk>/checkpoints/<step>/pretrained_model/` (약 200MB) |

`pretrained_model/` 안의 파일 7개가 실행에 필요한 전부입니다 (`config.json`, `model.safetensors`, 정규화 값 파일 등). `training_state/`는 학습을 이어 할 때만 필요합니다.

loss는 학습 데이터를 얼마나 잘 따라 하는지일 뿐이라, 실제 성공 여부는 로봇에서 실행해 봐야 압니다.

## 3-5. 다시 실행할 때

- `datasets/so101_tape_basket`이 이미 있으면 그걸로 학습합니다. 세션을 추가했다면 그 폴더를 지우고 다시 실행합니다.
- 같은 이름의 `outputs/act_c<chunk>/`가 있으면 그 학습은 건너뜁니다 (lerobot-train은 덮어쓰지 않음).
- 이상한 에피소드를 빼려면:
  ```bash
  lerobot-edit-dataset --repo_id local/so101_tape_basket --root datasets/so101_tape_basket \
    --new_repo_id local/so101_tape_basket_b --new_root datasets/so101_tape_basket_b \
    --operation.type delete_episodes --operation.episode_indices "[3, 17]"
  DATASET=datasets/so101_tape_basket_b OUT=outputs/b scripts/train.sh
  ```

## 3-6. 녹화 품질 확인 도구 (선택)

```bash
python scripts/ep_frames.py datasets/so101_tape_basket --out outputs/frames   # 에피소드마다 시작/잡기/끝 장면 + 테이프 위치(px)
python scripts/cam_shift.py datasets/incoming                                 # 세션끼리 카메라 화면이 움직였는지(px)
```
`cam_shift.py`에서 15px 넘게 차이 나는 세션이 있으면 그 사이에 카메라가 움직인 것입니다.

다음: [4. 실행](4_rollout.md)
