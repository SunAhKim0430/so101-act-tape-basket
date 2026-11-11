# 1. 설치 · 팔 점검 · 캘리브레이션 · 카메라

로봇 PC(Windows)에서 합니다. 모든 `.bat`은 `scripts\win\config.bat` 한 곳의 값을 읽습니다.

## 1-1. 설치 (Windows)

1. Miniforge 설치: https://github.com/conda-forge/miniforge/releases/latest → `Miniforge3-Windows-x86_64.exe` (기본 옵션)
2. 시작 메뉴 › **Miniforge Prompt**에서
   ```bat
   conda create -y -n lerobot python=3.12
   conda activate lerobot
   conda install -y ffmpeg -c conda-forge
   pip install "lerobot[feetech,core_scripts]==0.6.1"
   ```
   - `feetech`: SO-101 모터, `core_scripts`: 녹화·재생·캘리브레이션에 필요한 데이터셋, 키보드 입력(n/r/q), 화면 표시(rerun)
   - **0.6.1로 고정**합니다. 이 저장소의 스크립트는 0.6.1 코드 기준입니다.
3. 확인
   ```bat
   pip show lerobot
   python -c "import scservo_sdk, serial, cv2, pynput, rerun; print('ok')"
   ```
4. 이 저장소 받기: `git clone https://github.com/SunAhKim0430/so101-act-tape-basket` (또는 Download ZIP)

이후 매번:
```bat
conda activate lerobot
cd <저장소 위치>\scripts\win
```
- PowerShell을 쓰면 처음 한 번 `conda init powershell`, 실행할 때 `.\1_check.bat`처럼 `.\`를 붙입니다.
- VSCode의 원격(SSH) 터미널은 원격 컴퓨터에서 돌아서 로봇이 보이지 않습니다. 로봇 PC의 로컬 터미널에서 실행합니다.
- pip로 받는 Windows용 PyTorch는 CPU 버전입니다. 녹화와 실행에는 충분합니다 (학습은 GPU PC에서).

## 1-2. 하드웨어 연결

- 리더·팔로워 각각 전원 어댑터 연결. **팔로워 전압은 모터 사양에 맞게** (7.4V 모터 → 5V 어댑터, 12V 모터 → 12V 어댑터)
- 두 팔과 카메라를 USB로 연결. 노트북 USB 포트가 모자라면 USB 3.0 허브(전원 공급형 권장): 팔 두 개는 허브에, 카메라는 노트북에 직접
- 두 팔의 베이스를 C-클램프로 책상에 고정
- 장치 관리자 › 포트(COM & LPT)에서 COM 번호 2개 확인 (또는 `lerobot-find-port`) → `config.bat`의 `FOLLOWER_PORT`, `LEADER_PORT`

## 1-3. 팔 점검

```bat
1_check.bat robot
```
- 포트마다 모터 1\~6이 응답하는지, 전압·온도를 보여 줍니다. 읽기만 하고 토크나 캘리브레이션은 건드리지 않습니다.
- 모터에 저장된 값으로 어느 포트가 리더/팔로워인지 알려 줍니다. `config.bat`의 포트가 반대면 바꿉니다.

```bat
1_check.bat motion
```
- 손으로 관절을 하나씩 움직여 12개 모터 값이 모두 따라오는지 확인합니다.

## 1-4. 캘리브레이션

```bat
2_calibrate.bat follower
2_calibrate.bat leader
```
캘리브레이션 파일은 `config.bat`의 `FOLLOWER_ID`, `LEADER_ID` 이름으로 저장됩니다. **녹화부터 실행까지 같은 id를 씁니다.**

주의 (LeRobot 0.6.1, 각도 단위)
1. 처음 단계(가운데 자세)에서 관절 각도 0°가 정해집니다. 위팔은 세우고, 아래팔은 앞으로 수평, 손목은 아래팔과 일직선, 그리퍼는 반쯤 열기. 토크가 꺼져 팔이 처지니 아래팔 밑을 상자 등으로 받칩니다.
2. 범위 기록 단계에서는 관절마다 양 끝까지 확실히 움직입니다. 관절 각도 0°가 범위의 가운데로 다시 잡힙니다.
3. 범위 기록 중 어느 관절의 MIN이 0 근처, MAX가 4095 근처로 가면 가운데 자세가 잘못된 것입니다. Ctrl+C 후 다시 합니다. 정상 예: MIN 수백 \~ MAX 3000대.
4. `wrist_roll`은 범위를 기록하지 않고 처음 자세의 방향이 0°가 됩니다. **두 팔의 손목 방향을 같게** 맞춥니다.
5. 다시 할 때 "Press ENTER to use provided calibration file ... or type 'c'"가 나오면 `c` + Enter (그냥 Enter면 기존 값을 다시 씀).
6. 관절 하나라도 안 움직이고 Enter를 누르면 `Some motors have the same min and max values` → 다시 실행.
7. **녹화를 시작한 뒤에는 다시 캘리브레이션하지 않습니다.** 값이 바뀌면 녹화 데이터와 실행이 어긋납니다.

조종해 보기:
```bat
3_teleoperate.bat
```
- 시작 전에 두 팔을 비슷한 자세로 둡니다 (팔로워가 시작하자마자 리더 자세로 움직임). 종료는 Ctrl+C.
- 팔로워가 리더를 부드럽게 따라오고 관절 방향이 같은지 봅니다.

## 1-5. 카메라

```bat
1_check.bat camera
```
- 연결된 카메라를 모두 640×480 @ 30fps로 열어 실제 fps를 재고, `scripts\camera_check\camera_<번호>.jpg` 스냅샷을 저장합니다.
- 스냅샷을 보고 고정 카메라 번호를 `config.bat`의 `FRONT_CAM`에 적습니다. 노트북 내장 웹캠(보통 0번)은 쓰지 않습니다.

배치 (가장 중요)
- 앞쪽 위에서 **약 45°로 내려다보게**. 정면 수평이면 앞뒤 거리를 알기 어렵습니다.
- 한 화면에 **테이프 자리 + 바구니 + 그리퍼 움직임 전체**가 들어오게. 예시: [media/example_episode.mp4](../media/example_episode.mp4)
- 클램프 암이나 삼각대로 고정하고, 카메라와 거치대 자리를 테이프로 표시합니다. **녹화부터 실행까지 절대 움직이지 않습니다.** 우리는 녹화 도중 한 번 움직여서 그 전후 화면이 달라졌습니다.
- 조명을 일정하게 (스탠드 조명, 창문 햇빛 피하기). 조작자 손·몸과 지나가는 사람이 화면에 찍히지 않게.
- 기준: "카메라 화면만 보고 내가 이 작업을 할 수 있는가"

화면을 보며 카메라 맞추기:
```bat
3_teleoperate.bat camera
```

## 1-6. 작업 공간

- 매번 같은 노란 테이프, 같은 바구니, 같은 바구니 위치
- 마스킹 테이프로 표시: 테이프 자리, 바구니 자리, 카메라 거치대 자리
- 시작 자세를 하나로 정합니다. 우리는 팔을 접어서 세운 자세를 썼습니다 (예시 영상 처음과 끝). 실행이 끝나면 팔이 이 자세로 돌아간 뒤 힘이 빠지므로, 힘이 빠져도 쓰러지지 않는 자세가 안전합니다.

다음: [2. 녹화](2_record.md)
