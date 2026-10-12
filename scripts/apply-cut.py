#!/usr/bin/env python3
"""apply-cut.py: render cut-list.json into a frame-accurate flat cut (one encode) and write cut-map.json.

Every kept start and end is snapped to the source's frame grid first (r_frame_rate, 30000/1001 included, counted from
the video stream's start), so each segment holds whole frames and its audio is cut at exactly the same instants.
Without the snap, video and audio of each piece differ by a fraction of a frame and hundreds of joins drift the cut
by a second. Each piece gets a 20 ms audio fade at both ends (no clicks at joins).

Output: H.264 (CRF --crf), a keyframe every second, constant frame rate (the source's own, rounded: 59.94 -> 60),
yuv420p, BT.709 tags, AAC 256k 48 kHz, faststart. 4K sources cap x264's threads (memory on 8 GB machines).
cut-map.json (next to the cut list): {"cuts": [flat time of every join], "segments": [{flat_start, flat_end,
src_start, src_end, frames}], "flat_duration", "source_fps", "frame_origin"} - used by patch-cut.py --drop-flat
and dead-air.py. The finished file is probed: if its video length is off cut-map.json by more than a frame, or video
and audio differ by more than 0.12 s, it prints DRIFT and exits 2.

Usage: python apply-cut.py --input W/conformed/take.mp4 --cut-list W/cut-list.json --out W/public/input-video.mp4 [--fps 30]
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cutlib import fail, load_json, probe, save_json, stream  # noqa: E402

cli = argparse.ArgumentParser(description="Render a cut list into a frame-accurate flat cut.")
cli.add_argument("--cut-list", required=True, help="cut-list.json (its folder also gets cut-map.json)")
cli.add_argument("--input", required=True, help="the source the cut list refers to")
cli.add_argument("--out", required=True, help="the flat cut, usually W/public/input-video.mp4")
cli.add_argument("--preset", default="fast", help="x264 preset")
cli.add_argument("--crf", type=int, default=16, help="x264 quality (lower = better)")
cli.add_argument("--fps", type=int, help="output frame rate (default: the source's, rounded to 24/25/30/48/50/60)")
args = cli.parse_args()

info = probe(args.input, "stream=codec_type,width,height,start_time,r_frame_rate:format=start_time")
v, a = stream(info, "video"), stream(info, "audio")
if v is None:
    fail("no video stream in %s" % args.input)
if a is None:
    fail("no audio stream in %s: apply-cut cuts picture and sound together" % args.input)


def as_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


try:
    rate = Fraction(v.get("r_frame_rate", "30/1"))
except (ValueError, ZeroDivisionError):
    rate = Fraction(30)
if rate <= 0:
    rate = Fraction(30)
fps = args.fps or min((24, 25, 30, 48, 50, 60), key=lambda c: abs(c - float(rate)))
origin = Fraction(as_float(v.get("start_time")) - as_float(info.get("format", {}).get("start_time"))).limit_denominator(10 ** 6)
half = 1 / (2 * rate)
big = max(int(v.get("width") or 0), int(v.get("height") or 0)) >= 3840


def frame_of(t):
    return int(round((Fraction(t).limit_denominator(10 ** 6) - origin) * rate))


def time_of(k):
    return origin + Fraction(k) / rate


FADE = 0.02
graph, labels, segments, skipped = [], [], [], []
flat = Fraction(0)
for seg in load_json(args.cut_list)["kept"]:
    k0, k1 = max(0, frame_of(seg["start"])), frame_of(seg["end"])
    if k1 <= k0:
        skipped.append(seg)
        continue
    n = len(labels)
    t0, t1 = time_of(k0), time_of(k1)
    length = float(Fraction(k1 - k0) / rate)
    # video keeps frames k0..k1-1 (a half-frame guard either side); audio is cut at the same instants, faded 20 ms
    graph.append("[0:v]trim=%.6f:%.6f,setpts=PTS-STARTPTS[v%d]" % (t0 - half, t1 - half, n))
    graph.append(("[0:a]atrim=%.6f:%.6f,asetpts=PTS-STARTPTS," % (t0, t1)) +
                 ("afade=in:0:d=%.3f,afade=out:st=%.6f:d=%.3f[a%d]" % (FADE, max(0.0, length - FADE), FADE, n)))
    labels.append("[v%d][a%d]" % (n, n))
    segments.append({"flat_start": round(float(flat), 3), "flat_end": round(float(flat + Fraction(k1 - k0) / rate), 3),
                     "src_start": round(float(t0), 4), "src_end": round(float(t1), 4), "frames": k1 - k0})
    flat += Fraction(k1 - k0) / rate
if not labels:
    fail("no kept segment is at least one frame long")
graph.append("%sconcat=n=%d:v=1:a=1[v][a]" % ("".join(labels), len(labels)))
fc = ";".join(graph)

# a long graph goes in a file (Windows caps a command line at ~32k characters); FFmpeg 7+ reads it with -/filter_complex
graph_args, tmp = ["-filter_complex", fc], None
if len(fc) > 6000:
    tmp = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
    tmp.write(fc)
    tmp.close()
    ver = re.search(r"ffmpeg version (?:n)?(\d+)", subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout)
    new = ver is None or int(ver.group(1)) >= 7
    graph_args = ["-/filter_complex", tmp.name] if new else ["-filter_complex_script", tmp.name]

os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
video = ["-c:v", "libx264", "-crf", str(args.crf), "-preset", args.preset, "-pix_fmt", "yuv420p", "-keyint_min", str(fps), "-g", str(fps)]
if big:
    video += ["-x264-params", "threads=4:rc-lookahead=10"]          # 4K: x264's own thread count runs out of memory on 8 GB
colour = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
sound = ["-c:a", "aac", "-ar", "48000", "-b:a", "256k"]
cmd = (["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", args.input] + graph_args + ["-map", "[v]", "-map", "[a]"]
       + ["-fps_mode", "cfr", "-r", str(fps)] + video + colour + sound + ["-movflags", "+faststart+write_colr", args.out])
try:
    done = subprocess.run(cmd)
finally:
    if tmp:
        os.unlink(tmp.name)
if done.returncode:
    fail("ffmpeg failed (exit %d)" % done.returncode)

flat_d = round(float(flat), 3)
cut_map = {"flat_duration": flat_d, "cuts": [s["flat_start"] for s in segments[1:]], "segments": segments,
           "frame_origin": round(float(origin), 6), "source_fps": "%d/%d" % (rate.numerator, rate.denominator)}
save_json(os.path.join(os.path.dirname(os.path.abspath(args.cut_list)), "cut-map.json"), cut_map)
for s in skipped:
    print("ignored %.3f-%.3f (under one frame)" % (s["start"], s["end"]))
print("%s: %d pieces, %d joins, %.3f s, snapped to %g fps" % (args.out, len(segments), len(segments) - 1, flat_d, float(rate)))

res = probe(args.out, "stream=codec_type,duration")
vd = as_float((stream(res, "video") or {}).get("duration")) or None
ad = as_float((stream(res, "audio") or {}).get("duration")) or None
problems = []
if not vd or abs(vd - flat_d) > 1.0 / fps + 1e-6:
    problems.append("the picture lasts %s s but cut-map.json says %.3f s (one frame allowed)" % (vd and "%.3f" % vd, flat_d))
if not (vd and ad) or abs(vd - ad) > 0.12:
    problems.append("picture %s s and sound %s s differ by more than 0.12 s" % (vd and "%.3f" % vd, ad and "%.3f" % ad))
if problems:
    print("!!! DRIFT: " + "; ".join(problems) + ". Do not build on this file or its cut-map.json.")
    sys.exit(2)
print("verified: picture %.3f s, sound %.3f s, cut-map %.3f s (off by %+.1f ms)" % (vd, ad, flat_d, 1000 * (vd - flat_d)))
