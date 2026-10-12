#!/usr/bin/env python3
"""verify-render.py: checks on the RENDERED file before delivery, plus the sheets to read by eye.

Snapshots of the composition show what should render, not what did: a long render can, for example, come out
with stretches of black. This inspects the encoded MP4 itself and writes VERIFY.md beside it (or at --out):
  Resolution      width x height = --res (default 2160x3840)
  Colour tags     primaries / transfer / matrix all bt709
  Video bitrate   >= --min-mbps at 3840x2160 (40), scaled by pixel count
  Duration        within one frame of the composition's data-duration (--index, default public/index.html beside it)
  Video vs audio  stream lengths within 0.12 s
  Black frames    any black run at all (blackdetect, pix_th 0.08): a 0.1 s interval or a 2-frame flash both FAIL
  Clipped words   given --kept (the flat cut's transcript) and --words (a transcript of the render's own audio): any
                  flat-cut word absent from the render FAILS (it was probably cut off at a join); words that were
                  merely transcribed differently are listed for a listen, not failed.
And the sheets (one decode pass; Pillow tiles them, times written on every tile):
  render-sheet.png              first frame, every .card-host at data-start + 0.9 s, last frame (4 across, 480 px)
  render-dense-NN.png           a frame every --dense s (0.5; 0 = off), 6 x 5 per page, 240 px
  render-transitions-NN.png     around every card entrance and exit and every jump cut in --joins: the frames at
                                -0.10 / +0.05 / +0.20 / +0.40 / +0.70 s, one event per row, 8 rows per page
VERIFY.md says which page and row holds which event. Read them all: a card flashing for a frame, a caption under a
panel or a cut on the same framing only shows there.

Usage: python verify-render.py --render W/renders/reel-v1.mp4 [--index W/public/index.html] [--res 1080x1920]
                               [--joins W/joins.json] [--words W/delivered.json --kept W/transcript.json] [--dense 0.5]
Exit 1 on any FAIL.
"""
import argparse
import difflib
import json
import os
import re
import subprocess
import sys
import time
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cutlib import fail, load_words, probe, rate_of, stream, tokens  # noqa: E402

cli = argparse.ArgumentParser(description="Check a rendered MP4 and make its review sheets.")
cli.add_argument("--render", required=True, help="the rendered MP4")
cli.add_argument("--res", default="2160x3840", help="expected WIDTHxHEIGHT")
cli.add_argument("--index", help="the composition (default: public/index.html beside the render)")
cli.add_argument("--joins", help="joins.json from find-joins.py: each jump cut gets a transition row")
cli.add_argument("--dense", type=float, default=0.5, help="seconds between dense-sheet frames (0 = no dense sheets)")
cli.add_argument("--no-transitions", action="store_true", help="skip the transition sheets")
cli.add_argument("--kept", help="transcript of the flat cut, for the clipped-word check")
cli.add_argument("--words", help="transcript of the RENDER's own audio, for the clipped-word check")
cli.add_argument("--min-mbps", type=float, default=40.0, help="bitrate floor at 3840x2160, scaled to the real size")
cli.add_argument("--out", help="where VERIFY.md goes (default: beside the render)")
args = cli.parse_args()

R = os.path.abspath(args.render)
if not os.path.isfile(R):
    fail("render not found: %s" % R)
render_dir = os.path.dirname(R)
report = os.path.abspath(args.out) if args.out else os.path.join(render_dir, "VERIFY.md")
out_dir = os.path.dirname(report)
if not os.path.isdir(out_dir):
    os.makedirs(out_dir)
index = args.index if args.index else os.path.join(render_dir, "public", "index.html")

results, sections = [], []


def record(name, ok, measured, expected):
    results.append((name, ok, measured, expected))


