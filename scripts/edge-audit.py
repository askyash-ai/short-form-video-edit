#!/usr/bin/env python3
"""edge-audit.py: listen (by level) to both ends of every kept segment, and repair the bad ones with --fix.

A transcript can look clean while the viewer hears a sliver of a dropped take ("right. [ght] A couple of hours ago"):
transcribers fold a leaked fragment into the next word. Three shapes, all found by level alone:
  starts mid-sound   the first 30 ms of a segment are over --threshold: a dropped take's tail rides in
  ends mid-sound     the last 30 ms are over --threshold: a chopped word, or the onset of the next dropped take
  fragment           a segment under 0.5 s with no kept word starting in it: a restart left behind
Fixes never lose a kept word: a loud start moves into the quiet before the first kept word (searched from 0.28 s before
it to 0.10 s after; when the room tone is uniformly quiet, the spot 0.08 s ahead of the word is used); a loud end moves
into the quiet within its last 0.35 s, just after the kept sound dies away, never before the last word's start + 0.15 s; a fragment is
dropped. Re-run without --fix until it prints "0 issues".

Usage:
  python edge-audit.py --audio W/raw/take.MOV --cut-list W/cut-list.json --transcript W/tx/take.json [--keeps keeps.txt] [--fix]
--keeps: a text file holding the hand-cut "A-B" ranges; only words inside them count as kept (default: every word).
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cutlib import Audio, load_json, load_words, save_json, total  # noqa: E402

cli = argparse.ArgumentParser(description="Audit (and fix) cut edges by the audio.")
cli.add_argument("--cut-list", required=True, help="cut-list.json (rewritten by --fix)")
cli.add_argument("--transcript", required=True, help="the source's word-level transcript")
cli.add_argument("--audio", required=True, help="the source the cut list refers to")
cli.add_argument("--fix", action="store_true", help="move bad edges and drop fragments")
cli.add_argument("--threshold", type=float, default=300, help="RMS over which an edge counts as mid-sound")
cli.add_argument("--keeps", default="", help="text file of hand-cut A-B ranges: only words inside them count as kept")
args = cli.parse_args()

audio = Audio(args.audio)
words = load_words(args.transcript)
ranges = []
if args.keeps:
    with open(args.keeps, encoding="utf-8") as fh:
        ranges = [(float(a), float(b)) for a, b in re.findall(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)", fh.read())]


def is_kept(t):
    return not ranges or any(a - 0.02 <= t <= b + 0.02 for a, b in ranges)


def quietest(t0, t1, aim=None):
    """A cut point between t0 and t1 in the quietest 20 ms there (5 ms steps). Room tone is often equally quiet across
    the whole gap; then the point nearest `aim` wins (for a head: just ahead of the word), else the earliest one."""
    steps = [t0 + 0.005 * k for k in range(int(max(t1 - t0, 0.02) / 0.005) + 1)]
    levels = [audio.level(t, t + 0.02) for t in steps]
    floor = min(levels)
    calm = [t for t, v in zip(steps, levels) if v <= floor * 1.5 + 5]
    pick = min(calm, key=lambda t: abs(t + 0.01 - aim)) if aim is not None else calm[0]
    return round(pick + 0.01, 3)


cl = load_json(args.cut_list)
issues, out = [], []
for no, seg in enumerate(cl["kept"]):
    s, e = seg["start"], seg["end"]
    inside = [w for w in words if s - 0.35 <= w["start"] < e and is_kept(w["start"])]
    if e - s < 0.5 and not any(s - 0.05 <= w["start"] < e for w in inside):
        issues.append("seg %d %.2f-%.2f: a %.2f s scrap with no kept word in it" % (no, s, e, e - s))
        if args.fix:
            continue
    head = audio.level(s, s + 0.03)
    if head > args.threshold:
        issues.append("seg %d starts mid-sound at %.2f (level %d over its first 30 ms)" % (no, s, head))
        if args.fix and inside:
            first = inside[0]["start"]
            seg["start"] = quietest(first - 0.28, first + 0.10, aim=first - 0.08)
    tail = audio.level(e - 0.03, e)
    if tail > args.threshold:
        issues.append("seg %d ends mid-sound at %.2f (level %d over its last 30 ms)" % (no, e, tail))
        if args.fix:
            floor = inside[-1]["start"] + 0.15 if inside else s + 0.2
            lo = max(e - 0.35, floor)
            calm_from = quietest(lo, e)                     # earliest calm point: where the kept sound has died away
            seg["end"] = quietest(lo, e, aim=calm_from + 0.06)
    out.append(seg)

print("%d segments, %d issues" % (len(cl["kept"]), len(issues)))
for line in issues:
    print(line)
if args.fix:
    cl["kept"] = out
    cl["kept_seconds"] = total(out)
    cl["edge_audit"] = "fixed by edge-audit.py"
    save_json(args.cut_list, cl)
    print("saved %s: %d segments, %.2f s. Check again without --fix: it should say 0 issues." % (args.cut_list, len(out), cl["kept_seconds"]))
