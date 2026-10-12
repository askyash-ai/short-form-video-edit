#!/usr/bin/env python3
"""sliver.py: find the small audio glitches at the edges of a cut list, and fix them with --fix.
Run it after tighten-cut.py and before edge-audit.py.

  empty segment   nothing in it reaches speech level (300 RMS): a breath, or what is left of a cut take -> dropped
  bleed-in head   the sound runs straight through the start (both sides over 100 RMS) and dies into a quiet run
                  (>= 50 ms under 70 RMS) within 0.35 s, with speech after it: the previous word's tail rides in
                  -> the start moves into the quiet run, 0.08 s before the speech
  leak-out tail   the sound runs straight through the end and the last 0.35 s holds a quiet run with sound rising
                  after it: the next (dropped) word starts to leak -> the end moves into the quiet run, 0.10 s after
                  the speech before it
  tight edge      under 40 ms between the edge and the speech, with room tone outside -> widened by up to 0.10 s

Usage: python sliver.py --cut-list W/cut-list.json --audio W/raw/take.MOV [--fix]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cutlib import FRAME, Audio, load_json, save_json, total  # noqa: E402

cli = argparse.ArgumentParser(description="Find (and fix) breath slivers and bleed at cut edges.")
cli.add_argument("--audio", required=True, help="the source the cut list refers to")
cli.add_argument("--fix", action="store_true", help="rewrite the cut list with the changes")
cli.add_argument("--cut-list", required=True, help="cut-list.json")
args = cli.parse_args()

SPEECH, BLEED, QUIET, QUIET_RUN = 300, 100, 70, 5          # RMS levels; QUIET_RUN in 10 ms frames
LEAD, TAIL, LOOK = 0.08, 0.10, 35                            # seconds, seconds, frames

audio = Audio(args.audio)
lvl = audio.frames
quiet = lvl < QUIET
n = len(lvl)


def quiet_runs(i0, i1):
    return [(a, b) for a, b in audio.runs(quiet, i0, i1) if b - a + 1 >= QUIET_RUN]


def room_outside(i, step):
    """How many frames of room tone lie beyond frame i in direction step (max 10)."""
    k = 0
    while 0 <= i + step * (k + 1) < n and quiet[i + step * (k + 1)] and k < 10:
        k += 1
    return k


path = args.cut_list
cl = load_json(path)
section = os.path.basename(os.path.dirname(os.path.abspath(path)))
out, notes = [], []
for no, seg in enumerate(cl["kept"]):
    if seg.get("room_tone"):
        out.append(seg)
        continue
    s, e = seg["start"], seg["end"]
    a, b = audio.idx(s), audio.idx(e)
    if not (lvl[a:b] > SPEECH).any():
        notes.append("seg %d %.3f-%.3f: never reaches speech level (%d RMS), removed" % (no, s, e, SPEECH))
        continue

    if audio.level(s - 0.03, s) > BLEED and audio.level(s, s + 0.03) > BLEED:
        for q0, q1 in quiet_runs(a, min(b, a + LOOK)):
            if (lvl[q1 + 1:q1 + 30] > SPEECH).any():
                t = max((q0 + 2) * FRAME, (q1 + 1) * FRAME - LEAD)
                notes.append("seg %d head %.3f -> %.3f: it opened on the end of an earlier sound (quiet from %.2f)" % (no, s, t, q0 * FRAME))
                s = t
                break

    if audio.level(e - 0.03, e) > BLEED and audio.level(e, e + 0.03) > BLEED:
        for q0, q1 in reversed(quiet_runs(max(a, b - LOOK), b)):
            if (lvl[max(a, q0 - 30):q0] > SPEECH).any():
                t = min((q1 - 1) * FRAME, q0 * FRAME + TAIL)
                notes.append("seg %d tail %.3f -> %.3f: a new onset after the quiet run at %.2f leaks out" % (no, e, t, q0 * FRAME))
                e = t
                break

    a, b = audio.idx(s), audio.idx(e)
    loud = [i for i in range(a, b) if lvl[i] > SPEECH]
    if loud:
        if (loud[0] - a) * FRAME < 0.04 and room_outside(a, -1) >= 3:
            t = s - room_outside(a, -1) * FRAME + 0.01
            notes.append("seg %d head %.3f -> %.3f: lead-in %.2f s widened into room tone" % (no, s, t, (loud[0] - a) * FRAME))
            s = t
        if (b - 1 - loud[-1]) * FRAME < 0.04 and room_outside(b - 1, 1) >= 3:
            t = e + room_outside(b - 1, 1) * FRAME - 0.01
            notes.append("seg %d tail %.3f -> %.3f: tail %.2f s widened into room tone" % (no, e, t, (b - 1 - loud[-1]) * FRAME))
            e = t
    out.append(dict(seg, start=round(s, 3), end=round(e, 3)))

print("%s: %d segments, %d changes" % (section, len(cl["kept"]), len(notes)))
for line in notes:
    print("  " + line)
if args.fix and notes:
    cl["kept"] = out
    cl["kept_seconds"] = total(out)
    cl.setdefault("hand_fixes", []).extend("sliver.py: " + line for line in notes)
    save_json(path, cl)
    print("wrote %s (%d segments, %.2f s)" % (path, len(out), cl["kept_seconds"]))
