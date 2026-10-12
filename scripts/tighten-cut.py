#!/usr/bin/env python3
"""tighten-cut.py: trim the dead air a word-timed cut list still holds, by the SOUND.

Transcribers often start a phrase up to ~0.4 s before it is audible after a long pause, so a cut built from word
times keeps that silence at every join. For each kept segment this finds the audible stretch (10 ms frames over
--threshold, with single-frame clicks ignored) and trims the lead-in to --lead s before it and the tail to --tail s
after it. A silence inside the segment longer than --maxgap splits it in two, adding a join. A segment flagged
"room_tone": true is a pause kept on purpose and is left exactly as it is.

Example:  python tighten-cut.py --cut-list W/cut-list.json --audio W/raw/take.MOV --out W/cut-list-tight.json
Render the tightened list with apply-cut.py and transcribe the result: no word may have gone missing.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cutlib import FRAME, Audio, load_json, save_json, total  # noqa: E402

cli = argparse.ArgumentParser(description="Trim lead-ins, tails and inner silences by the audio.")
cli.add_argument("--cut-list", required=True, help="the cut list to tighten")
cli.add_argument("--out", required=True, help="where the tightened list goes")
cli.add_argument("--audio", required=True, help="the source the cut list refers to (wav, mp4 or mov)")
cli.add_argument("--maxgap", type=float, default=0.30, help="an inner silence longer than this splits the segment (s)")
cli.add_argument("--lead", type=float, default=0.07, help="air kept before the sound starts (s)")
cli.add_argument("--tail", type=float, default=0.11, help="air kept after the sound ends (s)")
cli.add_argument("--threshold", type=float, default=40.0, help="10 ms level that counts as sound (room ~5-30, speech 1000+)")
args = cli.parse_args()

audio = Audio(args.audio)
lvl = audio.frames
loud = lvl > args.threshold
# a frame counts only when a neighbour is loud too: a lone loud frame is a lip click or a tap, not speech
steady = loud.copy()
for i in range(len(loud)):
    steady[i] = loud[i] and loud[max(0, i - 1):i + 2].sum() >= 2

cl = load_json(args.cut_list)
out = []
for seg in cl["kept"]:
    if seg.get("room_tone"):
        out.append(seg)
        continue
    i0, i1 = audio.idx(seg["start"]), audio.idx(seg["end"])
    runs = audio.runs(steady, i0, i1)
    if not runs:
        continue                                   # nothing audible: the segment goes
    groups = [list(runs[0])]
    for a, b in runs[1:]:
        if (a - groups[-1][1]) * FRAME > args.maxgap:
            groups.append([a, b])
        else:
            groups[-1][1] = b
    for a, b in groups:
        out.append({"start": round(max(seg["start"], a * FRAME - args.lead), 3),
                    "end": round(min(seg["end"], (b + 1) * FRAME + args.tail), 3)})

cl["kept"] = out
cl["kept_seconds"] = total(out)
save_json(args.out, cl)
print("tightened to %d segments, %.2f s -> %s" % (len(out), cl["kept_seconds"], args.out))
