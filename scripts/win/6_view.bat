@echo off
rem Watch a recording: camera video + joint values of one episode in a rerun window (lerobot-dataset-viz).
rem   6_view.bat                                 list the recorded folders
rem   6_view.bat main\pos1_20261106_101500       episode 0 of that session
rem   6_view.bat main\pos1_20261106_101500 3     episode 3
rem Just the video: <folder>\videos\observation.images.front\chunk-000\file-000.mp4 holds every episode of the
rem session back to back (ep_stats.py prints where each one is). It is AV1: plays in VLC, or drag it into Chrome / Edge.
setlocal
call "%~dp0config.bat"

if "%~1"=="" (
    echo Recordings in %DATA_DIR%:
    for /d %%d in ("%DATA_DIR%\pilot\*") do echo   pilot\%%~nxd
    for /d %%d in ("%DATA_DIR%\main\*") do echo   main\%%~nxd
    echo.
    echo Usage: 6_view.bat ^<folder^> [episode]    e.g. 6_view.bat main\pos1_20261106_101500 3
    exit /b 1
)
set "ROOT=%DATA_DIR%\%~1"
if exist "%~1\meta\info.json" set "ROOT=%~1"
if not exist "%ROOT%\meta\info.json" (
    echo No recording at %ROOT% - run 6_view.bat without arguments for the list
    exit /b 1
)
set EP=0
if not "%~2"=="" set EP=%~2

python "%~dp0..\ep_stats.py" "%ROOT%"
echo.
echo Opening episode %EP% in a rerun window ...
set HF_HUB_OFFLINE=1
lerobot-dataset-viz --repo-id local/view --root "%ROOT%" --episode-index %EP% --num-workers 0
