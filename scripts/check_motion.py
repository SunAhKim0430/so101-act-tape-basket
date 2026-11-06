#!/usr/bin/env python
r"""Hand-move test - checks that every joint actually turns and its motor's position sensor follows.

check_robot.py only proves the motors answer on the bus. Here you move each joint by hand while the
positions are read live; a joint passes once its raw position has changed by --min-travel.
Stops when every joint of every connected arm has passed, or when you press Enter.

Nothing is written to the motors, except: if torque is on (arm stiff), it asks before turning it off.
The follower's powered movement is checked afterwards with 3_teleoperate.bat (needs calibration).

    python check_motion.py --leader COM7 --follower COM8
    win\1_check.bat motion     (Windows: reads ports from win\config.bat)
"""

import argparse
import sys
import time

from serial.tools import list_ports

from lerobot.utils.utils import enter_pressed

from check_robot import MOTOR_NAMES, make_bus


def connect_arms(ports: dict[str, str]) -> dict:
    present = {p.device for p in list_ports.comports()}
    buses = {}
    for role, port in ports.items():
        label = f"{role} {port}"
        if port not in present:
            print(f"{label}: not connected - skipped")
            continue
        bus = make_bus(port)
        try:
            bus.connect()  # handshake: all 6 motors must answer
        except Exception as e:
            print(f"{label}: [FAIL] {e}")
            continue

        torque_on = [m for m, v in bus.sync_read("Torque_Enable", num_retry=2).items() if v]
        if torque_on:
            print(f"{label}: torque is ON for {torque_on} - those joints can't be moved by hand.")
            answer = input("  Turn torque off? HOLD THE ARM FIRST, it goes limp. [Enter = yes / n = skip this arm] ")
            if answer.strip().lower() == "n":
                bus.disconnect(disable_torque=False)
                continue
            bus.disable_torque()
        buses[label] = bus
    return buses


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--leader", help="leader port, e.g. COM7")
    parser.add_argument("--follower", help="follower port, e.g. COM8")
    parser.add_argument("--min-travel", type=int, default=300, help="raw steps a joint must move to pass (4096 = 1 turn)")
    args = parser.parse_args()

    ports = {role: port for role, port in (("leader", args.leader), ("follower", args.follower)) if port}
    buses = connect_arms(ports)
    if not buses:
        print("[FAIL] no arm to test. Check the USB cable / port numbers in win\\config.bat.")
        sys.exit(1)

    try:
        lo, hi, passed, read_errors = {}, {}, {k: set() for k in buses}, {k: 0 for k in buses}
        for k, bus in buses.items():
            pos = bus.sync_read("Present_Position", normalize=False, num_retry=2)
            lo[k], hi[k] = dict(pos), dict(pos)

        print(f"\nMove every joint of {list(buses)} by hand, one at a time, through a good part of its range.")
        print(f"A joint passes after moving {args.min_travel} raw steps (~{args.min_travel * 360 // 4096} deg). Press Enter to stop.\n")
        while not enter_pressed():
            for k, bus in buses.items():
                try:
                    pos = bus.sync_read("Present_Position", normalize=False, num_retry=2)
                except ConnectionError:
                    read_errors[k] += 1
                    continue
                for m, v in pos.items():
                    lo[k][m], hi[k][m] = min(lo[k][m], v), max(hi[k][m], v)
                    if m not in passed[k] and hi[k][m] - lo[k][m] >= args.min_travel:
                        passed[k].add(m)
                        print(f"  OK  {k:<14}{m:<14}({len(passed[k])}/{len(MOTOR_NAMES)})")
            if all(len(p) == len(MOTOR_NAMES) for p in passed.values()):
                break
            time.sleep(0.02)
    finally:
        for bus in buses.values():
            bus.disconnect(disable_torque=False)

    print(f"\n=== summary (raw range seen, pass = {args.min_travel}+)")
    failed = []
    for k in buses:
        for m in MOTOR_NAMES:
            ok = m in passed[k]
            if not ok:
                failed.append(f"{k} {m}")
            print(f"  {k:<14}{m:<14}{'OK' if ok else '--':<4}{lo[k][m]:>5} .. {hi[k][m]:<5}")
        if read_errors[k]:
            print(f"  [WARN] {k}: {read_errors[k]} failed reads (loose cable or power dips?)")
    if failed:
        print(f"  not passed: {failed}")
        print("  - the joint moved but the value didn't change -> that motor's sensor or its cable")
        print("  - the joint wouldn't move -> torque still on, or something is jammed")
    else:
        print("  all joints passed")


if __name__ == "__main__":
    main()
