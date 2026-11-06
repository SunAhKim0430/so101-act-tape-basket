@echo off
rem Read-only checks. Usage: 1_check.bat          (arms + cameras)
rem                          1_check.bat robot    (arms only)
rem                          1_check.bat camera   (cameras only)
rem                          1_check.bat motion   (move joints by hand: does every motor's position follow?)
call "%~dp0config.bat"
if /I "%1"=="motion" (
    python "%~dp0..\check_motion.py" --leader %LEADER_PORT% --follower %FOLLOWER_PORT%
    goto :eof
)
if /I not "%1"=="camera" (
    echo ===== ARMS =====
    python "%~dp0..\check_robot.py" --follower-id %FOLLOWER_ID% --leader-id %LEADER_ID%
    echo.
)
if /I not "%1"=="robot" (
    echo ===== CAMERAS =====
    python "%~dp0..\check_cameras.py" --out "%~dp0..\camera_check"
)
