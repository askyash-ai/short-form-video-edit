#!/usr/bin/env python3
"""broll-conform.py: make one stock clip, screen recording, AI clip or still ready to drop into a vertical video.

Output: filled (never letterboxed) to 2160x3840 @ 60 by default (a 4K60 reel); --hd --fps 30 gives 1080x1920 @ 30,
--size WxH any other frame (a landscape plate inside a card). No audio, H.264 with a keyframe every half second (a
clip that seeks badly freezes in the render), BT.709 tags. A still (.png/.jpg/.webp) becomes a slow centred push-in
of --dur seconds, ending at --push scale. --vf runs your own ffmpeg filters first, in source pixels: crop a logo out
("crop=3490:1964:175:0") or blur a browser bar. --grade nudges generated colour toward camera footage.
Writes the clip, <out>.sheet.png (first, middle and last frame: look at hands, screens and faces) and prints a beat line.

Usage:
  python broll-conform.py --in gen/desk.mp4 --out W/public/broll/desk.mp4 [--start 0.4] [--dur 4] [--grade]
  python broll-conform.py --in gen/desk.png --out W/public/broll/desk.mp4 --dur 4 [--push 1.08]
  add --hd --fps 30 for an HD30 reel, or --size WxH
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cutlib import fail, probe, stream  # noqa: E402

cli = argparse.ArgumentParser(description="Conform a clip or still into a vertical cutaway.")
cli.add_argument("--in", dest="src", required=True, metavar="FILE", help="clip or still (.png/.jpg/.webp)")
cli.add_argument("--out", required=True, help="the conformed .mp4")
cli.add_argument("--hd", action="store_true", help="1080x1920 instead of 2160x3840")
cli.add_argument("--fps", type=int, default=60, help="output frame rate")
cli.add_argument("--size", help="any other WIDTHxHEIGHT (wins over --hd)")
cli.add_argument("--4k", dest="uhd", action="store_true", help="2160x3840, which is already the default")
cli.add_argument("--dur", type=float, help="length to keep in s (a still needs it; a clip defaults to the rest)")
cli.add_argument("--start", type=float, default=0.0, help="s to skip first (generated clips often settle for a moment)")
cli.add_argument("--push", type=float, default=1.08, help="stills: the zoom the slow push ends on (1.00 = static)")
cli.add_argument("--grade", action="store_true", help="a touch more contrast, a touch less saturation, like camera footage")
cli.add_argument("--vf", default="", help="your own ffmpeg filters, run first on the source (crop a logo, blur a bar)")
args = cli.parse_args()

W, H = (1080, 1920) if args.hd else (2160, 3840)
if args.size:
    try:
        W, H = [int(x) for x in args.size.lower().split("x")]
    except ValueError:
        fail("--size %s: expected WxH, e.g. 1080x1920" % args.size)
IMAGE = {".png", ".jpg", ".jpeg", ".webp"}
still = os.path.splitext(args.src.lower())[1] in IMAGE
if still and not args.dur:
    fail("a still needs --dur (the length of the push-in)")

grade = "" if not args.grade else ",eq=contrast=1.03:saturation=0.92"
out_dir = os.path.dirname(os.path.abspath(args.out))
if not os.path.isdir(out_dir):
    os.makedirs(out_dir)
if still:
    frames = max(1, int(round(args.dur * args.fps)))
    # the push runs on a canvas twice the output size so each step is sub-pixel: smooth, not stepped
    vf = ("scale={w2}:{h2}:force_original_aspect_ratio=increase:flags=lanczos,crop={w2}:{h2},"
          "zoompan=z='1+({p}-1)*on/{last}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={n}:s={w}x{h}:fps={fps}{g},format=yuv420p"
          ).format(w2=W * 2, h2=H * 2, p=args.push, last=max(1, frames - 1), n=frames, w=W, h=H, fps=args.fps, g=grade)
    cmd = ["ffmpeg", "-nostdin", "-y", "-v", "error", "-loop", "1", "-i", args.src, "-frames:v", str(frames), "-vf", vf]
else:
    info = probe(args.src)
    left = float(info["format"]["duration"]) - args.start
    if args.dur and args.dur > left + 0.01:
        fail("--dur %.2f is longer than the %.2f s left after --start %.2f" % (args.dur, left, args.start))
    keep = args.dur or left
    fill = "scale=w=%d:h=%d:force_original_aspect_ratio=increase:flags=lanczos,crop=w=%d:h=%d" % (W, H, W, H)
    vf = ",".join(part for part in (args.vf, fill, "fps=%d" % args.fps) if part) + grade + ",format=yuv420p"
    cmd = ["ffmpeg", "-nostdin", "-y", "-v", "error", "-ss", "%.3f" % args.start, "-t", "%.3f" % keep, "-i", args.src, "-vf", vf]
if max(W, H) >= 3840:
    cmd += ["-x264-params", "threads=4:rc-lookahead=10"]      # 4K: x264's automatic threads run out of memory on 8 GB
gop = max(1, args.fps // 2)
cmd += ["-an", "-c:v", "libx264", "-crf", "14", "-preset", "slow", "-sc_threshold", "0", "-keyint_min", str(gop), "-g", str(gop),
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-movflags", "+faststart", args.out]
if subprocess.run(cmd).returncode:
    fail("ffmpeg failed on %s" % args.src)

out = probe(args.out)
v = stream(out, "video")
if stream(out, "audio"):
    fail("FAIL %s still has audio" % args.out)
dur = float(out["format"]["duration"])
total_frames = int(dur * args.fps)
sheet = args.out + ".sheet.png"
picks = "+".join("eq(n,%d)" % n for n in (0, total_frames // 2, max(0, total_frames - 2)))
subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", args.out, "-frames:v", "1", "-fps_mode", "vfr",
                "-vf", "select='%s',scale=640:-2,tile=3x1" % picks, sheet], check=True)
print("%s ready: %dx%d, %s fps, %.2f s, silent" % (args.out, v["width"], v["height"], v["r_frame_rate"], dur))
print("check %s before using it: hands, screens with text, faces that changed between frames" % sheet)
name = os.path.splitext(os.path.basename(args.out))[0]
print("beat:", json.dumps({"type": "clip", "id": name[:12], "src": "broll/" + os.path.basename(args.out), "in": 0.0,
                           "out": round(min(dur, 4.0), 2), "anchor": "the words spoken as it cuts in"}))
