#!/usr/bin/env python3
"""ingest.py: list every clip in a raw/ folder in order, set aside the odd ones out, and optionally join the camera
clips into one source file.

Order: --order (comma-separated names without extension), else file name, then modification time. The most common
resolution is the camera; any other (a screen recording) is set aside, or pick clips explicitly with --only.
--concat joins them: a stream copy when every clip matches (codec, size, frame rate, audio), otherwise each odd clip
is re-encoded to the first one's format before joining. ingest.json records each clip's offset in the joined file,
so any time in it maps back to (clip, time).

Usage:
  python ingest.py --raw W/raw --out W                     # probe + ingest.json
  python ingest.py --raw W/raw --out W --concat            # also W/source.mp4
  python ingest.py ... --order IMG_0102,IMG_0101 --only IMG_0101,IMG_0102
"""
import argparse
import os
import subprocess
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cutlib import fail, probe, rate_of, save_json, stream  # noqa: E402

cli = argparse.ArgumentParser(description="Probe, order and optionally join raw clips.")
cli.add_argument("--raw", required=True, help="folder of camera clips (and anything else)")
cli.add_argument("--out", required=True, help="where ingest.json (and the joined file) go")
cli.add_argument("--only", default="", help="comma-separated clip names (no extension) to use")
cli.add_argument("--order", default="", help="comma-separated clip names in the order to use them")
cli.add_argument("--concat", action="store_true", help="also join the camera clips into one file")
cli.add_argument("--name", default="source.mp4", help="file name of the joined clip")
args = cli.parse_args()

EXT = (".mp4", ".mov", ".m4v", ".mxf")
paths = [os.path.join(args.raw, f) for f in os.listdir(args.raw) if f.lower().endswith(EXT)] if os.path.isdir(args.raw) else []
if not paths:
    fail("no video files in %s" % args.raw)


def describe(path):
    """One clip's facts, or None for a file without a picture."""
    info = probe(path, "stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt,sample_rate,channels:format=duration,size")
    pic, snd = stream(info, "video"), stream(info, "audio")
    if pic is None:
        return None
    snd = snd or {}
    clip = {"file": os.path.basename(path), "path": os.path.abspath(path), "mtime": os.path.getmtime(path)}
    clip.update(width=pic["width"], height=pic["height"], fps=round(rate_of(pic), 3), vcodec=pic.get("codec_name"),
                pix_fmt=pic.get("pix_fmt"))
    clip.update(acodec=snd.get("codec_name"), sample_rate=int(snd["sample_rate"]) if "sample_rate" in snd else None,
                channels=snd.get("channels", 0))
    clip.update(duration=float(info["format"]["duration"]), size=int(info["format"].get("size", 0)))
    return clip


clips = [c for c in map(describe, paths) if c]


def stem(c):
    return os.path.splitext(c["file"])[0]


if args.only:
    clips = [c for c in clips if stem(c) in set(args.only.split(","))]
if args.order:
    named = {stem(c): c for c in clips}
    unknown = [n for n in args.order.split(",") if n not in named]
    if unknown:
        fail("--order: %s not found in %s" % (", ".join(unknown), args.raw))
    clips = [named[n] for n in args.order.split(",")]
else:
    clips.sort(key=lambda c: (c["file"].lower(), c["mtime"]))
if not clips:
    fail("no clips left after --only")

sizes = Counter((c["width"], c["height"]) for c in clips)
camera = sizes.most_common(1)[0][0]
aside = [c for c in clips if (c["width"], c["height"]) != camera]
clips = [c for c in clips if c not in aside]
offset = 0.0
for c in clips:
    c["source_start"] = round(offset, 3)
    offset += c["duration"]
    c["source_end"] = round(offset, 3)

result = {"raw_dir": os.path.abspath(args.raw), "clips": clips, "set_aside": aside, "total_duration": round(offset, 3), "concat": None}
os.makedirs(args.out, exist_ok=True)
FORMAT = ("vcodec", "width", "height", "fps", "acodec", "sample_rate", "channels")
if args.concat:
    first = clips[0]

    def shape(c):
        return tuple(c[k] for k in FORMAT)

    uniform = len({shape(c) for c in clips}) == 1
    parts = []
    for c in clips:
        p = c["path"]
        if not uniform and shape(c) != shape(first):
            p = os.path.join(args.out, "normalised-%s.mp4" % stem(c))
            if not os.path.exists(p):
                subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", c["path"], "-r", str(first["fps"]),
                                "-vf", "scale=%d:%d" % (first["width"], first["height"]), "-pix_fmt", "yuv420p",
                                "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-ar", "48000", "-c:a", "aac", "-b:a", "256k", p],
                               check=True)
        parts.append(p)
    listing = os.path.join(args.out, "concat-list.txt")
    with open(listing, "w", encoding="utf-8") as fh:
        fh.writelines("file '%s'\n" % p.replace("\\", "/").replace("'", "'\\''") for p in parts)
    target = os.path.join(args.out, args.name)
    codec = ["-c", "copy"] if uniform else ["-c:v", "libx264", "-preset", "fast", "-crf", "16", "-c:a", "aac", "-b:a", "256k"]
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", listing, *codec,
                    "-movflags", "+faststart", target], check=True)
    result["concat"] = {"file": target, "stream_copy": uniform}

save_json(os.path.join(args.out, "ingest.json"), result)
print("camera clips: %d, %.1f s in all" % (len(clips), offset))
for c in clips:
    print("  %8.3f s  %-16s %6.1f s  %dx%d @ %g" % (c["source_start"], c["file"], c["duration"], c["width"], c["height"], c["fps"]))
if aside:
    print("set aside (other size): " + ", ".join(c["file"] for c in aside))
if result["concat"]:
    print("joined -> %s (%s)" % (result["concat"]["file"], "no re-encode" if result["concat"]["stream_copy"] else "re-encoded to match"))
