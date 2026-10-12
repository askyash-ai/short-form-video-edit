#!/usr/bin/env python3
"""screen-activity.py: how much a screen recording changes over time (typing, scrolling and clicks show up; a still
page does not), to pick the stretches worth showing as an L panel and the dead ones to cut or cover.
Samples --fps frames a second at --width px, greyscale, and writes [[seconds, mean change 0-255], ...].
Usage: python screen-activity.py --video W/screen.mp4 --out W/activity.json
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cutlib import fail, probe, stream  # noqa: E402

cli = argparse.ArgumentParser(description="Measure activity in a screen recording.")
cli.add_argument("--out", required=True, help="activity.json to write")
cli.add_argument("--video", required=True, help="the screen recording")
cli.add_argument("--width", type=int, default=96, help="analysis width in px (small is enough)")
cli.add_argument("--fps", type=float, default=2.0, help="samples per second")
args = cli.parse_args()

import numpy as np  # noqa: E402

v = stream(probe(args.video, "stream=codec_type,width,height"), "video")
if v is None:
    fail("no video stream in %s" % args.video)
w = args.width
h = max(2, int(round(v["height"] * w / v["width"] / 2.0)) * 2)
raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", args.video, "-vf", "fps=%s,scale=%d:%d,format=gray" % (args.fps, w, h),
                      "-f", "rawvideo", "-"], capture_output=True).stdout
frames = np.frombuffer(raw, np.uint8)[: len(raw) // (w * h) * w * h].reshape(-1, h, w).astype(np.int16)
change = np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2)) if len(frames) > 1 else np.zeros(0)
series = [[round(i / args.fps, 2), round(float(d), 2)] for i, d in enumerate(change)]
with open(args.out, "w", encoding="utf-8") as fh:
    json.dump(series, fh)
active = 100.0 * float((change > 1.5).mean()) if len(change) else 0.0
print("%s: %d samples, %.1f s, active (>1.5) %.0f%%" % (args.video, len(series), len(series) / args.fps, active))
