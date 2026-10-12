#!/usr/bin/env python3
"""phrase-times.py: look phrases up in a word-level transcript and print when each one is said - from its first
word's start to its last word's end, for up to four occurrences (case and punctuation do not matter). Handy for
anchoring beats without scrolling through the transcript.
Usage: python phrase-times.py --transcript W/transcript.json "most important part" "comment skill" [--after 30]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cutlib import load_words, tokens  # noqa: E402

cli = argparse.ArgumentParser(description="Find phrases in a word-level transcript.")
cli.add_argument("phrases", nargs="+", help="one or more phrases, each in quotes")
cli.add_argument("--after", type=float, default=0.0, help="ignore anything said before this time (s)")
cli.add_argument("--transcript", required=True, help="transcript.json")
args = cli.parse_args()

seq = [(tok, w["start"], w["end"]) for w in load_words(args.transcript) for tok in tokens(w["text"])]
for phrase in args.phrases:
    want = tokens(phrase)
    hits = [(seq[i][1], seq[i + len(want) - 1][2]) for i in range(len(seq) - len(want) + 1)
            if want and seq[i][1] >= args.after and [s[0] for s in seq[i:i + len(want)]] == want]
    if not hits:
        print("%-44s  NOT FOUND" % phrase)
        continue
    more = "   (+%d more)" % (len(hits) - 4) if len(hits) > 4 else ""
    print("%-44s  %s%s" % (phrase, "   ".join("%.2f-%.2f" % h for h in hits[:4]), more))
