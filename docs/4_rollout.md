# 4. 실행 (rollout)

학습한 모델이 리더 대신 팔로워를 움직입니다. 로봇 PC에서 하고, 리더는 쓰지 않습니다 (꽂혀 있어도 됨).
rollout은 학습이 아닙니다. 실행해도 모델은 바뀌지 않습니다.

## 4-1. 모델 가져오기

모델 폴더를 `%USERPROFILE%\so101_models\<이름>\`에 둡니다. 폴더 이름이 실행할 때 쓰는 이름입니다.

- **공개 모델**: [Releases](https://github.com/SunAhKim0430/so101-act-tape-basket/releases/tag/v1.0)의 zip
  ```bat
  mkdir %USERPROFILE%\so101_models
  curl -L -o %TEMP%\model.zip https://github.com/SunAhKim0430/so101-act-tape-basket/releases/download/v1.0/act_so101_tape_15ep_c100_050000.zip
  tar -xf %TEMP%\model.zip -C %USERPROFILE%\so101_models
  ```
- **직접 학습한 모델**: 학습 PC의 `outputs/act_c<chunk>/checkpoints/<step>/pretrained_model/` 폴더를 통째로 복사해서 `so101_models\<이름>\`으로
  - VSCode Remote-SSH 탐색기의 Download는 고른 폴더 **안에** 폴더를 하나 더 만듭니다. 저장 위치로 `so101_models` 자체를 고릅니다. 한 겹 더 들어가도 `5_rollout.bat`이 찾아 줍니다.

## 4-2. 실행

1. 팔로워를 녹화 때의 시작 자세에, 테이프를 녹화 때 자리에 둡니다. 카메라·바구니·조명은 녹화 때 그대로.
2. 팔이 닿는 곳에 다른 물건이나 손이 없게 하고, 한 손은 팔로워 전원 어댑터 근처에 둡니다.
3. 실행
   ```bat
   5_rollout.bat                                        가져온 모델 목록
   5_rollout.bat act_so101_tape_15ep_c100_050000 100    40초 실행, 100스텝(3.3초)마다 새로 예측 ← 시연 성공 설정
   5_rollout.bat act_so101_tape_15ep_c100_050000 50     1.7초마다 새로 예측
   ```
4. 진행: 모델 점검(`[OK] model fits the rollout settings`) → `Press Enter to start` → Enter → 팔로워·카메라 연결 → 40초 동안 모델이 움직임 → 시작할 때 자세로 천천히 돌아간 뒤 **토크가 꺼져 팔에 힘이 빠짐**
5. 일찍 멈추기: Ctrl+C → 시작 자세로 돌아간 뒤 멈춤 ("일괄 작업을 끝내시겠습니까"에는 Y). **비상시에는 팔로워 전원 어댑터를 뽑습니다.**

`5_rollout.bat`이 실행 전에 `check_model.py`로 확인하는 것: 모델 파일이 다 있는지(덜 받은 파일 포함), 모델이 학습한 카메라 이름과 `config.bat`의 카메라가 같은지, `n_action_steps`가 1\~chunk_size인지.

처음 실행할 때 ResNet18 가중치(45MB)를 인터넷에서 한 번 받습니다.

## 4-3. 설정 (`config.bat`)

| 항목 | 값 | 의미 |
|---|---|---|
| `ROLLOUT_S` | 40 | 실행 시간(초) |
| `N_ACTION_STEPS` | 비어 있음 | 예측 한 번에 실행할 동작 수. 비어 있으면 모델의 chunk_size. 명령 뒤 숫자가 우선 |
| `MAX_STEP_DEG` | 10 | 한 스텝(1/30초)에 관절이 움직일 수 있는 최대 각도 (= 초당 300°). 안전 제한 |
| `ROLLOUT_DISPLAY` | true | 카메라 화면 표시. 노트북이 느리면 false |

## 4-4. 동작을 부드럽게 하기

`lerobot-rollout`은 모델이 다음 동작들을 계산하는 동안 팔 제어를 멈춥니다. CPU에서는 한 번 계산에 0.1\~0.25초가 걸려서(서버 CPU 측정, 스레드 8/4/2개 = 86/136/237ms) 30fps 기준 3\~7스텝 동안 팔이 멈춥니다.

| 방법 | 효과 | 비고 |
|---|---|---|
| `n_action_steps`를 chunk_size까지 (c100 → `100`) | 멈칫이 3.3초에 한 번 | **시연 성공 설정.** 대신 중간에 상황이 바뀌어도 늦게 반응 |
| `n_action_steps` 30 | 1초마다 멈칫 | 반응은 빠름 |
| ACT temporal ensembling (`--policy.temporal_ensemble_coeff=0.01 --policy.n_action_steps=1`) | 가장 부드러움 | 매 스텝 예측 → CPU로는 3\~7배 느려져서 안 씀. GPU 있는 PC라면 시도해 볼 만함 |

터미널에 `Record loop is running slower (… Hz)` 경고가 예측할 때마다 한 번씩 나오는 것은 이 멈춤 때문입니다. 계속 나오면 `ROLLOUT_DISPLAY=false`.

## 4-5. 모델 비교 방법

같은 자리에서 모델마다 5번씩 실행해 성공 횟수를 셉니다. chunk 30 / 50 / 100을 먼저 비교하고, 좋은 쪽에서 체크포인트(50k, 100k)와 `n_action_steps`를 바꿔 봅니다.

## 4-6. Linux / macOS에서 (bat 없이)

`5_rollout.bat`이 실행하는 명령입니다. 포트·id·카메라 번호를 바꿔서 씁니다.

```bash
lerobot-rollout \
  --strategy.type=base \
  --policy.path=$HOME/so101_models/act_so101_tape_15ep_c100_050000 \
  --policy.n_action_steps=100 \
  --robot.type=so101_follower --robot.port=/dev/ttyACM0 --robot.id=my_so101_follower \
  --robot.cameras="{ front: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30} }" \
  --robot.max_relative_target=10 \
  --fps=30 --task="Grab the yellow tape and put in the basket" --duration=40 --display_data=true
```
- 카메라 이름은 반드시 `front` (모델이 `observation.images.front`로 학습함)
- 녹화도 같은 방식으로 `python scripts/record.py <lerobot-record 인자>` (`4_record.bat` 참고)
