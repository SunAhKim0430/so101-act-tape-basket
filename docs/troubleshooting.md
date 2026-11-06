# 문제 해결

이 프로젝트를 하면서 실제로 겪은 문제들입니다 (LeRobot 0.6.1, Windows 노트북).

## 녹화

### `ValueError: You must add one or several frames with add_frame before calling add_episode`로 세션이 끝남
- 원인: 에피소드를 저장하는 동안(약 1분) 누른 `n`이 남아 있다가, 다음 에피소드가 첫 프레임도 찍기 전에 끝나 버림 → 빈 에피소드를 저장하려다 에러. `lerobot-record`는 키를 눌러 두기만 하고 녹화 루프가 다음에 확인하는데, 저장 중에는 루프가 돌지 않기 때문입니다.
- 해결: `4_record.bat`은 `lerobot-record` 대신 `scripts/record.py`를 실행합니다. 에피소드 시작 전에 눌린 `n`/`r`은 무시하고(`q`는 유지), 그래도 빈 에피소드가 생기면 저장하지 않고 다시 녹화합니다.

### 에피소드마다 저장이 1분 가까이 걸리고 화면이 멈춘 것처럼 보임
- 노트북 CPU의 AV1 영상 인코딩입니다 (30초 에피소드 ≈ 56초). 터미널에 `Svt[info]` 줄이 나오면 정상이니 기다립니다. 에피소드가 짧을수록 줄어듭니다.
- `--dataset.video_encoding_batch_size`(끝에 몰아서 인코딩)는 0.6.1에서 새 데이터셋에 쓰면 `TypeError`가 나서 쓰지 않습니다.

### 녹화 창을 닫았더니 그 세션을 못 씀
- 에피소드 정보(`meta/episodes`)는 세션이 끝날 때 한꺼번에 기록됩니다. 녹화 중에는 창을 닫지 말고, 일찍 끝내려면 리셋 시간에 `q`.

### `Record loop is running slower (xx Hz) than the target FPS`가 계속 나옴 (녹화 중)
- 카메라나 CPU가 30fps를 못 따라갑니다. `config.bat`의 `CAM_OPTS` 끝에 `, fourcc: MJPG`를 붙이고 다른 프로그램을 닫습니다. 첫 프레임에서 한 번 나오는 것은 괜찮습니다.

### 녹화한 mp4가 Windows 미디어 플레이어에서 안 열림
- AV1 코덱입니다. VLC로 열거나 Chrome/Edge 창에 끌어다 놓습니다. 또는 Microsoft Store의 "AV1 Video Extension".

### 무시해도 되는 메시지
- `Could not load libtorchcodec ... Falling back to 'pyav'`: Windows에서 영상 읽기 라이브러리 대신 다른 것을 씀. 녹화·실행에 영향 없음
- `re_grpc_server: Exceeded gRPC proxy server memory limit`: rerun 화면이 오래된 기록을 버린다는 안내

## 데이터

### 정지 프레임 비율(`idle fraction`)이 높음
- 대부분 에피소드 시작 직후입니다. `Recording episode` 줄이 뜨면 바로 움직이고, 작업이 끝나면 바로 `n`을 누릅니다. 가만히 있는 구간도 그대로 학습돼서, 실행할 때 처음에 머뭇거리거나 출발하지 않을 수 있습니다.
- 참고: 첫 시도(실패)는 10fps로 60초를 꽉 채워 녹화해서 65%, 이번(성공)은 22~25%.

### 녹화 도중 카메라가 움직임
- `python scripts/cam_shift.py datasets/incoming`으로 세션끼리 화면이 얼마나 밀렸는지(px) 봅니다. 15px 넘게 차이 나면 카메라가 움직인 것입니다.
- 움직인 전후의 녹화를 섞으면 두 화면을 다 배워야 합니다. 카메라 자리를 표시해 두고, 실행도 마지막으로 녹화한 화면에서 합니다.

## 실행

### `[FAIL] ...: missing ['config.json', 'model.safetensors', ...]`
- 모델 파일이 그 폴더 바로 안에 없습니다. VSCode Download는 고른 폴더 **안에** 같은 이름 폴더를 하나 더 만들어서 `so101_models\이름\이름\...`이 되기 쉽습니다. 지금 `5_rollout.bat`은 안쪽 폴더를 찾아서 쓰고, 실패하면 폴더 내용을 보여 줍니다.
- `missing or cut short`면 다운로드가 덜 된 것이니 다시 받습니다.

### `ConnectionError: Failed to write 'Torque_Enable' on id_=5 with '1' after 1 tries. [TxRxResult] Incorrect status packet!`
- 팔로워에 연결할 때 토크를 다시 켜는 명령에 한 모터가 잘못된 응답을 보냄. LeRobot 0.6.1은 이 단계에서 재시도하지 않아 바로 종료됩니다. 우리 경우 **다시 실행하니 됐습니다.**
- 반복되면: 팔로워 전원 어댑터, 해당 모터(id 5 = wrist_roll) 앞뒤 케이블을 다시 꽂기, USB 다시 꽂기, 녹화·조종 창이 열려 있으면 닫기 → `1_check.bat robot`으로 모터 6개 응답 확인

### 동작이 1초마다 멈칫거림
- 모델이 다음 동작을 계산하는 동안(CPU 0.1~0.25초) 제어가 멈추기 때문입니다. `n_action_steps`를 chunk 크기까지 올립니다 (`5_rollout.bat <모델> 100`). [4-4](4_rollout.md#4-4-동작을-부드럽게-하기)

### `No accelerated backend detected` / `Device 'cuda' is not available. Switching to 'cpu'`
- GPU가 없는 노트북에서는 정상입니다. 모델은 CPU로 돕니다.

### 실행이 끝나면 팔에 힘이 빠짐
- 정상입니다. 시작할 때 자세로 천천히 돌아간 뒤 토크를 끕니다. 시작 자세를 힘이 빠져도 쓰러지지 않는 자세로 정합니다.

## 캘리브레이션

### 범위 기록에서 MIN이 0 근처, MAX가 4095 근처
- 첫 단계의 가운데 자세가 그 관절의 실제 가운데에서 크게 벗어나 값이 한 바퀴 넘어간 것입니다. 이 상태로 조종하면 팔이 반대로 크게 돌 수 있습니다. `2_calibrate.bat follower` → `c` + Enter → 가운데 자세를 고쳐서 다시 ([1-4](1_setup.md#1-4-캘리브레이션)).

### `Some motors have the same min and max values`
- 범위 기록 중 움직이지 않은 관절이 있습니다. 모든 관절을 끝까지 움직이고 다시.
