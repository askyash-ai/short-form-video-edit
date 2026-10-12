#!/usr/bin/env python3
"""paper-cut.py: propose the cut of one continuous take from its word-level transcript (Checkpoint A material).

It reads the take sentence by sentence and marks for removal, in this order:
  restarts       a run of words that is said again a moment later inside the same sentence ("the tool, the tool does")
                 -> the first attempt goes, the later one stays
  markers        "cut that", "scratch that", "let me try that again", "start over", "take two", a lone "again"
                 -> the marker sentence and the flubbed sentence before it
  retakes        a sentence that comes back within the next --window sentences, close in wording -> the LAST take stays.
                 If the later take only adds a leading filler ("so", "okay", "and"), the clean earlier one stays.
  false starts   a short fragment (5 words or fewer) whose first two words open the next sentence
Then the kept words become segments: --before s of lead-in, --after s of tail (or the end of the auto-editor speech
chunk with --speech, since transcribers stretch word ends into pauses), split wherever a pause exceeds --gap.

Outputs, in --out-dir:
  cut-list.json   the segments to keep ("kept", source seconds) and everything taken out with why ("removed")
  PAPER-CUT.md    the take as text, one sentence per line with its time; what goes is struck through and labelled
Usage:
  python paper-cut.py --transcript W/tx/take.json --duration 187.19 --out-dir W [--speech W/speech.v1.json]
"""
import argparse
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cutlib import ends_sentence, gaps, key, load_speech, load_words, merge, save_json, tokens, total  # noqa: E402

ap = argparse.ArgumentParser(description="Propose the cut of one continuous take.")
ap.add_argument("--out-dir", required=True, help="where cut-list.json and PAPER-CUT.md go")
ap.add_argument("--duration", type=float, required=True, help="the take's length in seconds")
ap.add_argument("--transcript", required=True, help="the take's word-level transcript")
ap.add_argument("--speech", help="auto-editor v1 JSON: segment ends follow the audio instead of the transcript")
ap.add_argument("--sim", type=float, default=0.62, help="wording similarity for a retake (0-1)")
ap.add_argument("--window", type=int, default=6, help="how many sentences ahead a retake may come back")
ap.add_argument("--gap", type=float, default=0.60, help="a pause longer than this splits a segment")
ap.add_argument("--before", type=float, default=0.15, help="lead-in kept before a word")
ap.add_argument("--after", type=float, default=0.45, help="tail kept after a word")
ap.add_argument("--head", type=float, default=0.25, help="lead-in before the very first word")
ap.add_argument("--tail", type=float, default=0.60, help="tail after the very last word")
args = ap.parse_args()

words = load_words(args.transcript)
if not words:
    sys.exit("no words in %s" % args.transcript)
keys = [key(w["text"]) for w in words]

FUNCTION = set("a an the is are was it its it's to of in on at as for with and or but so if be by i i'm i'll me my "
               "you you're your we our that this um uh".split())
FILLERS = {"now", "right", "alright", "okay", "ok", "yeah", "so", "and", "um", "uh"}
MARKER = re.compile(r"\b(cut that|scratch that|start (over|again)|take two|one more time|"
                    r"let me (redo|start (over|again)|do (that|it) again|try (that |it )?again))\b")


def alike(a, b):
    return bool(a and b) and (a == b or difflib.SequenceMatcher(None, a, b).ratio() >= 0.6)


# ---------------------------------------------------------------- sentences
sentences, current = [], []
for i, w in enumerate(words):
    current.append(i)
    pause_after = words[i + 1]["start"] - w["end"] if i + 1 < len(words) else 0
    if ends_sentence(w["text"]) or pause_after > 0.9:
        sentences.append(current)
        current = []
if current:
    sentences.append(current)

# ---------------------------------------------------------------- restarts inside a sentence
removed = []          # {start, end, reason, text}
dropped = set()       # word indices removed as restarts


def restart_at(idx, p):
    """The furthest position q (within 12 words) where the words at p are said again, or None.
    Two matching words are needed; three when the first is a function word and the stretch is long."""
    for q in range(min(len(idx) - 1, p + 12), p, -1):
        if keys[idx[q]] != keys[idx[p]] or not keys[idx[p]]:
            continue
        need = 3 if keys[idx[p]] in FUNCTION and q - p > 4 else 2
        if all(p + k < q and q + k < len(idx) and alike(keys[idx[p + k]], keys[idx[q + k]]) for k in range(1, need)):
            return q
    return None


units = []            # one per sentence: {idx (kept word indices), text, toks, start, end, why}
for idx in sentences:
    p, local = 0, set()
    while p < len(idx) - 1:
        q = restart_at(idx, p)
        if q is None:
            p += 1
            continue
        gone = idx[p:q]
        local.update(gone)
        said = " ".join(words[k]["text"] for k in gone)
        removed.append(dict(reason="restart", text=said, start=round(words[gone[0]]["start"], 3), end=round(words[idx[q]]["start"], 3)))
        p = q
    keep = [k for k in idx if k not in local]
    # rapid retakes the transcriber merged into one sentence leave the same word 3+ times: keep from the last restart on
    if local and keep:
        counts = {}
        for k in keep:
            if keys[k]:
                counts[keys[k]] = counts.get(keys[k], 0) + 1
        if counts and max(counts.values()) >= 3 and max(counts.values()) >= 0.25 * len(keep):
            last = max(idx.index(k) for k in local)
            keep = idx[last + 1:]
            local = set(idx) - set(keep)
    dropped |= local
    if not keep:
        continue
    text = " ".join(words[k]["text"] for k in keep)
    units.append({"idx": keep, "text": text, "toks": tokens(text), "start": words[keep[0]]["start"],
                  "end": words[keep[-1]]["end"], "why": None})