def num(value):
    """float(value), or None for missing / non-numeric probe fields."""
    if value in (None, "", "N/A"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


# ---------------------------------------------------------------- the composition
class Comp(HTMLParser):
    def __init__(self):
        super().__init__()
        self.duration, self.cards = None, []

    def handle_starttag(self, tag, attrs):
        if tag != "div":
            return
        a = dict(attrs)
        if self.duration is None and "data-composition-id" in a:
            self.duration = num(a.get("data-duration"))
        if "card-host" in (a.get("class") or "").split() and num(a.get("data-start")) is not None:
            self.cards.append((a.get("id") or "?", num(a.get("data-start")), num(a.get("data-duration"))))

    handle_startendtag = handle_starttag


comp = Comp()
if os.path.exists(index):
    with open(index, encoding="utf-8") as fh:
        comp.feed(fh.read())

# ---------------------------------------------------------------- probe
info = probe(R, "format=size,duration,bit_rate:stream=codec_type,duration,bit_rate,r_frame_rate,width,height,"
                "color_space,color_transfer,color_primaries")
v, a = stream(info, "video"), stream(info, "audio")
if v is None:
    fail("no video stream in %s" % R)
fps = rate_of(v)
W, H = int(v.get("width") or 0), int(v.get("height") or 0)
want_w, want_h = [int(x) for x in args.res.lower().split("x")]
record("Resolution", (W, H) == (want_w, want_h), "%dx%d" % (W, H), args.res)

tags = [str(v.get(field) or "unset") for field in ("color_primaries", "color_transfer", "color_space")]
record("Colour tags", tags == ["bt709"] * 3, "/".join(tags) + " (primaries/transfer/matrix)", "bt709 on all three")

container = info.get("format", {})
vdur = next((x for x in (num(v.get("duration")), num(container.get("duration"))) if x), 0.0)
adur = num(a.get("duration")) if a else None


def video_bitrate():
    """The stream's own bit_rate; some muxers omit it, then the file's average minus the audio's."""
    own = num(v.get("bit_rate"))
    if own is not None:
        return own
    size = num(container.get("size"))
    if not (size and vdur):
        return None
    return size * 8 / vdur - (num((a or {}).get("bit_rate")) or 0)


vbr = video_bitrate()
need_bps = args.min_mbps * 1e6 * (W * H) / (3840.0 * 2160.0)
record("Video bitrate", bool(vbr) and vbr >= need_bps, ("%.1f Mb/s" % (vbr / 1e6)) if vbr else "unknown",
       "at least %.1f Mb/s" % (need_bps / 1e6))
frame = 1.0 / fps
if comp.duration is None:
    record("Duration", None, "%.3f s" % vdur, "skipped: no composition found (%s)" % index)
else:
    record("Duration", abs(vdur - comp.duration) <= frame + 1e-6, "%.3f s" % vdur,
           "data-duration %.3f s, one frame either way" % comp.duration)
if adur is None:
    record("Video vs audio", False, "no audio stream", "picture and sound within 0.12 s")
else:
    record("Video vs audio", abs(vdur - adur) <= 0.12, "picture %.3f s, sound %.3f s" % (vdur, adur), "within 0.12 s")

# ---------------------------------------------------------------- black frames
# blackdetect on a small decode; d=0 reports every black run, however short (a 2-frame flash included)
bd = subprocess.run(["ffmpeg", "-nostdin", "-nostats", "-hide_banner", "-an", "-i", R, "-map", "0:v:0", "-f", "null",
                     "-vf", "scale=320:-2,blackdetect=d=0:pix_th=0.08", "-"], capture_output=True, text=True)
blacks = []
for line in bd.stderr.splitlines():
    if "black_start:" in line:
        fields = dict(part.split(":", 1) for part in line.split("]", 1)[-1].split() if ":" in part)
        blacks.append((float(fields["black_start"]), float(fields["black_end"]), float(fields["black_duration"])))
flashes = [b for b in blacks if b[2] < 0.1 - 1e-6]
if bd.returncode:
    record("Black frames", False, "blackdetect could not run", "no black frames")
else:
    record("Black frames", not blacks, "%d run(s) of 0.1 s or more, %d shorter flash(es)" % (len(blacks) - len(flashes), len(flashes)),
           "no black frames")
if blacks:
    lines = ["## Black frames", ""]
    for s, e, d in blacks:
        n = max(1, round(d * fps))
        lines.append("- %.3f - %.3f s (%.3f s, %d frame%s): %s" % (s, e, d, n, "" if n == 1 else "s",
                                                                  "black interval" if d >= 0.1 - 1e-6 else "flash"))
    lines += ["", "Step through these moments in the MP4. Black stretches in a long 4K render usually come from parallel"
              " render workers: render again with --workers 1."]
    sections.append(lines)

# ---------------------------------------------------------------- which frames the sheets need
last_k = max(0, int(vdur * fps) - 1)


def at(t):
    return min(max(0, int(round(t * fps))), last_k)


beats = [(0.0, "first")] + [(min(st + 0.9, vdur - 1.5 * frame), cid) for cid, st, _ in sorted(comp.cards, key=lambda c: c[1])]
beats.append((max(0.0, vdur - 1.5 * frame), "last"))
seen, beat_frames = set(), []
for t, label in beats:
    if at(t) not in seen:
        seen.add(at(t))
        beat_frames.append((at(t), t, label))
dense = list(range(0, last_k + 1, max(1, int(round(args.dense * fps))))) if args.dense > 0 else []
events = []
if not args.no_transitions:
    for cid, st, du in comp.cards:
        events.append((st, "in " + cid))
        if du:
            events.append((st + du - 0.3, "out " + cid))
    if args.joins and os.path.exists(args.joins):
        with open(args.joins, encoding="utf-8") as fh:
            events += [(float(t), "cut") for t in json.load(fh).get("joins", [])]
OFFSETS = (-0.10, 0.05, 0.20, 0.40, 0.70)
events = sorted((t, lab) for t, lab in events if 0 <= t < vdur)
rows = [(t, lab, [at(t + o) for o in OFFSETS]) for t, lab in events]
need = {k for k, _, _ in beat_frames} | set(dense) | {k for _, _, ks in rows for k in ks}

# ---------------------------------------------------------------- one decode, Pillow tiles
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

TW = 480
TH = int(round(TW * H / W / 2.0)) * 2 if W else 854
size = TW * TH * 3
frames = {}
dec = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-threads", "4", "-i", R, "-map", "0:v:0",
                        "-vf", "scale=%d:%d" % (TW, TH), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
big = {k for k, _, _ in beat_frames}   # only the beat sheet needs 480 px; the rest is kept at 240 px (memory)
k = 0
while True:
    buf = dec.stdout.read(size)
    if len(buf) < size:
        break
    if k in need:
        img = Image.frombytes("RGB", (TW, TH), buf)
        frames[k] = img if k in big else img.resize((TW // 2, TH // 2))
    k += 1
dec.wait()


def font(px):
    try:
        return ImageFont.load_default(size=px)
    except TypeError:          # Pillow < 10.1: a fixed bitmap font
        return ImageFont.load_default()


def tile(k, width, label):
    img = frames.get(k)
    img = img.copy() if img is not None else Image.new("RGB", (TW, TH))
    if img.size[0] != width:
        img = img.resize((width, int(round(TH * width / TW))))
    d = ImageDraw.Draw(img)
    f = font(max(12, width // 20))
    box = d.textbbox((8, 8), label, font=f)
    d.rectangle((box[0] - 4, box[1] - 3, box[2] + 4, box[3] + 3), fill=(0, 0, 0))
    d.text((8, 8), label, fill=(255, 255, 255), font=f)
    return img


def grid(tiles, cols, path):
    w, h = tiles[0].size
    page = Image.new("RGB", (w * cols, h * ((len(tiles) + cols - 1) // cols)))
    for i, t in enumerate(tiles):
        page.paste(t, ((i % cols) * w, (i // cols) * h))
    page.save(path)


for old in os.listdir(out_dir):
    if re.fullmatch(r"render-(dense|transitions)-\d+\.png", old):
        os.remove(os.path.join(out_dir, old))
sheet = os.path.join(out_dir, "render-sheet.png")
grid([tile(k, TW, "%.2fs %s" % (t, lab)) for k, t, lab in beat_frames], 4, sheet)
sections.append(["## Frame sheet", "", "`render-sheet.png`: %d frames - the first, every card at data-start + 0.9 s, the last."
                 % len(beat_frames)])

dense_pages, trans_pages = [], []
for p in range(0, len(dense), 30):
    name = "render-dense-%02d.png" % (p // 30 + 1)
    grid([tile(k, 240, "%.2fs" % (k / fps)) for k in dense[p:p + 30]], 6, os.path.join(out_dir, name))
    dense_pages.append(name)
for p in range(0, len(rows), 8):
    name = "render-transitions-%02d.png" % (p // 8 + 1)
    grid([tile(k, 240, "%.2fs" % (k / fps)) for _, _, ks in rows[p:p + 8] for k in ks], 5, os.path.join(out_dir, name))
    trans_pages.append(name)
if dense_pages or trans_pages:
    lines = ["## Dense sheets and transitions", ""]
    if dense_pages:
        lines.append("Dense, a frame every %.2f s (6 x 5 per page): %s. Read every page." % (args.dense, ", ".join("`%s`" % n for n in dense_pages)))
    if trans_pages:
        lines += ["", "Transitions at %s s around each event, one event per row, 8 rows per page (%s):"
                  % (" / ".join("%+.2f" % o for o in OFFSETS), ", ".join("`%s`" % n for n in trans_pages)), ""]
        lines += ["- page %d row %d: %.2f s %s" % (i // 8 + 1, i % 8 + 1, t, lab) for i, (t, lab, _) in enumerate(rows)]
    sections.append(lines)

# ---------------------------------------------------------------- clipped words
if args.words and args.kept:
    FILLERS = {"um", "uh", "er", "ah", "hmm", "mm"}

    def toks(path):
        return [(tok, w["start"]) for w in load_words(path) for tok in tokens(w["text"]) if tok not in FILLERS]

    flat, heard = toks(args.kept), toks(args.words)
    missing, differ = [], []
    sm = difflib.SequenceMatcher(None, [t for t, _ in flat], [t for t, _ in heard], autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "delete":
            missing.append((flat[i1][1], " ".join(t for t, _ in flat[i1:i2]), " ".join(t for t, _ in flat[max(0, i1 - 3):i1])))
        elif op == "replace":
            differ.append((flat[i1][1], " ".join(t for t, _ in flat[i1:i2]), " ".join(t for t, _ in heard[j1:j2])))
    lost = sum(len(m[1].split()) for m in missing)
    record("Clipped words", lost == 0, "%d of %d flat-cut words absent" % (lost, len(flat)), "all present")
    lines = ["## Clipped words", ""]
    lines += ['- %.2f s: **%s** (after "%s") is in the flat cut but not in the render: check the join there' % m for m in missing] \
        or ["Every flat-cut word is in the render."]
    if differ:
        lines += ["", "Transcribed differently in the render (usually transcriber noise; listen if one sits on a join):", ""]
        lines += ['- %.2f s: flat "%s" / render "%s"' % d for d in differ[:40]]
    sections.append(lines)
elif args.words or args.kept:
    record("Clipped words", None, "needs both --words and --kept", "not checked")

# ---------------------------------------------------------------- report
STATE = {True: "PASS", False: "FAIL", None: "skip"}
failed = [r[0] for r in results if r[1] is False]
md = ["# VERIFY: %s" % os.path.basename(R), "",
      "**%s**  (%s)" % ("PASS" if not failed else "FAIL: " + ", ".join(failed), time.strftime("%Y-%m-%d %H:%M")), "",
      "| Check | Result | Measured | Expected |", "|---|---|---|---|"]
md += ["| %s | %s | %s | %s |" % (n, STATE[ok], m, e) for n, ok, m, e in results]
for sec in sections:
    md += [""] + sec
with open(report, "w", encoding="utf-8") as fh:
    fh.write("\n".join(md) + "\n")
for n, ok, m, e in results:
    print("%-15s %-5s %s  (expected %s)" % (n, STATE[ok], m, e))
for s, e, d in blacks:
    print("  black %.3f - %.3f s (%.3f s)" % (s, e, d))
print("%s -> %s, %s" % ("PASS" if not failed else "FAIL", report, sheet))
if dense_pages or trans_pages:
    print("read these too: " + ", ".join(dense_pages + trans_pages))
sys.exit(1 if failed else 0)
