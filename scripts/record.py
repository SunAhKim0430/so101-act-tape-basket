#!/usr/bin/env python
r"""lerobot-record (LeRobot 0.6.1) with a fix for keys pressed between episodes. 4_record.bat runs this.

A key pressed while the previous episode is being saved stays set. A stray `n` then ends the next episode before
its first frame, and saving that empty episode stops the whole session with
"You must add one or several frames with `add_frame` before calling `add_episode`" (seen in our first test recording).
  1. n / r pressed before an episode starts are ignored (q is kept: the session stops after saving)
  2. an episode that still ends with no frame is re-recorded instead of saved

Takes the same arguments as lerobot-record:
    python record.py --robot.type=so101_follower ... --dataset.root=...
"""

import logging

import lerobot.scripts.lerobot_record as lerobot_record

_record_loop = lerobot_record.record_loop


def record_loop(*args, **kwargs):
    events, dataset = kwargs["events"], kwargs.get("dataset")
    if dataset is not None:  # episode, not reset
        if events["exit_early"] or events["rerecord_episode"]:
            logging.warning("Ignoring n / r pressed before this episode started")
        events["exit_early"] = events["rerecord_episode"] = False
    _record_loop(*args, **kwargs)
    if dataset is not None and not dataset.has_pending_frames() and not events["rerecord_episode"]:
        logging.warning("Episode ended before its first frame - recording it again")
        events["rerecord_episode"] = True


lerobot_record.record_loop = record_loop

if __name__ == "__main__":
    lerobot_record.main()