# ---------------------------------------------------------------- markers
for n, u in enumerate(units):
    said = " ".join(u["toks"])
    if MARKER.search(said) or u["toks"] in (["again"], ["okay", "again"], ["ok", "again"]):
        u["why"] = 'marker: "%s"' % u["text"]
        if n and units[n - 1]["why"] is None:
            units[n - 1]["why"] = 'flub before "%s"' % u["text"]


# ---------------------------------------------------------------- retakes
def content(toks):
    return [t for t in toks if t not in FUNCTION]


def is_retake(a, b):
    A, B = a["toks"], b["toks"]
    if difflib.SequenceMatcher(None, A, B).ratio() >= args.sim:
        return True
    if A[:3] == B[:3] and len(B) >= 0.6 * len(A):
        return True
    ca, cb = content(A), content(B)
    if ca and cb and len(A) <= 14 and len(B) <= 14:
        overlap = len(set(ca) & set(cb)) / len(set(ca) | set(cb))
        return overlap >= 0.4 or (ca[-1] == cb[-1] and overlap >= 0.2)
    return False


for n, u in enumerate(units):
    if u["why"] or len(u["toks"]) < 2:
        continue
    for m in range(n + 1, min(len(units), n + 1 + args.window)):
        later = units[m]
        if later["why"] or len(later["toks"]) < 2 or not is_retake(u, later):
            continue
        if later["toks"][0] in FILLERS and later["toks"][1:] == u["toks"]:
            later["why"] = "retake (the same line with a filler in front; the clean one at %.1fs stays)" % u["start"]
            continue
        for between in units[n:m]:
            if between["why"] is None:
                between["why"] = "retake (kept the later take at %.1fs)" % later["start"]
        break

# ---------------------------------------------------------------- false starts
for n in range(len(units) - 1):
    u, nxt = units[n], units[n + 1]
    if not u["why"] and not nxt["why"] and len(u["toks"]) <= 5 and len(nxt["toks"]) >= 4 and u["toks"][:2] == nxt["toks"][:2]:
        u["why"] = "false start"

removed += [{"start": round(u["start"], 3), "end": round(u["end"], 3), "reason": u["why"], "text": u["text"]}
            for u in units if u["why"]]

# ---------------------------------------------------------------- kept words -> segments
speech = load_speech(args.speech) if args.speech else []


def audio_end(t, fallback):
    """End of the speech chunk holding time t, else the fallback."""
    hold = [c for c in speech if c[0] - 0.05 <= t <= c[1] + 0.05]
    return hold[-1][1] if hold else fallback


runs = []  # consecutive kept word indices; `stop` = the start of a dropped word right after the run, if any
for u in units:
    if u["why"]:
        continue
    run = [u["idx"][0]]
    for k in u["idx"][1:]:
        if k == run[-1] + 1:
            run.append(k)
            continue
        runs.append({"idx": run, "stop": words[run[-1] + 1]["start"]})
        run = [k]
    runs.append({"idx": run, "stop": None})

segments = []
for r_no, run in enumerate(runs):
    first, last_run = r_no == 0, r_no == len(runs) - 1
    ws = [words[k] for k in run["idx"]]
    start = ws[0]["start"] - (args.head if first else args.before)
    for a, b in zip(ws, ws[1:]):
        if b["start"] - a["end"] > args.gap:                       # a long pause inside: close this piece
            end = min(audio_end(a["start"], a["end"] + args.after), b["start"] - args.before)
            segments.append({"start": start, "end": end})
            start = b["start"] - args.before
    end = audio_end(ws[-1]["start"], ws[-1]["end"] + (args.tail if last_run else args.after))
    if not speech:
        end = min(end, ws[-1]["end"] + 1.2)
    if run["stop"] is not None:                                     # a restart follows: stop before its first word
        end = min(end, run["stop"] - 0.02)
    segments.append({"start": start, "end": max(end, ws[-1]["start"] + 0.12)})

kept = merge(segments, duration=args.duration)
explained = [(r["start"], r["end"]) for r in removed]
for a, b in gaps(kept, args.duration):
    if not any(x < b and a < y for x, y in explained):
        removed.append({"start": a, "end": b, "reason": "silence %.1fs" % (b - a), "text": ""})
removed.sort(key=lambda r: r["start"])
kept_s = total(kept)

os.makedirs(args.out_dir, exist_ok=True)
save_json(os.path.join(args.out_dir, "cut-list.json"),
          {"source_duration": args.duration, "kept_seconds": kept_s, "kept": kept, "removed": removed})

lines = ["# Paper cut", "",
         "Raw %.1f s -> kept %.1f s in %d segments. Struck through = removed, with the reason in brackets."
         % (args.duration, kept_s, len(kept)), ""]
restarts = [r for r in removed if r["reason"] == "restart"]
for u in units:
    for r in restarts:
        if abs(r["end"] - u["start"]) < 0.02 or (u["start"] <= r["start"] < u["end"]):
            lines.append("%6.2f  ~~%s~~  [restart]" % (r["start"], r["text"]))
    if u["why"]:
        lines.append("%6.2f  ~~%s~~  [%s]" % (u["start"], u["text"], u["why"]))
    else:
        lines.append("%6.2f  %s" % (u["start"], u["text"]))
silences = [r for r in removed if r["reason"].startswith("silence")]
if silences:
    lines += ["", "Silence trimmed: %d gaps, %.1f s in all." % (len(silences), sum(r["end"] - r["start"] for r in silences))]
with open(os.path.join(args.out_dir, "PAPER-CUT.md"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")

print("paper cut: %d segments, %.1f s of %.1f s kept | out: %d sentences, %d restarts, %d silences"
      % (len(kept), kept_s, args.duration, sum(1 for u in units if u["why"]), len(restarts), len(silences)))
