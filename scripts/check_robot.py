#!/usr/bin/env python
r"""SO-101 leader/follower connection check - run this on the PC the arms are plugged into.

Read-only: it opens each USB serial port, pings the Feetech motors and reads registers.
It never enables/disables torque or writes calibration.

    python check_robot.py
    python check_robot.py --follower-id my_so101_follower --leader-id my_so101_leader
    win\1_check.bat robot    (Windows: reads ports/ids from win\config.bat)
"""

import argparse
import json
import os
import platform
import sys

from serial.tools import list_ports

from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus
from lerobot.utils.constants import HF_LEROBOT_CALIBRATION, ROBOTS, TELEOPERATORS

MOTOR_NAMES = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
STS3215_MODEL_NB = 777


def make_bus(port: str) -> FeetechMotorsBus:
    motors = {name: Motor(i + 1, "sts3215", MotorNormMode.RANGE_M100_100) for i, name in enumerate(MOTOR_NAMES)}
    return FeetechMotorsBus(port=port, motors=motors)


def load_calibration(kind: str, name: str, arm_id: str) -> dict | None:
    fpath = HF_LEROBOT_CALIBRATION / kind / name / f"{arm_id}.json"
    if not fpath.is_file():
        return None
    with open(fpath) as f:
        return json.load(f)


def wrapped_joints(calib: dict | None) -> list[str]:
    """Joints whose recorded range runs into 0 / 4095: the position wrapped around during calibration
    because the 'middle' pose was too far from the real middle. Their angle jumps by 360 deg."""
    if not calib:
        return []
    return [m for m, c in calib.items() if m != "wrist_roll" and (c["range_min"] < 100 or c["range_max"] > 3995)]


def check_port(port: str) -> dict | None:
    """Ping and read one port. Returns None if no Feetech motors answer."""
    if platform.system() != "Windows" and not os.access(port, os.R_OK | os.W_OK):
        print(f"  [FAIL] no read/write permission on {port} (add yourself to the 'dialout' group, then re-login)")
        return None

    bus = make_bus(port)
    try:
        bus.connect(handshake=False)
    except ConnectionError as e:
        print(f"  [FAIL] cannot open {port}: {e}")
        return None

    try:
        found = bus.broadcast_ping(num_retry=2) or {}
        if not found:
            print("  no Feetech motors answered (wrong port, arm power off, or not an arm)")
            return None

        id_to_name = {i + 1: name for i, name in enumerate(MOTOR_NAMES)}
        missing = [f"{i}:{id_to_name[i]}" for i in id_to_name if i not in found]
        unknown = [i for i in found if i not in id_to_name]
        wrong_model = [i for i, nb in found.items() if i in id_to_name and nb != STS3215_MODEL_NB]

        print(f"  motors found : {sorted(found)}")
        if missing:
            print(f"  [FAIL] missing motor ids: {missing} (check daisy-chain cables / that motor's connector)")
        if unknown:
            print(f"  [WARN] unexpected motor ids: {unknown} (motor ids not set with lerobot-setup-motors?)")
        if wrong_model:
            print(f"  [WARN] non-STS3215 model on ids: {wrong_model}")

        print(f"  {'motor':<14}{'pos(raw)':>9}{'volt':>7}{'temp':>6}")
        state = {}
        for i, name in id_to_name.items():
            if i not in found:
                continue
            pos = bus.read("Present_Position", name, normalize=False)
            volt = bus.read("Present_Voltage", name, normalize=False) / 10
            temp = bus.read("Present_Temperature", name, normalize=False)
            state[name] = (pos, volt, temp)
            print(f"  {name:<14}{pos:>9}{volt:>6.1f}V{temp:>4}C")

        volts = [v for _, v, _ in state.values()]
        if volts and min(volts) < 4.5:
            print(f"  [WARN] low supply voltage ({min(volts):.1f}V) - is the arm's power adapter plugged in?")
        if any(t >= 60 for _, _, t in state.values()):
            print("  [WARN] a motor is at 60C or hotter - let it cool down")

        on_motors = {}
        for i, name in id_to_name.items():
            if i in found:
                on_motors[name] = {
                    "homing_offset": bus.read("Homing_Offset", name, normalize=False),
                    "range_min": bus.read("Min_Position_Limit", name, normalize=False),
                    "range_max": bus.read("Max_Position_Limit", name, normalize=False),
                }
        return {"found": found, "missing": missing, "calibration": on_motors}
    finally:
        bus.disconnect(disable_torque=False)


def calibration_matches(on_motors: dict, calib_file: dict | None) -> bool:
    if not calib_file:
        return False
    return all(
        name in calib_file
        and all(int(calib_file[name][key]) == int(value) for key, value in regs.items())
        for name, regs in on_motors.items()
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--follower-id", default="my_so101_follower")
    parser.add_argument("--leader-id", default="my_so101_leader")
    args = parser.parse_args()

    follower_calib = load_calibration(ROBOTS, "so_follower", args.follower_id)
    leader_calib = load_calibration(TELEOPERATORS, "so_leader", args.leader_id)
    print(f"calibration dir : {HF_LEROBOT_CALIBRATION}")
    print(f"follower '{args.follower_id}' calibration file: {'found' if follower_calib else 'NOT FOUND'}")
    print(f"leader   '{args.leader_id}' calibration file: {'found' if leader_calib else 'NOT FOUND'}")
    for label, calib in (("follower", follower_calib), ("leader", leader_calib)):
        if wrapped := wrapped_joints(calib):
            print(f"  [WARN] {label} calibration: {wrapped} range reaches 0/4095 (wrapped) - recalibrate")
    if not (follower_calib and leader_calib):
        existing = sorted(p.relative_to(HF_LEROBOT_CALIBRATION) for p in HF_LEROBOT_CALIBRATION.glob("*/*/*.json"))
        print(f"  existing calibration files: {[str(p) for p in existing] or 'none'}")

    ports = [p for p in list_ports.comports() if p.vid is not None]  # USB serial devices only
    if not ports:
        print("\n[FAIL] no USB serial ports found. Check the USB cables (and that this is the PC the arms are on).")
        sys.exit(1)

    results = {}
    for p in ports:
        print(f"\n=== {p.device}  ({p.description}, serial={p.serial_number})")
        res = check_port(p.device)
        if res:
            results[p.device] = res

    print("\n=== summary")
    roles = {}
    for port, res in results.items():
        if calibration_matches(res["calibration"], follower_calib):
            roles[port] = "FOLLOWER"
        elif calibration_matches(res["calibration"], leader_calib):
            roles[port] = "LEADER"
        else:
            roles[port] = "unknown (calibration on motors doesn't match either file)"
        status = "OK" if not res["missing"] else f"missing {res['missing']}"
        print(f"  {port}: {roles[port]:<10} motors {status}")

    if len(results) < 2:
        print(f"  [FAIL] expected 2 arms, found {len(results)}")
        print("         Is the other arm's USB plugged in and its power on? If Device Manager shows no new COM port")
        print("         for it, try another cable/port; a device under 'Other devices' needs the CH343/CH340 driver.")
    for role in ("FOLLOWER", "LEADER"):
        if role not in roles.values():
            print(f"  [WARN] no port matched the {role.lower()} calibration - recalibrate or check the --*-id value")
    print("\nNext: lerobot-teleoperate with these ports to check that the follower tracks the leader.")


if __name__ == "__main__":
    main()
