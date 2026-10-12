#!/usr/bin/env python3
"""cutlist-to-edl.py: convert cut-list.json into the EDL that build-edl-review.mjs turns into CUT-REVIEW.html (the
original and the edit side by side; click a red mark to hear what was removed). Checkpoint A for a long take.

Usage:
  python cutlist-to-edl.py --cut-list W/cut-list.json --out W/cut-edl.json
  node "$SK/scripts/build-edl-review.mjs" W/cut-edl.json --original W/raw/take.MOV --edited W/public/input-video.mp4 \
       --output W/CUT-REVIEW.html
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cutlib import gaps, load_json, save_json  # noqa: E402

cli = argparse.ArgumentParser(description="cut-list.json -> the review page's EDL")
cli.add_argument("--out", required=True, help="the EDL json to write")
cli.add_argument("--cut-list", required=True, help="cut-list.json from paper-cut or hand-cut")
args = cli.parse_args()

plan = load_json(args.cut_list)
duration = float(plan["source_duration"])
reasons = plan.get("removed", [])
kept = sorted(plan["kept"], key=lambda seg: (seg["start"], seg["end"]))

deletes = []
for a, b in gaps(kept, duration):
    why = [r["reason"] + (": " + r["text"][:60] if r.get("text") else "") for r in reasons if r["start"] < b and a < r["end"]]
    deletes.append({"start": a, "end": b, "reasons": (why or ["tail" if b >= duration - 0.001 else "removed"])[:4]})

removed = round(sum(d["end"] - d["start"] for d in deletes), 3)
edl = {"agent": "short-form-video-edit/cut", "source_duration": duration, "removed": removed,
       "edited_duration": round(duration - removed, 3), "keep_ranges": [dict(start=s["start"], end=s["end"]) for s in kept],
       "delete_ranges": deletes, "params": {"gap": "speech chunks", "headPad": 0.15, "tailPad": 0.45}}
save_json(args.out, edl)
print("%s: %d stretches cut (%.1f s), %d kept, %.1f s left of %.1f s" % (args.out, len(deletes), removed, len(kept),
                                                                      edl["edited_duration"], duration))
