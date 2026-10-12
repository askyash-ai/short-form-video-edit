#!/usr/bin/env python3
"""teardown.py: measure a short-form video you admire (or your own), so its pacing can be compared and copied.
Use it on files the user downloaded themselves; never scrape.

From the picture (64x36 grey frames, one decode):
  hard cuts      a 1-2 frame spike in frame-to-frame change against the local median (+-0.5 s), at least --cut-ratio
                 times it and twice the frames around it. Same-framing jump cuts barely move a fixed threshold, so the
                 bar is relative; a 0.3/255 floor keeps encoder flicker out. A graphic snapping in counts too.
  bursts         3-15 frame runs over the same bar: animated entrances, fast switches, big gestures
  first change   seconds to the first cut or burst (the hook's first visual beat)
  holds          the longest stretches with no cut or burst (anything over --hold s is listed)
From the sound: RMS per 0.25 s (median, p10, p90) and loudness jumps (sound-cue candidates).
With --transcript: words per minute, the first spoken word, and one line every 5 s in the worksheet.

Writes into --out: sheet_NN.png (4x4 tiles, one every --every s), report.json and TEARDOWN.md (the numbers, a
"count by eye" block for what only the sheets show, and a worksheet). --compare puts several report.json side by side.

Usage:
  python teardown.py --video ref.mp4 --out W/_teardown/ref [--every 1] [--transcript ref.json]
  python teardown.py --compare a/report.json b/report.json --out COMPARE.md
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cutlib import Audio, ends_sentence, fail, load_words, probe, rate_of, stream  # noqa: E402

cli = argparse.ArgumentParser(description="Measure the pacing of a short-form video.")
what = cli.add_mutually_exclusive_group(required=True)
what.add_argument("--video", help="the file to measure")
what.add_argument("--compare", nargs="+", metavar="REPORT", help="report.json files to put side by side")
cli.add_argument("--out", help="folder for the sheets and reports (with --compare: a .md path or a folder)")
cli.add_argument("--name", help="label in reports (default: the file name)")
cli.add_argument("--transcript", help="word-level transcript of the video, for words per minute and the worksheet")
cli.add_argument("--hold", type=float, default=3.0, help="report stretches without a visual change longer than this (s)")
cli.add_argument("--every", type=float, default=1.0, help="seconds between contact-sheet tiles")
cli.add_argument("--cut-ratio", type=float, default=4.0, help="how far above the local median a frame change must jump")
args = cli.parse_args()


def mmss(t):
    return "%d:%04.1f" % (int(t) // 60, t % 60)


def save_text(path, text):
    folder = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(folder):
        os.makedirs(folder)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


# ---------------------------------------------------------------- compare
def cell(value, pattern, empty=""):
    return empty if value is None else pattern % value


def longest_hold(r):
    return "none" if not r.get("holds") else "%.1f s at %s" % (r["holds"][0]["length"], mmss(r["holds"][0]["from"]))


METRICS = [("Duration", lambda r: cell(r["duration"], "%.1f s")),
           ("First visual change", lambda r: cell(r.get("first_change"), "%.2f s", "none")),
           ("Visual changes / 10 s", lambda r: cell(r["changes_per_10s"], "%.1f")),
           ("Hard cuts / min", lambda r: cell(r["cuts_per_min"], "%.1f")),
           ("Mean shot", lambda r: cell(r["mean_shot_s"], "%.1f s")),
           ("Longest hold", longest_hold),
           ("First word", lambda r: cell(r.get("first_word"), "%.2f s")),
           ("Words / min", lambda r: cell(r.get("words_per_min"), "%.0f")),
           ("Audio level (median)", lambda r: cell((r.get("audio") or {}).get("median_db"), "%.0f dB"))]

if args.compare:
    reports = []
    for p in args.compare:
        with open(p, encoding="utf-8") as fh:
            reports.append(json.load(fh))
    names = [rep.get("name") or os.path.splitext(os.path.basename(path))[0] for rep, path in zip(reports, args.compare)]
    md = ["# Teardown comparison", "", "| Metric | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    md += ["| %s | %s |" % (label, " | ".join(f(r) for r in reports)) for label, f in METRICS]
    text = "\n".join(md) + "\n"
    print(text)
    if args.out:
        path = args.out if args.out.lower().endswith(".md") else os.path.join(args.out, "COMPARE.md")
        save_text(path, text)
        print("-> %s" % path)
    sys.exit(0)

# ---------------------------------------------------------------- video
if not args.out:
    fail("--out is required with --video")
import numpy as np  # noqa: E402

src = args.video
info = probe(src, "stream=codec_type,width,height,r_frame_rate:format=duration")
vs = stream(info, "video")
if vs is None:
    fail("no video stream in %s" % src)
fps = rate_of(vs)
dur = float(info["format"]["duration"])
os.makedirs(args.out, exist_ok=True)
for stale in sorted(glob.glob(os.path.join(args.out, "sheet_*.png"))):
    os.remove(stale)

# frame-to-frame change on tiny grey frames
GW, GH = 64, 36
raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", src, "-map", "0:v:0", "-vf",
                      "scale=%d:%d:flags=area,format=gray" % (GW, GH), "-f", "rawvideo", "-"], capture_output=True).stdout
grey = np.frombuffer(raw, np.uint8)[: len(raw) // (GW * GH) * GW * GH].reshape(-1, GH, GW).astype(np.int16)
change = np.abs(np.diff(grey, axis=0)).mean(axis=(1, 2)) if len(grey) > 1 else np.zeros(0)
times = (np.arange(len(change)) + 1) / fps          # change[i] = the step INTO frame i+1

half = max(3, int(round(0.5 * fps)))
local = np.array([np.median(np.concatenate([change[max(0, i - half):i], change[i + 1:i + 1 + half]]) if len(change) > 1 else [0.0])
                  for i in range(len(change))])
hot = (change >= 0.3) & (change >= args.cut_ratio * (local + 0.05))

cuts, detail, bursts = [], [], []
i = 0
while i < len(hot):
    if not hot[i]:
        i += 1
        continue
    j = i
    while j + 1 < len(hot) and hot[j + 1]:
        j += 1
    if 0 < i and j < len(hot) - 1:                                 # a spike at the very ends has no "after"
        around = max(change[i - 1], change[j + 1]) + 0.05
        if j - i <= 1 and change[i:j + 1].min() >= 2 * around:
            k = i + int(np.argmax(change[i:j + 1]))
            cuts.append(round(float(times[k]), 3))
            detail.append({"t": round(float(times[k]), 3), "diff": round(float(change[k]), 2),
                           "x_median": round(float(change[k] / (local[k] + 0.05)), 1)})
        elif 2 <= j - i <= 14:
            bursts.append((round(float(times[i]), 3), round(float(times[j]), 3)))
    i = j + 1

events = sorted(cuts + [b[0] for b in bursts])
first_change = events[0] if events else None
marks = [0.0] + events + [dur]
holds = sorted(({"from": round(a, 2), "to": round(b, 2), "length": round(b - a, 2)} for a, b in zip(marks, marks[1:])
                if b - a > args.hold), key=lambda h: -h["length"])

# contact sheets: vertical videos get portrait tiles
portrait = int(vs.get("height") or 0) > int(vs.get("width") or 0)
tw, th = (270, 480) if portrait else (480, 270)
tiles = "fps=%.6f,scale=%d:%d:force_original_aspect_ratio=decrease,pad=%d:%d:-1:-1,tile=4x4" % (1.0 / args.every, tw, th, tw, th)
subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", src, "-map", "0:v:0", "-vf", tiles, "-fps_mode", "passthrough",
                os.path.join(args.out, "sheet_%02d.png")], check=True)
sheets = sorted(glob.glob(os.path.join(args.out, "sheet_*.png")))

# sound
audio_stats = None
if stream(probe(src, "stream=codec_type"), "audio"):
    snd = Audio(src)
    win = int(snd.sr * 0.25)
    n = len(snd.x) // win
    if n:
        rms = np.sqrt((snd.x[: n * win].reshape(n, win) ** 2).mean(axis=1))
        db = 20 * np.log10(np.maximum(rms, 1.0) / 32768.0)
        srt = np.sort(db)
        onsets = [round(i * 0.25, 2) for i in range(4, n) if db[i] - np.median(db[i - 4:i]) >= 12 and db[i] > -40]
        audio_stats = {"median_db": round(float(np.median(db)), 1), "p10_db": round(float(srt[n // 10]), 1),
                       "p90_db": round(float(srt[9 * n // 10]), 1), "onset_candidates": onsets}

# words
wpm, first_word, lines = None, None, []
if args.transcript:
    ws = load_words(args.transcript)
    if ws:
        wpm = round(len(ws) * 60.0 / dur, 1)
        first_word = round(ws[0]["start"], 2)
        for slot in np.arange(0, dur, 5.0):
            here = [w for w in ws if slot <= w["start"] < slot + 5]
            if here:
                text = []
                for w in here:
                    text.append(w["text"])
                    if ends_sentence(w["text"]) and len(text) > 3:
                        break
                lines.append((round(float(slot), 1), " ".join(text)))

stem = os.path.splitext(os.path.basename(src))[0]
report = {"name": args.name or stem, "source": src, "kind": "video", "size": "%sx%s" % (vs.get("width"), vs.get("height")),
          "fps": round(fps, 3), "duration": round(dur, 3), "cuts": cuts, "cut_detail": detail,
          "cuts_per_min": round(len(cuts) * 60.0 / dur, 2),
          "mean_shot_s": round(dur / (len(cuts) + 1), 2), "bursts": bursts,
          "changes_per_10s": round(len(events) * 10.0 / dur, 2), "first_change": first_change, "holds": holds,
          "median_change": round(float(np.median(change)), 3) if len(change) else 0.0,
          "audio": audio_stats, "words_per_min": wpm, "first_word": first_word, "spoken_every_5s": lines,
          "sheets": [os.path.basename(s) for s in sheets],
          "detector": {"cut_ratio": args.cut_ratio, "window_frames": half, "min_change": 0.3}}
with open(os.path.join(args.out, "report.json"), "w", encoding="utf-8") as fh:
    json.dump(report, fh, indent=1)

per_sheet = 16 * args.every
md = ["# Teardown: %s" % report["name"], "",
      "`%s`, measured %s. Everything under Measured is computed from the file; fill in the rest by looking at the sheets."
      % (src, time.strftime("%Y-%m-%d")), "",
      "## Measured", "", "| Metric | Value |", "|---|---|",
      "| Duration | %.1f s, %sx%s at %g fps |" % (dur, vs.get("width"), vs.get("height"), round(fps, 3)),
      "| First visual change | %s |" % ("%.2f s" % first_change if first_change is not None else "none found"),
      "| Visual changes | %d (%d cuts + %d bursts), %.1f per 10 s |" % (len(events), len(cuts), len(bursts), report["changes_per_10s"]),
      "| Mean shot | %.1f s |" % report["mean_shot_s"],
      "| Longest hold | %s |" % ("%.1f s from %s" % (holds[0]["length"], mmss(holds[0]["from"])) if holds else "none over %.1f s" % args.hold),
      "| First spoken word | %s |" % ("%.2f s" % first_word if first_word is not None else "needs --transcript"),
      "| Speaking rate | %s |" % ("%.0f words/min" % wpm if wpm is not None else "needs --transcript"),
      "| Audio | %s |" % ("median %.0f dB, p10 %.0f, p90 %.0f" % (audio_stats["median_db"], audio_stats["p10_db"], audio_stats["p90_db"])
                         if audio_stats else "no audio stream"), "",
      "Cuts at: %s" % (", ".join("%.2f s" % c for c in cuts) if cuts else "-"), "",
      "Bursts at: %s" % (", ".join("%.2f-%.2f s" % b for b in bursts) if bursts else "-"), "",
      "Sudden +12 dB jumps (sound effects or hits?): %s" % (", ".join("%.2f s" % x for x in audio_stats["onset_candidates"][:40])
                                                            if audio_stats and audio_stats["onset_candidates"] else "-"), ""]
if holds:
    md += ["## Holds over %.1f s (no cut or burst)" % args.hold, ""] + ["- %s - %s: %.1f s" % (mmss(h["from"]), mmss(h["to"]), h["length"]) for h in holds] + [""]
md += ["## Sheets", "", "Each sheet is 16 tiles, %g s apart, read in rows." % args.every, ""]
md += ["- `%s`  %s - %s" % (os.path.basename(s), mmss(k * per_sheet), mmss(min(dur, (k + 1) * per_sheet))) for k, s in enumerate(sheets)]
md += ["", "## Count by eye from the sheets", "",
       "- When the promise is on screen (s):", "- Face visible (% of the video):", "- Overlay sizes used (S / M / L):",
       "- Caption style (words per group, position, highlight):", "- Motion inside panels (typing, counters, highlights):",
       "- Where the CTA lands, and what it asks for:", "",
       "Waveform numbers are not listening: say whether the audio was actually heard.", "",
       "## Worksheet", "", "| Time | Said | On screen | Camera | Sound | Why keep watching |", "|---|---|---|---|---|---|"]
said = dict(lines)
md += ["| %s | %s |  |  |  |  |" % (mmss(s), said.get(round(float(s), 1), "").replace("|", "/")) for s in np.arange(0, dur, 5.0)]
save_text(os.path.join(args.out, "TEARDOWN.md"), "\n".join(md) + "\n")

print("%s  %.1f s  first change %s  changes %.1f/10 s  cuts %d (mean shot %.1f s)  bursts %d  longest hold %s%s"
      % (report["name"], dur, "%.2f s" % first_change if first_change is not None else "none", report["changes_per_10s"],
         len(cuts), report["mean_shot_s"], len(bursts), "%.1f s" % holds[0]["length"] if holds else "none",
         "  wpm %.0f" % wpm if wpm else ""))
if cuts:
    print("cuts at " + ", ".join("%.2f" % c for c in cuts))
print("wrote TEARDOWN.md, report.json and %d sheet(s) to %s" % (len(sheets), args.out))
