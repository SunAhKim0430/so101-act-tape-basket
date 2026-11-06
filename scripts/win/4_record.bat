@echo off
rem Record episodes (leader -> follower + cameras). Every run makes a new folder, train.sh merges them.
rem   4_record.bat test            3 test episodes                          -> %DATA_DIR%\pilot\test_<time>
rem   4_record.bat main pos1       MAIN_EPISODES (5) with the tape at spot 1 -> %DATA_DIR%\main\pos1_<time>
rem   4_record.bat main pos1 4     4 more episodes at spot 1 (e.g. after stopping early)
rem Run it again for more at the same spot (pos1 x 4 = 20). Same start pose, basket and camera every time.
rem Keys: n = task done -> reset time -> next   r = redo this episode   q = stop early (press it in the reset time:
rem       q while an episode is running saves that unfinished episode). The session ends by itself after the last
rem       episode. Never close the window: episode info is written at the end, the whole folder would be lost.
rem Runs lerobot-record through ..\record.py: keys pressed while an episode is being saved are ignored
rem (with plain lerobot-record a stray n there ends the next episode with no frame and stops the whole session).
setlocal
call "%~dp0config.bat"

if /I "%1"=="test" (
    set KIND=pilot
    set NAME=test
    set EPISODES=3
    set UPLOAD=datasets/pilot/
) else if /I "%1"=="main" (
    if "%2"=="" goto :usage
    set KIND=main
    set NAME=%2
    set EPISODES=%MAIN_EPISODES%
    if not "%3"=="" set EPISODES=%3
    set UPLOAD=datasets/incoming/
) else (
    goto :usage
)

if "%CAMS%"=="" (
    echo FRONT_CAM is empty in config.bat - connect the camera, run 1_check.bat camera and set FRONT_CAM
    exit /b 1
)

set STAMP=
for /f %%t in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set STAMP=%%t
if "%STAMP%"=="" set STAMP=%RANDOM%
set "ROOT=%DATA_DIR%\%KIND%\%NAME%_%STAMP%"

echo Recording %EPISODES% episode(s), %EPISODE_TIME_S% s max each, %RESET_TIME_S% s reset in between
echo   folder : %ROOT%
echo   cameras: %CAMS%
echo   keys   : n = done/next   r = redo   q = stop early, in the reset time. Keys work in every window - don't type elsewhere.
echo   after each reset the episode is saved: about 1 min, Svt[info] lines. Wait for "Recording episode" before moving.
echo   ends by itself after the last episode. Never close this window.
echo.
python "%~dp0..\record.py" ^
    --robot.type=so101_follower --robot.port=%FOLLOWER_PORT% --robot.id=%FOLLOWER_ID% ^
    --robot.cameras="{ %CAMS% }" ^
    --teleop.type=so101_leader --teleop.port=%LEADER_PORT% --teleop.id=%LEADER_ID% ^
    --dataset.repo_id=local/so101_tape_basket ^
    --dataset.root="%ROOT%" ^
    --dataset.single_task="%TASK%" ^
    --dataset.fps=%FPS% ^
    --dataset.num_episodes=%EPISODES% ^
    --dataset.episode_time_s=%EPISODE_TIME_S% ^
    --dataset.reset_time_s=%RESET_TIME_S% ^
    --dataset.push_to_hub=false ^
    --display_data=true
set RC=%errorlevel%
rem Nothing recorded, e.g. a port or camera error before the first episode: remove the folder that only has meta\info.json
if not exist "%ROOT%\data" (
    if exist "%ROOT%" rmdir /s /q "%ROOT%"
    echo.
    echo [FAIL] no episode was saved - see the messages above
    exit /b 1
)
if not "%RC%"=="0" (
    echo.
    echo [WARN] recording stopped with an error - the episodes saved before it are kept
)
echo.
python "%~dp0..\ep_stats.py" "%ROOT%"
echo.
echo Saved: %ROOT%
echo Copy this whole folder into %UPLOAD% of this repo on the training PC (GPU)
exit /b 0

:usage
echo Usage: 4_record.bat test            (3 test episodes)
echo        4_record.bat main pos1       (%MAIN_EPISODES% episodes, tape at spot 1; then pos2 ... pos5)
echo        4_record.bat main pos1 4     (4 episodes)
exit /b 1
