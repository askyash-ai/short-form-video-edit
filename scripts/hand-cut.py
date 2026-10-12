#!/usr/bin/env python3
"""hand-cut.py: write cut-list.json from an explicit list of the lines to keep, for takes paper-cut.py reads wrong
(a list it took for restarts, a slate it kept, a "last take" with a wrong word in it, retakes merged into one sentence).

Each --keep is "A-B": A = the start time of the first kept word, B = the start time of the last kept word, both copied
from the transcript. "A-B!" keeps the stretch whole, pauses and all (a deliberate beat). Otherwise the pauses inside are
trimmed at the gaps between auto-editor speech chunks. Starts come from the transcript (A minus --before). Ends come
from the audio, because transcribers stretch final words: a line ends where its speech chunk ends, or a hair before the
next word if that word follows straight on.

Usage:
  python hand-cut.py --transcript W/tx/take.json --speech W/speech.v1.json --duration 125.1 --out-dir W \
      --keep 5.20-9.90 --keep 10.96-15.40! [--label "take 3"]
Output: cut-list.json in paper-cut's format, flagged "hand_cut": true, and a PAPER-CUT.md of the lines you kept.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cutlib import fail, gaps, load_speech, load_words, merge, save_json, total  # noqa: E402

cli = argparse.ArgumentParser(description="Build cut-list.json from the lines to keep.")
cli.add_argument("--keep", action="append", required=True, metavar="A-B[!]", help="word start times of a line to keep (repeat per line)")
cli.add_argument("--transcript", required=True, help="the take's word-level transcript")
cli.add_argument("--speech", required=True, help="auto-editor v1 JSON of the same take")
cli.add_argument("--duration", type=float, required=True, help="length of the take (s)")
cli.add_argument("--out-dir", required=True, help="where cut-list.json and PAPER-CUT.md go")
cli.add_argument("--label", default="", help="a note for the PAPER-CUT.md title")
cli.add_argument("--before", type=float, default=0.15, help="lead-in before the first word (s)")
cli.add_argument("--after", type=float, default=0.45, help="tail when no speech chunk is found (s)")
args = cli.parse_args()

words = load_words(args.transcript)
chunks = load_speech(args.speech)
if not words:
    fail("no words in %s" % args.transcript)


starts = [w["start"] for w in words]


def word_at(t):
    """Index of the word starting at t (within 60 ms), else stop with the closest one as a hint."""
    best = min(range(len(starts)), key=lambda k: abs(starts[k] - t))
    if abs(starts[best] - t) <= 0.06:
        return best
    fail("--keep: %.2f is not a word start; the closest is %r at %.2f" % (t, words[best]["text"], starts[best]))


pieces, lines = [], []
for spec in args.keep:
    whole = spec.strip().endswith("!")
    try:
        a, b = [float(x) for x in spec.strip().rstrip("!").split("-")]
    except ValueError:
        fail('--keep %s: expected "A-B" or "A-B!"' % spec)
    i, j = word_at(a), word_at(b)
    first, last = words[i], words[j]
    nxt = words[j + 1] if j + 1 < len(words) else None

    near = [c for c in chunks if c[1] > first["start"] - 0.3 and c[0] < last["start"] + 0.2]
    end = min(max((c[1] for c in near), default=last["end"] + args.after), last["end"] + 1.2)
    if nxt and nxt["start"] < end and nxt["start"] - last["start"] < 1.5:
        end = max(last["start"] + 0.12, nxt["start"] - 0.03)
    start = max(0.0, first["start"] - args.before)

    inside = sorted(c for c in near if c[1] > start and c[0] < end)
    if whole or len(inside) < 2:
        pieces.append({"start": start, "end": end})
    else:
        p0, p1 = start, min(end, inside[0][1] + args.after)
        for c0, c1 in inside[1:]:
            if c0 - p1 > args.before + 0.05:     # a real pause between chunks: close the piece, reopen at the next one
                pieces.append({"start": p0, "end": p1})
                p0 = c0 - args.before
            p1 = min(end, c1 + args.after)
        pieces.append({"start": p0, "end": max(p1, end)})
    lines.append("%6.2f  %s%s" % (first["start"], " ".join(w["text"] for w in words[i:j + 1]), "  (whole)" if whole else ""))

kept = merge(pieces, duration=args.duration)
removed = [{"start": a, "end": b, "reason": "tail" if b >= args.duration - 0.001 else "hand cut", "text": ""}
           for a, b in gaps(kept, args.duration)]
kept_s = total(kept)
save_json(os.path.join(args.out_dir, "cut-list.json"),
          {"source_duration": args.duration, "kept_seconds": kept_s, "kept": kept, "removed": removed, "hand_cut": True})
title = "# Paper cut, by hand" + (": " + args.label if args.label else "")
md = [title, "",
      "%d line(s) kept: %.1f s of the %.1f s take, in %d segment(s). Anything not listed below is cut."
      % (len(lines), kept_s, args.duration, len(kept)), ""] + lines
with open(os.path.join(args.out_dir, "PAPER-CUT.md"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(md) + "\n")
print("hand cut: %d segment(s), %.1f s of %.1f s" % (len(kept), kept_s, args.duration))
print("\n".join("  %.3f -> %.3f  (%.2f s)" % (s["start"], s["end"], s["end"] - s["start"]) for s in kept))
