#!/usr/bin/env python3
"""cover-frames.py: numbered cover candidates for the creator to pick from, BEFORE make-cover.mjs runs.

Added 2026-10-11: the creator did not like the expression on aotw-01's first cover (picked by Claude, mid-word) and
picked frame 05 from a sheet like this one. Mid-word frames catch the mouth half open; the candidates here sit just
after a word ends (sentence ends and pauses first), outside every L panel (the cover needs the face), spread over the
reel. Writes W/renders/cover-options.png (6 x 3, numbered, the face crop as the cover shows it) and
W/renders/cover-options.txt ("NN time"). Send the sheet, ask for a number, then: make-cover.mjs --at <time>.

  python cover-frames.py --project W [--n 18]
"""
import argparse, json, os, re, subprocess, tempfile

ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True)
ap.add_argument("--n", type=int, default=18)
a = ap.parse_args()
W = a.project; PUB = os.path.join(W, "public"); OUT = os.path.join(W, "renders"); os.makedirs(OUT, exist_ok=True)
words = json.load(open(os.path.join(W, "transcript.json"), encoding="utf-8"))["words"]
html = open(os.path.join(PUB, "index.html"), encoding="utf-8").read()
L = [(float(s), float(s) + float(d)) for s, d in re.findall(r'data-size="l"[^>]*?data-start="([\d.]+)" data-duration="([\d.]+)"', html)]
D = max(w["end"] for w in words)
covered = lambda t: t > D - 0.05 or any(s - 0.04 <= t <= e + 0.30 for s, e in L)   # an L panel is up from its start to its exit

jf = os.path.join(W, "joins.json")
J = json.load(open(jf))["joins"] if os.path.exists(jf) else []

cands = []   # (priority, time): 0 = sentence end, 1 = a pause after a word, 2 = any word end
for p, q in zip(words, words[1:] + [None]):
    gap = (q["start"] - p["end"]) if q else 0.3
    t = round(p["end"] + min(max(gap, 0.06) / 2, 0.12), 2)
    t = min([t] + [round(j - 0.03, 2) for j in J if p["end"] < j <= t + 0.03])   # stay on the take the word is in
    pr = 0 if p["text"].rstrip().endswith((".", "?", "!")) else 1 if gap >= 0.15 else 2
    if not covered(t):
        cands.append((pr, t))
cands.insert(0, (0, round(max(0.3, words[0]["start"] - 0.1), 2)))
pick = sorted({t for pr, t in cands if pr == 0})
for want in (1, 2):
    if len(pick) >= a.n:
        break
    extra = sorted(t for pr, t in cands if pr == want and all(abs(t - x) > 0.6 for x in pick))
    step = max(1, len(extra) // max(1, a.n - len(pick)))
    pick = sorted(set(pick + extra[::step][: a.n - len(pick)]))
if len(pick) > a.n:   # spread evenly
    pick = [pick[round(i * (len(pick) - 1) / (a.n - 1))] for i in range(a.n)]

tmp = tempfile.mkdtemp()
font = "fontfile='C\\:/Windows/Fonts/arialbd.ttf':" if os.name == "nt" else ""
for i, t in enumerate(pick):
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-threads", "2", "-ss", "%.2f" % t, "-i", os.path.join(PUB, "input-video.mp4"),
                    "-frames:v", "1", "-vf", "scale=1080:1920,crop=1080:1350:0:300,scale=300:375,drawtext=%stext='%02d':x=10:y=10:fontsize=40:"
                    "fontcolor=white:box=1:boxcolor=black@0.65:boxborderw=6" % (font, i + 1), os.path.join(tmp, "f%02d.png" % i)], check=True)
cols = 6; rows = -(-len(pick) // cols)
subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", os.path.join(tmp, "f%02d.png"), "-vf",
                "tile=%dx%d:padding=6:color=white" % (cols, rows), "-frames:v", "1", os.path.join(OUT, "cover-options.png")], check=True)
open(os.path.join(OUT, "cover-options.txt"), "w").write("".join("%02d %.2f\n" % (i + 1, t) for i, t in enumerate(pick)))
print("%d candidates -> %s (map: cover-options.txt)" % (len(pick), os.path.join(OUT, "cover-options.png")))
