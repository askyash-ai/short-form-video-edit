#!/usr/bin/env python3
"""stutter-scan.py: run the word-level mistake finder (find-cut-candidates.mjs, an MIT-licensed script that ships
beside this one; notice in LICENSES/MIT-starter-kit.txt) over a flat cut, as a second opinion after the paper cut. It adds stutters ("the the", "I- I") and near-duplicate lines.
Run it on the FLAT cut's transcript, so every candidate is something still in the edit, and read each one in
context: emphasis ("never, never") looks exactly like a stutter and must stay. Needs Node.js.
Approved cuts go back through patch-cut.py --drop-flat (their times are flat-cut times).

Usage: python stutter-scan.py --transcript W/transcript.json --out-dir W/candidates
Writes candidates/<stem>.cut-candidates.json and .md and prints the summary and the .md.
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cutlib import fail, load_words, save_json  # noqa: E402

cli = argparse.ArgumentParser(description="Word-level stutter and duplicate scan.")
cli.add_argument("--out-dir", required=True, help="where the candidate files go")
cli.add_argument("--transcript", required=True, help="the FLAT cut's transcript.json")
args = cli.parse_args()

finder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "find-cut-candidates.mjs")
if not os.path.exists(finder):
    fail("find-cut-candidates.mjs is missing from %s" % os.path.dirname(finder))

words = load_words(args.transcript)
if not words:
    fail("no words in %s" % args.transcript)
os.makedirs(args.out_dir, exist_ok=True)
flat = os.path.join(args.out_dir, "flat-transcript.json")
save_json(flat, {"language_code": "en", "audio_duration_secs": words[-1]["end"], "text": " ".join(w["text"] for w in words),
                 "words": [dict(w, type="word") for w in words]})
run = subprocess.run(["node", finder, flat, "--out-dir", args.out_dir], capture_output=True, text=True, encoding="utf-8")
if run.returncode:
    fail(run.stderr.strip() or "find-cut-candidates.mjs failed")
result = json.loads(run.stdout)
report = result["outputs"]["md"]
kinds = ", ".join("%s %s" % (n, kind) for kind, n in result["counts"].items()) or "none"
print("%d candidate(s) (%s), written to %s\n" % (result["candidates"], kinds, report))
with open(report, encoding="utf-8") as fh:
    print(fh.read())
