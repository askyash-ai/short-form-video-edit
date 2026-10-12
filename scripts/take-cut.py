#!/usr/bin/env python3
"""take-cut.py: the many-takes flat cut in one pass, smooth by default (approved on aotw-01 v4, 2026-10-11).

Input: W/cuts/picks.tsv (one row per script line, in order: line, take, in, out[, note]; '#' lines skipped), the
take's word transcript W/tx/<take>.json (normalized, raw-take time) and the conformed take W/conformed/<take>.mp4.

Per take: the words inside [in, out]; every pause over --max (or --max-sentence after . ? !) becomes a SOFT cut: the
picture and the sound cross-dissolve for --xfade s (0.08) with --margin s (0.10) kept either side of the gap, so the
pause left is ~0.12 s (2 x margin - xfade) and the head never jumps. Between takes: a HARD cut (the reframe goes there).
Output: W/cuts/<take>.filter.txt, W/cuts/<take>.mp4, W/cuts/concat-list.txt, W/cuts/plan.json (per take: start, dur,
soft-cut times, in flat-cut time) and W/public/input-video.mp4 (yuv420p, BT.709, a keyframe every second).

  python take-cut.py --project W [--fps 60] [--plan-only]

Run it detached (scripts/bg-job.ps1) on 4K: one take at a time, threads capped. Afterwards transcribe the flat cut and
run find-joins.py: the hard joins it finds land 0.03-0.06 s after plan.json's (each take's length rounds up to a whole
frame), so use find-joins' times for the reframes; a dissolve over a big head move can also show up there (score ~4-9x,
against 18-38x for a hard join): it is not a jump cut and gets no reframe.
"""
import argparse, json, os, subprocess, sys

ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True)
ap.add_argument("--fps", type=int, default=60)
ap.add_argument("--xfade", type=float, default=0.08)
ap.add_argument("--margin", type=float, default=0.10)
ap.add_argument("--max", type=float, default=0.30, help="longest pause kept inside a sentence")
ap.add_argument("--max-sentence", type=float, default=0.25, help="longest pause kept after . ? !")
ap.add_argument("--plan-only", action="store_true", help="write the filters and plan.json, encode nothing")
a = ap.parse_args()
W = a.project; C = os.path.join(W, "cuts"); X, M = a.xfade, a.margin
assert 2 * M > X + 0.02, "margin too small for the crossfade"

picks = []
for l in open(os.path.join(C, "picks.tsv"), encoding="utf-8"):
    if not l.strip() or l.lstrip().startswith("#"):
        continue
    f = l.rstrip("\n").split("\t")
    picks.append((f[1], float(f[2]), float(f[3])))

plan, t = [], 0.0
for take, a_in, a_out in picks:
    words = [w for w in json.load(open(os.path.join(W, "tx", take + ".json"), encoding="utf-8"))["words"]
             if w["start"] >= a_in - 0.01 and w["end"] <= a_out + 0.01]
    segs, s = [], a_in
    for p, q in zip(words, words[1:]):
        gap = q["start"] - p["end"]
        sent = p["text"].rstrip().endswith((".", "?", "!"))
        if gap > (a.max_sentence if sent else a.max) + 1e-6 and gap > 2 * M - X + 0.02:
            segs.append((s, round(p["end"] + M, 3))); s = round(q["start"] - M, 3)
    segs.append((s, a_out))
    L = []
    for i, (st, en) in enumerate(segs):
        L.append("[0:v]trim=start=%.3f:end=%.3f,setpts=PTS-STARTPTS[v%d];[0:a]atrim=start=%.3f:end=%.3f,asetpts=PTS-STARTPTS[a%d];" % (st, en, i, st, en, i))
    v, au, ln, soft = "v0", "a0", segs[0][1] - segs[0][0], []
    for i in range(1, len(segs)):
        L.append("[%s][v%d]xfade=transition=fade:duration=%s:offset=%.3f[vx%d];[%s][a%d]acrossfade=d=%s:c1=tri:c2=tri[ax%d];"
                 % (v, i, X, ln - X, i, au, i, X, i))
        soft.append(round(t + ln - X / 2, 3))
        v, au, ln = "vx%d" % i, "ax%d" % i, ln + (segs[i][1] - segs[i][0]) - X
    # format=yuv420p: xfade hands x264 a 4:4:4 frame otherwise (the colour gate rejects a 4:4:4 source)
    L.append("[%s]format=yuv420p[v];[%s]afade=t=in:d=0.008,afade=t=out:st=%.3f:d=0.012[a]" % (v, au, ln - 0.012))
    open(os.path.join(C, take + ".filter.txt"), "w").write("\n".join(L))
    plan.append({"take": take, "in": a_in, "out": a_out, "segs": segs, "start": round(t, 3), "dur": round(ln, 3), "soft": soft})
    t += ln

json.dump(plan, open(os.path.join(C, "plan.json"), "w"), indent=1)
open(os.path.join(C, "concat-list.txt"), "w").write("".join("file '%s.mp4'\n" % p["take"] for p in plan))
for p in plan:
    print("%-10s start %6.2f dur %5.2f soft cuts %s" % (p["take"], p["start"], p["dur"], p["soft"]))
print("total %.2f s; hard joins %s" % (t, [p["start"] for p in plan[1:]]))
if a.plan_only:
    sys.exit(0)

ENC = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", "-g", str(a.fps), "-keyint_min", str(a.fps),
       "-x264-params", "threads=4:rc-lookahead=10", "-color_primaries", "bt709", "-color_trc", "bt709",
       "-colorspace", "bt709", "-color_range", "tv"]
for p in plan:
    r = subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-threads", "4", "-filter_threads", "2",
                        "-i", os.path.join(W, "conformed", p["take"] + ".mp4"),
                        "-/filter_complex", os.path.join(C, p["take"] + ".filter.txt"), "-map", "[v]", "-map", "[a]",
                        *ENC, "-c:a", "aac", "-b:a", "256k", "-ar", "48000", os.path.join(C, p["take"] + ".mp4")])
    print(("cut " if r.returncode == 0 else "CUT FAIL ") + p["take"], flush=True)
    if r.returncode:
        sys.exit(1)
os.makedirs(os.path.join(W, "public"), exist_ok=True)
r = subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-threads", "4", "-filter_threads", "2", "-f", "concat",
                    "-safe", "0", "-i", os.path.join(C, "concat-list.txt"), *ENC, "-c:a", "aac", "-b:a", "256k",
                    "-ar", "48000", "-movflags", "+faststart", os.path.join(W, "public", "input-video.mp4")])
print("concat ok" if r.returncode == 0 else "CONCAT FAIL", flush=True)
sys.exit(r.returncode)
