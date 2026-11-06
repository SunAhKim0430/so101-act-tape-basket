@echo off
rem Run a trained model on the follower arm (the leader is not used). Ctrl+C stops it early.
rem   5_rollout.bat                        list the models in %MODEL_DIR%
rem   5_rollout.bat act_so101_tape_15ep_c100_050000        run that model for ROLLOUT_S seconds (config.bat)
rem   5_rollout.bat act_so101_tape_15ep_c100_050000 50     n_action_steps 50 = new prediction every 1.7 s
rem Model folder = a release zip extracted into MODEL_DIR, or outputs\act_c<chunk>\checkpoints\<step>\pretrained_model
rem from your own training (the files may sit one or two folders further in).
rem At the end (or after Ctrl+C) the arm moves back to where it started, then its torque goes off: start from a resting pose.
rem Emergency: unplug the follower's power adapter.
setlocal
call "%~dp0config.bat"

if "%~1"=="" (
    echo Models in %MODEL_DIR%:
    dir /b /ad "%MODEL_DIR%" 2>nul || echo   none - extract a release zip or copy a pretrained_model folder there
    echo.
    echo Usage: 5_rollout.bat ^<model folder name^> [n_action_steps]
    exit /b 1
)
if "%CAMS%"=="" (
    echo FRONT_CAM is empty in config.bat - connect the camera, run 1_check.bat camera and set FRONT_CAM
    exit /b 1
)

set "MODEL=%MODEL_DIR%\%~1"
if exist "%~1\config.json" set "MODEL=%~1"
if exist "%~1\pretrained_model\config.json" set "MODEL=%~1"
if exist "%MODEL%\pretrained_model\config.json" set "MODEL=%MODEL%\pretrained_model"
rem Model files one or more folders further in (VSCode Download into a folder of the same name): use that folder
set "FOUND="
if not exist "%MODEL%\config.json" if exist "%MODEL%\" (
    for /r "%MODEL%" %%F in (config.json) do if exist "%%F" set "FOUND=%%~dpF"
)
if defined FOUND set "MODEL=%FOUND:~0,-1%"
echo   model   : %MODEL%
set N=%N_ACTION_STEPS%
if "%N%"=="" for /f "usebackq delims=" %%c in (`python -c "import json,sys; print(json.load(open(sys.argv[1]))['chunk_size'])" "%MODEL%\config.json"`) do set "N=%%c"
if "%N%"=="" set N=30
if not "%~2"=="" set N=%~2

python "%~dp0..\check_model.py" "%MODEL%" --cameras %CAM_NAMES% --n-action-steps %N% --fps %FPS%
if errorlevel 1 exit /b 1
echo   arm     : %FOLLOWER_PORT% / %FOLLOWER_ID%
echo   cameras : %CAMS%
echo   run     : %ROLLOUT_S% s, at most %MAX_STEP_DEG% deg per step
echo.
echo Follower in the start pose, tape on its mark, nothing else in reach, a hand near the power adapter.
set /p "_=Press Enter to start (Ctrl+C to cancel) "

lerobot-rollout ^
    --strategy.type=base ^
    --policy.path="%MODEL%" ^
    --policy.n_action_steps=%N% ^
    --robot.type=so101_follower --robot.port=%FOLLOWER_PORT% --robot.id=%FOLLOWER_ID% ^
    --robot.cameras="{ %CAMS% }" ^
    --robot.max_relative_target=%MAX_STEP_DEG% ^
    --fps=%FPS% ^
    --task="%TASK%" ^
    --duration=%ROLLOUT_S% ^
    --display_data=%ROLLOUT_DISPLAY%
if errorlevel 1 (
    echo.
    echo [FAIL] lerobot-rollout stopped with an error - see the messages above
    exit /b 1
)
echo.
echo Done. Write down: model, n_action_steps, tape spot, success or how it failed.
