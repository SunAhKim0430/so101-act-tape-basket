@echo off
rem Usage: 2_calibrate.bat follower   or   2_calibrate.bat leader
call "%~dp0config.bat"
if /I "%1"=="follower" (
    lerobot-calibrate --robot.type=so101_follower --robot.port=%FOLLOWER_PORT% --robot.id=%FOLLOWER_ID%
) else if /I "%1"=="leader" (
    lerobot-calibrate --teleop.type=so101_leader --teleop.port=%LEADER_PORT% --teleop.id=%LEADER_ID%
) else (
    echo Usage: 2_calibrate.bat follower ^| leader
)
