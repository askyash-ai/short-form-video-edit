#!/usr/bin/env python3
"""patch-cut.py: edit an existing cut-list.json in place - take out a stretch you spotted in the flat cut, remove a
segment, or bring words back.

  --drop-flat A-B   A and B are FLAT-cut times (as dead-air.py, stutter-scan.py and CUT-REVIEW.html report them).
                    cut-map.json (from apply-cut.py) translates them into source times, so the fix is made in the cut
                    list and the source is rendered once more, never the flat file re-cut. A stretch in the middle of a
                    segment splits it in two; one that spans a join shortens both neighbours (and takes the few
                    milliseconds the frame snap left at that edge). Anything left shorter than --min-keep goes as well:
                    on screen it would be a flash frame.
  --drop T          delete the segment whose start is within 0.3 s of source time T (a stray "um", a lone fragment).
  --add A-B         restore source words: A = start of the first word, B = start of the last. The restored piece runs
                    from A - --before to where the auto-editor speech chunk around B ends, stopping short of the next
                    word if that comes sooner. Needs --transcript and --speech.
Nothing is written unless every range is valid. Then: apply-cut.py again, and a fresh transcript of the flat cut.

Examples:
  python patch-cut.py --cut-list W/cut-list.json --drop-flat 12.40-12.95 --drop-flat 30.10-30.48
  python patch-cut.py --cut-list W/cut-list.json --transcript W/tx/take.json --speech W/speech.v1.json --add 83.60-92.88
"""
import argparse
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cutlib import fail, load_json, load_speech, load_words, save_json, total  # noqa: E402

cli = argparse.ArgumentParser(description="Edit cut-list.json: drop flat-cut ranges, drop segments, restore words.")
cli.add_argument("--cut-list", required=True, help="the cut list to edit (rewritten in place)")
cli.add_argument("--drop-flat", action="append", default=[], metavar="A-B", help="flat-cut range to remove (repeatable)")
cli.add_argument("--drop", action="append", default=[], type=float, metavar="T", help="source time of a segment start to remove")
cli.add_argument("--add", action="append", default=[], metavar="A-B", help="source word starts of a stretch to restore")
cli.add_argument("--cut-map", help="default: cut-map.json beside the cut list")
cli.add_argument("--transcript", help="the source transcript (for --add)")
cli.add_argument("--speech", help="auto-editor v1 JSON of the source (for --add)")
cli.add_argument("--min-keep", type=float, default=0.10, help="shortest leftover piece worth keeping (s)")
cli.add_argument("--before", type=float, default=0.15, help="lead-in before a restored word (s)")
cli.add_argument("--after", type=float, default=0.45, help="tail after a restored word when no chunk is found (s)")
opt = cli.parse_args()
if opt.add and not (opt.transcript and opt.speech):
    fail("--add needs --transcript and --speech")


def span(text):
    """'1.5-2.25' -> (1.5, 2.25); None unless both are finite numbers with the first smaller."""
    m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)\s*", text)
    if not m:
        return None
    lo, hi = float(m.group(1)), float(m.group(2))
    return (lo, hi) if math.isfinite(lo) and math.isfinite(hi) and lo < hi else None


doc = load_json(opt.cut_list)
segments = [dict(s) for s in doc["kept"]]
notes = []

# 1. translate every --drop-flat into source ranges first; any problem stops here, before anything changes
to_remove = []
if opt.drop_flat:
    map_path = opt.cut_map or os.path.join(os.path.dirname(os.path.abspath(opt.cut_list)), "cut-map.json")
    if not os.path.exists(map_path):
        fail("cut-map.json not found (%s). Flat times refer to the cut apply-cut.py made: run it first." % map_path)
    cmap = load_json(map_path)
    pieces, flat_len = cmap["segments"], float(cmap["flat_duration"])
    stale = [p for p in pieces if not any(s["start"] - 0.05 <= p["src_start"] and p["src_end"] <= s["end"] + 0.05 for s in segments)]
    if stale:
        fail("cut-map.json was made from a different cut list (source %.3f-%.3f is no longer kept): re-run apply-cut.py"
             % (stale[0]["src_start"], stale[0]["src_end"]))
    for text in opt.drop_flat:
        rng = span(text)
        if rng is None:
            fail("--drop-flat %s: give two numbers, start < end (e.g. 12.40-12.95)" % text)
        lo, hi = rng
        if lo < 0 or hi > flat_len + 0.001:
            fail("--drop-flat %s: outside the flat duration of %.3f s" % (text, flat_len))
        src = []
        for p in pieces:
            if hi <= p["flat_start"] or lo >= p["flat_end"]:
                continue
            offset = p["src_start"] - p["flat_start"]
            a = lo + offset if lo > p["flat_start"] else p["src_start"] - 0.04     # reaching the join: take the snap remainder too
            b = hi + offset if hi < p["flat_end"] else p["src_end"] + 0.04
            if b > a:
                src.append((round(a, 3), round(b, 3)))
        to_remove.append((text, src))

# 2. --drop and --add work on source times
for t in opt.drop:
    n = len(segments)
    segments = [s for s in segments if min(abs(s["start"] - t), abs(s["start"] + opt.before - t)) > 0.3]
    notes.append("drop %.2f: %d segment(s) removed" % (t, n - len(segments)))
if opt.add:
    words = load_words(opt.transcript)
    chunks = load_speech(opt.speech)
    for text in opt.add:
        rng = span(text)
        if rng is None:
            fail("--add %s: give two word start times, start < end" % text)
        first_t, last_t = rng
        last = min(words, key=lambda w: abs(w["start"] - last_t))
        following = next((w for w in words if w["start"] > last["start"] + 0.01), None)
        around = [c for c in chunks if c[0] <= last["start"] <= c[1] + 0.05]
        end = around[-1][1] if around else last["end"] + opt.after
        if following is not None and end > following["start"] - 0.1:
            end = max(last["end"], following["start"] - 0.1)
        segments.append({"start": round(first_t - opt.before, 3), "end": round(end, 3)})
        notes.append("add %.2f-%.2f as %.2f-%.2f" % (first_t, last_t, first_t - opt.before, end))

joined = []
for s in sorted(segments, key=lambda s: s["start"]):
    if joined and s["start"] <= joined[-1]["end"] + 0.05:
        joined[-1]["end"] = max(joined[-1]["end"], s["end"])
    else:
        joined.append(dict(s))

# 3. carve the flat drops out last, so merging cannot put them back
for text, src in to_remove:
    notes.append("drop-flat %s = source %s" % (text, ", ".join("%.3f-%.3f" % r for r in src)))
    for a, b in src:
        carved = []
        for s in joined:
            if b <= s["start"] or a >= s["end"]:
                carved.append(s)
                continue
            for part in ({"start": s["start"], "end": round(a, 3)}, {"start": round(b, 3), "end": s["end"]}):
                size = part["end"] - part["start"]
                if size >= opt.min_keep:
                    carved.append(part)
                elif size > 0.001:
                    notes.append("removed a %.2f s sliver at %.3f (it would flash)" % (size, part["start"]))
        joined = carved
    doc.setdefault("flat_drops", []).append({"flat": text, "source": [list(r) for r in src]})

if not joined:
    fail("nothing would be left; the cut list was not changed")
doc["kept"] = joined
doc["kept_seconds"] = total(joined)
doc["hand_patched"] = True
save_json(opt.cut_list, doc)
print("%s -> %d segments, %.1f s kept" % ("; ".join(notes) or "no changes", len(joined), doc["kept_seconds"]))
if to_remove:
    print("next: apply-cut.py (the old cut-map.json no longer applies), then transcribe the new flat cut")
