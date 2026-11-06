@echo off
rem Leader -> follower teleoperation. Stop with Ctrl+C.
rem   3_teleoperate.bat          arms only
rem   3_teleoperate.bat camera   arms + camera view on screen (rerun): aim the front camera before recording
rem Put both arms in a similar pose first: the follower jumps to the leader's pose when it starts.
call "%~dp0config.bat"
if /I "%1"=="camera" (
    if "%CAMS%"=="" (
        echo FRONT_CAM is empty in config.bat - connect the camera, run 1_check.bat camera and set FRONT_CAM
        exit /b 1
    )
    lerobot-teleoperate ^
        --robot.type=so101_follower --robot.port=%FOLLOWER_PORT% --robot.id=%FOLLOWER_ID% ^
        --robot.cameras="{ %CAMS% }" ^
        --teleop.type=so101_leader --teleop.port=%LEADER_PORT% --teleop.id=%LEADER_ID% ^
        --fps=%FPS% --display_data=true
) else (
    lerobot-teleoperate ^
        --robot.type=so101_follower --robot.port=%FOLLOWER_PORT% --robot.id=%FOLLOWER_ID% ^
        --teleop.type=so101_leader --teleop.port=%LEADER_PORT% --teleop.id=%LEADER_ID%
)
