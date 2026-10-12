#!/usr/bin/env python3
"""beat-check.py: every card lands on its spoken word (run after authoring and after every re-time).

Each element with data-anchor="exact spoken words" is looked up in the flat cut's transcript (the occurrence nearest
its entry time). Its entry - data-at when it has one (a list item), else data-start - must fall between --early s
before the anchor's first word (default 0.60) and --late s after it (default 0.10). Entrances take ~0.4 s, so an entry
~0.25 s ahead of the word lands the card as the word is said.

It also FAILS on:
  NO-ANCHOR  a .card-host without data-anchor, or a <video> cutaway without one (the main #bg-video and #fg-matte
             are exempt). Something that should appear on no particular word (a series tag at 0.2 s) gets
             data-unanchored instead.
  MISS       the anchor words are not in the transcript.
  stale      transcript.json older than the video (input-video.mp4 next to the index, or --video): the words belong
             to another cut. Re-transcribe the flat cut, or pass --allow-stale.
--suggest prints an entry time for every anchored element (word - --lead) and an anchor for every NO-ANCHOR one.

Usage: python beat-check.py --index W/public/index.html --transcript W/transcript.json [--suggest]
Exit 1 on any problem.
"""
import argparse
import os
import sys
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cutlib import load_words, tokens  # noqa: E402

cli = argparse.ArgumentParser(description="Check every card's entry against its spoken anchor word.")
cli.add_argument("--transcript", required=True, help="the flat cut's transcript.json")
cli.add_argument("--index", required=True, help="the composition, W/public/index.html")
cli.add_argument("--suggest", action="store_true", help="print entry times (and anchors) that would pass")
cli.add_argument("--lead", type=float, default=0.25, help="how far ahead of its word --suggest puts an entry (s)")
cli.add_argument("--early", type=float, default=0.60, help="the most an entry may lead its word by (s)")
cli.add_argument("--late", type=float, default=0.10, help="the most an entry may trail its word by (s)")
cli.add_argument("--video", help="file the transcript must be newer than (default: input-video.mp4 beside the index)")
cli.add_argument("--allow-stale", action="store_true", help="only warn when the transcript is older than the video")
args = cli.parse_args()

# the transcript as one flat token stream: [(token, start of the word it came from)]
stream_ = [(tok, w["start"]) for w in load_words(args.transcript) for tok in tokens(w["text"])]


def locate(phrase, near):
    want = tokens(phrase)
    if not want:
        return None
    hits = [stream_[i][1] for i in range(len(stream_) - len(want) + 1)
            if all(stream_[i + k][0] == want[k] for k in range(len(want)))]
    return min(hits, key=lambda t: abs(t - near)) if hits else None


def words_from(t, n=3):
    after = [tok for tok, st in stream_ if st >= t]
    return " ".join(after[:n])


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.found = []

    def handle_starttag(self, tag, attrs):
        if tag in ("div", "video"):
            self.found.append((tag, dict(attrs)))

    handle_startendtag = handle_starttag


def number(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


problems = 0
notes = []
video = args.video if args.video else os.path.join(os.path.dirname(os.path.abspath(args.index)), "input-video.mp4")
tx_name, video_name = os.path.basename(args.transcript), os.path.basename(video)
if not os.path.isfile(video):
    notes.append("(staleness not checked: %s does not exist)" % video)
elif os.stat(args.transcript).st_mtime < os.stat(video).st_mtime:
    msg = "%s predates %s: the words may belong to an older cut, transcribe the current one" % (tx_name, video_name)
    if args.allow_stale:
        notes.append("WARN " + msg + "  [--allow-stale]")
    else:
        notes.append("FAIL " + msg)
        problems += 1

parser = Elements()
with open(args.index, encoding="utf-8") as fh:
    parser.feed(fh.read())

rows = []  # id, entry, which attr, anchor, word time, status
for tag, at in parser.found:
    eid = at.get("id") or "?"
    attr = "data-at" if "data-at" in at else "data-start"
    entry = number(at.get(attr))
    anchor = at.get("data-anchor")
    if anchor is None:
        cutaway = tag == "video" and eid not in ("bg-video", "fg-matte")
        if ("card-host" in (at.get("class") or "").split() or cutaway) and "data-unanchored" not in at:
            rows.append((eid, entry, attr, "", None, "NO-ANCHOR"))
            problems += 1
        continue
    if entry is None:
        continue
    said = locate(anchor, entry)
    if said is None:
        status = "MISS"
    elif said - entry < -args.late:
        status = "LATE"
    elif said - entry > args.early:
        status = "EARLY"
    else:
        status = "OK"
    problems += status != "OK"
    rows.append((eid, entry, attr, anchor, said, status))

for line in notes:
    print(line)
if notes:
    print()
print("%-22s %8s %8s %7s  %-9s %s" % ("id", "entry", "word", "slack", "status", "anchor"))
for eid, entry, attr, anchor, said, status in rows:
    print("%-22s %8s %8s %7s  %-9s %s" % (
        eid, ("%.2f" % entry if entry is not None else "-") + ("@" if attr == "data-at" else " "),
        "%.2f" % said if said is not None else "-", "%+.2f" % (said - entry) if said is not None else "-", status, anchor[:40]))
if args.suggest:
    print("\nsuggested (word - %.2f s; @ = a data-at item):" % args.lead)
    for eid, entry, attr, anchor, said, status in rows:
        if said is not None:
            print('  %-22s %s="%.2f"' % (eid, attr, max(0.0, said - args.lead)))
        elif status == "NO-ANCHOR" and entry is not None:
            spoken = words_from(entry)
            hint = 'data-anchor="%s"  (the words said as it appears; or mark it data-unanchored)' % spoken if spoken \
                else "no words follow it: mark it data-unanchored"
            print("  %-22s %s" % (eid, hint))
print("\n%d checked, %d problem(s)%s" % (len(rows), problems, "" if problems else ": every card is on its word"))
sys.exit(1 if problems else 0)
