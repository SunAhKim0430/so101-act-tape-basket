@echo off
rem SO-101 settings - every win\*.bat reads this file. Edit only here.

rem Arm ports: Device Manager > Ports (COM & LPT), or run lerobot-find-port
rem Example values - replace them with the COM numbers of your arms
set FOLLOWER_PORT=COM8
set LEADER_PORT=COM7

rem Calibration ids - keep these the same from calibration through recording and rollout
set FOLLOWER_ID=my_so101_follower
set LEADER_ID=my_so101_leader

rem Camera indexes: run 1_check.bat camera and look at the snapshots. 0 is usually the laptop webcam (don't use it).
rem This project uses one fixed front camera. Fill WRIST_CAM only if you add a wrist camera (then record and run with it).
set FRONT_CAM=1
set WRIST_CAM=

rem Settings shared by every camera. If fps drops with two cameras, add ", fourcc: MJPG" at the end
set FPS=30
set CAM_OPTS=width: 640, height: 480, fps: %FPS%

rem Recording (4_record.bat). Recordings go outside scripts\, so copying new scripts never touches them
set DATA_DIR=%USERPROFILE%\so101_data
set TASK=Grab the yellow tape and put in the basket
set MAIN_EPISODES=5
set EPISODE_TIME_S=30
rem Reset time is not recorded and n ends it early: long enough to put the tape back, then press n
set RESET_TIME_S=60

rem Rollout (5_rollout.bat). One folder per model (a release zip, or pretrained_model from your training) in MODEL_DIR
set MODEL_DIR=%USERPROFILE%\so101_models
set ROLLOUT_S=40
rem Actions run per prediction, at most the model's chunk_size. Empty = the model's chunk_size (demo: chunk 100 -> 100,
rem a new prediction every 3.3 s). Smaller = reacts sooner but pauses more often (each prediction takes ~0.1-0.25 s on CPU)
set N_ACTION_STEPS=
rem Safety: max joint move per control step, in degrees. 10 at 30 fps = 300 deg/s
set MAX_STEP_DEG=10
rem Camera view during rollout. Set false if the laptop is too slow (loop slower than 30 Hz warnings)
set ROLLOUT_DISPLAY=true

rem --- built from the values above, do not edit ---
set "CAMS="
if not "%FRONT_CAM%"=="" set "CAMS=front: {type: opencv, index_or_path: %FRONT_CAM%, %CAM_OPTS%}"
if not "%FRONT_CAM%"=="" if not "%WRIST_CAM%"=="" set "CAMS=%CAMS%, wrist: {type: opencv, index_or_path: %WRIST_CAM%, %CAM_OPTS%}"
set "CAM_NAMES="
if not "%FRONT_CAM%"=="" set "CAM_NAMES=front"
if not "%FRONT_CAM%"=="" if not "%WRIST_CAM%"=="" set "CAM_NAMES=front,wrist"
