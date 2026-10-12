#!/usr/bin/env python3
"""dead-air.py: list the pauses in a finished flat cut that are still too long for short-form, and plan their removal.

  python dead-air.py W --plan [--max 0.30] [--max-sentence 0.25] [--target 0.12] [--keep 14.2] [--json W/dead-air.json]

W is the project folder. Sound comes from W/audio.wav, or W/public/input-video.mp4 when there is no wav; the words
from W/transcript.json (a transcript of the flat cut); join times from W/cut-map.json when it exists.
Pauses are found in the sound itself - runs of 10 ms frames below --speech RMS between two spoken stretches - because
transcribers drag the last word of a sentence over the silence after it. A pause is too long above --max-sentence when
the word before it ends a sentence, above --max otherwise. --plan proposes, for each one, which flat range to remove so
--target s remain: a little of the last word's decay and of the breath before the next word stays, and both new edges
must sit in room tone (below --quiet RMS). An overlong head or tail of the cut is proposed as well.
--keep T protects the pause around flat time T (a pause you want).
Feed the PLAN ranges to patch-cut.py --drop-flat, render with apply-cut.py, transcribe, and scan again.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cutlib import FRAME, Audio, ends_sentence, fail, load_json, load_words, save_json  # noqa: E402

cli = argparse.ArgumentParser(description="Find and plan out overlong pauses in a flat cut.")
cli.add_argument("folder", help="project folder (audio.wav or public/input-video.mp4, transcript.json, cut-map.json)")
cli.add_argument("--plan", action="store_true", help="print the PLAN line of --drop-flat ranges")
cli.add_argument("--target", type=float, default=0.30, help="length a pause is brought down to (s)")
cli.add_argument("--max", type=float, default=0.45, help="longest allowed pause inside a sentence (s)")
cli.add_argument("--max-sentence", type=float, default=0.40, help="longest allowed pause after . ? ! (s)")
cli.add_argument("--keep", type=float, action="append", default=[], help="flat time of a pause to leave alone")
cli.add_argument("--head", type=float, default=0.12, help="silence to keep before the first speech (s)")
cli.add_argument("--tail", type=float, default=0.15, help="silence to keep after the last speech (s)")
cli.add_argument("--speech", type=float, default=300.0, help="RMS above which a 10 ms frame is speech")
cli.add_argument("--quiet", type=float, default=80.0, help="RMS below which a frame is room tone")
cli.add_argument("--json", default="", help="also write the findings to this file")
opt = cli.parse_args()

root = os.path.abspath(opt.folder)
sound = next((p for p in (os.path.join(root, "audio.wav"), os.path.join(root, "public", "input-video.mp4")) if os.path.exists(p)), None)
if sound is None:
    fail("%s has neither audio.wav nor public/input-video.mp4" % root)
transcript = os.path.join(root, "transcript.json")
if not os.path.exists(transcript):
    fail("%s has no transcript.json: transcribe the flat cut first" % root)
audio = Audio(sound)
lvl = audio.frames
spoken = load_words(transcript)
joins = load_json(os.path.join(root, "cut-map.json")).get("cuts", []) if os.path.exists(os.path.join(root, "cut-map.json")) else []
length = audio.duration
if os.path.exists(os.path.join(root, "cut-map.json")):
    length = float(load_json(os.path.join(root, "cut-map.json")).get("flat_duration", length))

voiced = [i for i, v in enumerate(lvl) if v > opt.speech]
if not voiced:
    fail("nothing above %d RMS in %s: is this the right file?" % (opt.speech, sound))


def word_before(t):
    return next((w["text"] for w in reversed(spoken) if w["start"] < t), "(start)")


def word_after(t):
    return next((w["text"] for w in spoken if w["start"] >= t - 0.05), "(end)")


# what stays of a pause: the decay of the word before and the breath into the next. A target tighter than the usual
# 0.10 + 0.08 s is split between them in the same proportion.
decay, breath = (0.10, 0.08) if opt.target >= 0.18 else (opt.target * 0.55, opt.target * 0.45)
found, ranges = [], []
for a, b in zip(voiced, voiced[1:]):
    if b - a < 2:
        continue
    start, end = (a + 1) * FRAME, b * FRAME
    pause = end - start
    allowed = opt.max_sentence if ends_sentence(word_before(start)) else opt.max
    if pause <= allowed:
        continue
    item = {"from": round(start, 2), "to": round(end, 2), "gap": round(pause, 2),
            "join": [round(j, 3) for j in joins if start - 0.05 <= j <= end + 0.05],
            "before": word_before(start), "after": word_after(end),
            "keep": any(start - 0.05 <= k <= end + 0.05 for k in opt.keep)}
    if not item["keep"]:
        cut_frames = int(round((pause - opt.target) / FRAME))
        lo = int(round((start + decay) / FRAME))
        hi = int(round((end - breath) / FRAME)) - cut_frames
        if 0 < lo - hi <= 2:          # 10 ms rounding can leave the window a frame or two short
            hi = lo
        middle = (a + b) / 2.0
        best = None
        for k0 in range(lo, hi + 1):
            k1 = min(k0 + cut_frames, len(lvl) - 1)
            louder_edge = max(lvl[k0], lvl[k1])
            if louder_edge >= opt.quiet:
                continue
            rank = (round(louder_edge / 20.0), abs((k0 + k1) / 2.0 - middle))     # quiet edges first, then centred
            if best is None or rank < best[0]:
                best = (rank, k0, k1)
        if best:
            _, k0, k1 = best
            item.update({"drop": [round(k0 * FRAME, 3), round(k1 * FRAME, 3)], "after_gap": round(pause - (k1 - k0) * FRAME, 2),
                         "edge_rms": [int(lvl[k0]), int(lvl[k1])], "max_in_drop": int(lvl[k0:k1].max())})
            ranges.append(tuple(item["drop"]))
        else:
            item["note"] = "breath or noise fills it: no quiet %.2f s window to remove" % (pause - opt.target)
    found.append(item)

lead_in = voiced[0] * FRAME
tail_out = (len(lvl) - 1 - voiced[-1]) * FRAME
edges = {"head": round(lead_in, 2), "tail": round(tail_out, 2)}
if lead_in > opt.head + 0.15:
    edges["head_drop"] = [0.0, round(lead_in - opt.head, 3)]
    ranges.append(tuple(edges["head_drop"]))
if tail_out > opt.tail + 0.08:
    t0 = round((voiced[-1] + 1) * FRAME + opt.tail, 3)
    if length - t0 > 0.05:
        edges["tail_drop"] = [t0, round(length, 3)]
        ranges.append(tuple(edges["tail_drop"]))

print("%s (%.3f s, %d joins): %d pause(s) too long [limits %.2f s, %.2f s after a sentence]; lead-in %.2f s, tail %.2f s"
      % (os.path.basename(root), length, len(joins), len(found), opt.max, opt.max_sentence, lead_in, tail_out))
for item in found:
    place = ("at join " + ", ".join("%.2f" % j for j in item["join"])) if item["join"] else "mid-segment"
    head = "  %.2f s pause %6.2f-%-6.2f %-16s  ...%s | %s..." % (item["gap"], item["from"], item["to"], place, item["before"], item["after"])
    if item["keep"]:
        print(head + "   kept on purpose (--keep)")
    elif "drop" in item:
        print(head + "   remove %.3f-%.3f, leaving %.2f s (edges %d/%d RMS, loudest inside %d)"
              % (item["drop"][0], item["drop"][1], item["after_gap"], item["edge_rms"][0], item["edge_rms"][1], item["max_in_drop"]))
    else:
        print(head + "   " + item["note"])
for side in ("head", "tail"):
    if side + "_drop" in edges:
        print("  %s of %.2f s: remove %.3f-%.3f" % (side, edges[side], *edges[side + "_drop"]))
if opt.plan:
    print(("PLAN " + " ".join("--drop-flat %.3f-%.3f" % r for r in sorted(ranges))) if ranges else "PLAN none")
if opt.json:
    save_json(opt.json, {"section": os.path.basename(root), "rows": found, "edges": edges, "plan": sorted(ranges)})
