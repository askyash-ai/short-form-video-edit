#!/usr/bin/env python3
"""find-joins.py: every jump cut in the flat cut, found in the picture itself (not from an edit list that the dead-air
pass has since changed). A join between two takes, or a pause trimmed out of one, is a single-frame jump: the
difference between two consecutive frames spikes far above the frame-to-frame motion around it. Talking, nodding and
hand moves change the picture gradually at 30/60 fps; a cut changes it all at once.

Decodes the video once, small and grey (96x170), scores each frame by its mean absolute difference from the one before,
and keeps a frame whose score is over --ratio x the median of its +/- 0.5 s neighbourhood AND over --floor (absolute,
0-255 scale), at most one per --min-gap s. Writes joins.json ({"video", "fps", "joins": [t, ...], "scores": [...]})
for reel-check.mjs --joins, and prints the camSet lines to paste.

Usage: python find-joins.py --video W/public/input-video.mp4 [--out W/joins.json] [--ratio 4] [--floor 3] [--min-gap 0.4]
"""
import argparse, json, os, subprocess, sys

import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--video", required=True)
ap.add_argument("--out", help="default: joins.json next to public/ (the project folder)")
ap.add_argument("--ratio", type=float, default=4.0, help="spike over the local median motion")
ap.add_argument("--floor", type=float, default=3.0, help="minimum mean abs difference, 0-255")
ap.add_argument("--min-gap", type=float, default=0.4)
a = ap.parse_args()

p = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                               "-of", "json", a.video], capture_output=True, text=True, check=True).stdout)
n, d = [int(x) for x in p["streams"][0]["r_frame_rate"].split("/")]
fps = n / d if d else 30.0
W, H = 96, 170
raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-threads", "4", "-i", a.video, "-map", "0:v:0", "-vf",
                      "scale=%d:%d:flags=area,format=gray" % (W, H), "-f", "rawvideo", "-"], capture_output=True).stdout
fr = np.frombuffer(raw, np.uint8)
fr = fr[: len(fr) // (W * H) * W * H].reshape(-1, H, W).astype(np.int16)
if len(fr) < 3:
    sys.exit("could not decode %s" % a.video)
diff = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))        # diff[i] = change from frame i to frame i+1
half = max(2, int(round(fps * 0.5)))
joins, scores = [], []
for i, v in enumerate(diff):
    lo, hi = max(0, i - half), min(len(diff), i + half + 1)
    around = np.concatenate([diff[lo:i], diff[i + 1:hi]])
    med = float(np.median(around)) if len(around) else 0.0
    if v >= a.floor and v >= a.ratio * max(med, 0.25) and v == diff[lo:hi].max():
        t = (i + 1) / fps                                    # the first frame of the new shot
        if joins and t - joins[-1] < a.min_gap:
            continue
        joins.append(round(t, 3)); scores.append(round(float(v / max(med, 0.25)), 1))
out = a.out or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(a.video))), "joins.json")
json.dump({"video": os.path.basename(a.video), "fps": fps, "joins": joins, "scores": scores}, open(out, "w"), indent=1)
print("%d jump cut(s) in %s (%.0f fps) -> %s" % (len(joins), os.path.basename(a.video), fps, out))
for t, s in zip(joins, scores):
    print("  %7.3f s  (x%.1f over the motion around it)" % (t, s))
print("\ncamSet at each (alternate the framing; reel-check --joins checks it):")
print("  " + " ".join("camSet(%.3f, %s);" % (t + 0.003, "1.0" if k % 2 else "Z") for k, t in enumerate(joins)))
print("  Z = 1.12 for a 4K source, 1.08 for HD (SKILL.md \"Camera\")")
