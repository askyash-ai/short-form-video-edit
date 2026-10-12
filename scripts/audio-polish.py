#!/usr/bin/env python3
"""audio-polish.py: the voice, measured and cleaned, because Claude cannot hear it. Four commands:

  measure FILE...     integrated loudness (LUFS), true peak, loudness range, the noise floor (5th percentile of 50 ms
                      RMS windows: the room between words), the speech level (90th percentile), clipped samples.
  apply FILE...       per take, on the CONFORMED takes before any cut: high-pass 80 Hz (rumble, desk knocks), FFT
                      denoise solved per take (measured, up to 3 tries) so every take lands on the same floor (-66 dBFS), a gentle de-esser, a pre-level to
                      -20 LUFS, a 2.5:1 compressor, then a trim so every take ends at -20 LUFS +/- 0.3. Video is copied,
                      never re-encoded. Writes next to the input with --out-dir, or replaces it with --in-place. A
                      polished file carries a "audio-polish" comment tag and is skipped on a re-run (--force redoes it
                      from the file as it is now, which polishes twice: re-conform first).
  master IN OUT       the delivery step on the HyperFrames render: two-pass loudnorm to -14 LUFS, true peak aimed at -1.5 dBTP (lands <= -1 after AAC),
                      linear (no pumping), AAC 256k 48 kHz, BT.709 colour tags and faststart. Video is copied. Then the
                      master gate runs on OUT.
  check FILE...       the gate. Takes (default): each at -20 +/- 1 LUFS, noise floor <= -62 dBFS (WARN to -56), floors
                      within 4 dB of each other (the background must not jump at a join), no clipping. --master: -14 +/- 1
                      LUFS, true peak <= -1.0, floor <= -56 dBFS (WARN to -50, FAIL above: an audible room), no clipping.
                      Exit 1 on any FAIL.

Measured on reel-1's DJI Mic takes (4K60, 2026-10-07): -31 to -33 LUFS, floors -65 to -73 dBFS. Mastered straight to
-14 they would carry a -48 dBFS room, and a 9 dB jump in it at every join. Polished: every take -66 +/- 1.5 dBFS
at -20 LUFS (the room ~-60 dBFS in the master), speech level unchanged. Most of that room was below 150 Hz.

Usage:
  python audio-polish.py measure W/conformed/*.mp4 [--json]
  python audio-polish.py apply --in-place W/conformed/*.mp4      (or --out-dir W/polished)
  python audio-polish.py check W/conformed/*.mp4
  python audio-polish.py master W/renders/raw.mp4 W/renders/<slug>-v1.mp4
Options for apply: --target -20 --floor -66 (floor at -20 LUFS) --nr-min 3 --nr-max 24 --nf -50 --deess 0.25 (0 = off) --hpf 80
                   --comp-threshold -26 --comp-ratio 2.5 --eq "<extra ffmpeg audio filters>"
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile

import numpy as np

TAG = "audio-polish"
SR = 48000


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def measure(path):
    """Loudness, peaks and the noise floor of a file's first audio stream (None when it has no audio)."""
    r = run(["ffmpeg", "-nostdin", "-hide_banner", "-nostats", "-i", path, "-map", "0:a:0", "-af", "ebur128=peak=true",
             "-f", "null", "-"])
    if r.returncode:
        return None
    summary = r.stderr[r.stderr.rfind("Summary:"):]
    grab = lambda k: float(re.search(r"\b%s:\s+(-?[\d.]+|-inf)" % k, summary).group(1).replace("-inf", "-120"))
    # native channels, averaged here: ffmpeg's own -ac 1 downmix ADDS identical channels (+3 dB, and fake clipping)
    ch = int((run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=channels", "-of", "csv=p=0",
                   path]).stdout.strip() or "1").split(",")[0])
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", path, "-map", "0:a:0", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True).stdout
    xs = np.frombuffer(raw, np.float32)
    xs = xs[: len(xs) // ch * ch].reshape(-1, ch)
    clipped = int((np.abs(xs) >= 0.999).any(axis=1).sum())
    x = xs.mean(axis=1)
    w = SR // 20                                            # 50 ms windows
    n = max(1, len(x) // w)
    win = x[: n * w].reshape(n, w) if len(x) >= w else x.reshape(1, -1)
    db = 20 * np.log10(np.sqrt((win.astype(np.float64) ** 2).mean(1)) + 1e-9)
    return {
        "file": os.path.basename(path),
        "duration": round(len(x) / SR, 2),
        "lufs": grab("I"),
        "lra": grab("LRA"),
        "true_peak": grab("Peak"),
        "floor": round(float(np.percentile(db, 5)), 1),
        "speech": round(float(np.percentile(db, 90)), 1),
        "clipped": clipped,
        "polished": TAG in (run(["ffprobe", "-v", "error", "-show_entries", "format_tags=comment", "-of", "csv=p=0",
                                 path]).stdout or ""),
    }


def has_video(path):
    return "video" in run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", path]).stdout


def mux(src, audio_wav, out, extra_out=(), comment=None, movflags="+faststart"):
    """Video copied from src, audio from the wav, AAC 256k 48 kHz."""
    cmd = ["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", src, "-i", audio_wav, "-map", "0:v:0?", "-map", "1:a:0",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", str(SR), *extra_out]
    if comment:
        cmd += ["-metadata", "comment=" + comment]
    r = run(cmd + ["-movflags", movflags, out])          # one -movflags: a second one silently replaces the first
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[-400:])


def render_audio(src, af, wav):
    r = run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", src, "-map", "0:a:0", "-af", af, "-ar", str(SR),
             "-c:a", "pcm_f32le", wav])
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[-400:])


def cmd_measure(a):
    rows = [m for m in (measure(f) for f in a.files) if m]
    if a.json:
        print(json.dumps(rows, indent=1))
        return 0
    print("%-28s %6s %8s %6s %7s %7s %6s %s" % ("file", "dur", "LUFS", "LRA", "TP", "floor", "speech", "clip"))
    for m in rows:
        print("%-28s %6.1f %8.1f %6.1f %7.1f %7.1f %6.1f %d%s" % (m["file"][:28], m["duration"], m["lufs"], m["lra"],
              m["true_peak"], m["floor"], m["speech"], m["clipped"], "  (polished)" if m["polished"] else ""))
    return 0


def cmd_apply(a):
    if not a.in_place and not a.out_dir:
        sys.exit("apply needs --in-place or --out-dir")
    if a.out_dir:
        os.makedirs(a.out_dir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="audio-polish-")
    failed = 0
    try:
        for f in a.files:
            m = measure(f)
            if not m:
                print("SKIP   %s: no audio stream" % f); continue
            if m["polished"] and not a.force:
                print("SKIP   %s: already polished (--force to redo)" % m["file"]); continue
            gain = a.target - m["lufs"]
            w1, w2 = os.path.join(tmp, "a.wav"), os.path.join(tmp, "b.wav")

            def polish(nr):
                """The whole chain at one reduction; returns (floor at target, trim, filter note)."""
                chain = ["highpass=f=%d:poles=2" % a.hpf, "afftdn=nr=%d:nf=%d" % (nr, a.nf)]
                if a.deess > 0:
                    chain.append("deesser=i=%.2f:m=0.5:f=0.5:s=o" % a.deess)
                if a.eq:
                    chain.append(a.eq)
                chain += ["volume=%.2fdB" % gain,
                          "acompressor=threshold=%.1fdB:ratio=%.2f:attack=10:release=150:knee=6:makeup=1" % (a.comp_threshold, a.comp_ratio)]
                render_audio(f, ",".join(chain), w1)
                trim = a.target - measure(w1)["lufs"]      # the compressor moved the level: land exactly on target
                render_audio(w1, "volume=%.2fdB" % trim, w2)
                return measure(w2)["floor"], trim

            try:
                # afftdn's nf is its own scale, not the measured dBFS floor: nf -50 with no tracking cut reel-1's floors
                # 12-20 dB while the speech level (90th pct) stayed within 0.6 dB. The reduction is solved per take, so
                # every take lands on --floor and the room does not jump at a join (about 1 dB of floor per dB of nr).
                nr = min(a.nr_max, max(a.nr_min, round(m["floor"] + gain - a.floor)))
                for _ in range(3):
                    fl, trim = polish(nr)
                    nxt = min(a.nr_max, max(a.nr_min, round(nr + fl - a.floor)))
                    if abs(fl - a.floor) <= 1.5 or nxt == nr:
                        break
                    nr = nxt
                out = os.path.join(tmp, "out" + os.path.splitext(f)[1]) if a.in_place else \
                    os.path.join(a.out_dir, os.path.basename(f))
                note = "%s v1: hpf %d, afftdn nr %d nf %d, deess %.2f, gain %+.1f, comp %.1f/%.1f, trim %+.1f" % (
                    TAG, a.hpf, nr, a.nf, a.deess, gain, a.comp_threshold, a.comp_ratio, trim)
                mux(f, w2, out, comment=note)
                if a.in_place:
                    os.replace(out, f)
                    out = f
                done = measure(out)
                print("OK     %-24s %6.1f -> %6.1f LUFS, floor %6.1f -> %6.1f dBFS (nr %d), clip %d" % (
                    m["file"][:24], m["lufs"], done["lufs"], m["floor"], done["floor"], nr, done["clipped"]))
            except RuntimeError as e:
                print("FAILED %s: %s" % (f, e)); failed += 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 1 if failed else 0


def loudnorm_pass1(src, I, TP, LRA):
    r = run(["ffmpeg", "-nostdin", "-hide_banner", "-nostats", "-i", src, "-map", "0:a:0",
             "-af", "loudnorm=I=%s:TP=%s:LRA=%s:print_format=json" % (I, TP, LRA), "-f", "null", "-"])
    js = r.stderr[r.stderr.rfind("{"): r.stderr.rfind("}") + 1]
    return json.loads(js)


def cmd_master(a):
    tmp = tempfile.mkdtemp(prefix="audio-master-")
    try:
        p = loudnorm_pass1(a.src, a.lufs, a.tp, a.lra)
        af = ("loudnorm=I={I}:TP={TP}:LRA={LRA}:measured_I={input_i}:measured_TP={input_tp}:measured_LRA={input_lra}:"
              "measured_thresh={input_thresh}:offset={target_offset}:linear=true:print_format=json").format(
            I=a.lufs, TP=a.tp, LRA=a.lra, **p)
        wav = os.path.join(tmp, "m.wav")
        render_audio(a.src, af, wav)
        tags = ["-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv",
                ] if has_video(a.src) else []
        mux(a.src, wav, a.out, extra_out=tags, movflags="+write_colr+faststart" if tags else "+faststart")
        print("master: %s LUFS / %s dBTP in -> %s" % (p["input_i"], p["input_tp"], a.out))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    a.files, a.master = [a.out], True
    return cmd_check(a)


def cmd_check(a):
    fails = warns = 0
    rows = [m for m in (measure(f) for f in a.files) if m]
    def say(lvl, what, msg):
        nonlocal fails, warns
        print("%-4s %-24s %s" % (lvl, what[:24], msg))
        fails += lvl == "FAIL"; warns += lvl == "WARN"
    for m in rows:
        if a.master:
            say("ok" if abs(m["lufs"] + 14) <= 1 else "FAIL", m["file"], "loudness %.1f LUFS (want -14 +/- 1)" % m["lufs"])
            say("ok" if m["true_peak"] <= -1.0 else "WARN" if m["true_peak"] <= -0.5 else "FAIL", m["file"],
                "true peak %.1f dBTP (want <= -1.0)" % m["true_peak"])
            say("ok" if m["floor"] <= -56 else "WARN" if m["floor"] <= -50 else "FAIL", m["file"],
                "noise floor %.1f dBFS at -14 LUFS (want <= -56; above -50 the room is audible)" % m["floor"])
        else:
            say("ok" if abs(m["lufs"] - a.target) <= 1 else "FAIL", m["file"],
                "loudness %.1f LUFS (want %d +/- 1: run apply)" % (m["lufs"], a.target))
            say("ok" if m["floor"] <= -62 else "WARN" if m["floor"] <= -56 else "FAIL", m["file"],
                "noise floor %.1f dBFS (want <= -62 at %d LUFS: run apply)" % (m["floor"], a.target))
        say("ok" if m["clipped"] == 0 else "FAIL", m["file"], "%d clipped samples%s" % (
            m["clipped"], "" if not m["clipped"] else ": the recording clipped; nothing after this fixes it, use another take"))
    if not a.master and len(rows) > 1:
        floors = [m["floor"] for m in rows]
        spread = max(floors) - min(floors)
        say("ok" if spread <= 4 else "WARN", "floor spread", "%.1f dB across %d takes (want <= 4: the room must not jump at a join)"
            % (spread, len(rows)))
        lv = [m["lufs"] for m in rows]
        say("ok" if max(lv) - min(lv) <= 1 else "FAIL", "level spread", "%.1f LU across %d takes (want <= 1)" % (max(lv) - min(lv), len(rows)))
    print("\n%s%s" % ("%d FAIL" % fails if fails else "PASS", ", %d WARN" % warns if warns else ""))
    return 1 if fails else 0


ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
sub = ap.add_subparsers(dest="cmd", required=True)
m = sub.add_parser("measure"); m.add_argument("files", nargs="+"); m.add_argument("--json", action="store_true")
p = sub.add_parser("apply"); p.add_argument("files", nargs="+")
p.add_argument("--in-place", action="store_true"); p.add_argument("--out-dir"); p.add_argument("--force", action="store_true")
p.add_argument("--target", type=float, default=-20.0, help="LUFS every take lands on (the master lifts it to -14)")
p.add_argument("--floor", type=float, default=-66.0, help="the noise floor every take should land on, at --target (-60 at the -14 master)")
p.add_argument("--nr-min", type=int, default=3); p.add_argument("--nr-max", type=int, default=24)
p.add_argument("--nf", type=int, default=-50, help="afftdn noise-floor setting (its own scale; -50 measured best on DJI Mic takes)")
p.add_argument("--deess", type=float, default=0.25, help="deesser intensity 0-1 (0 = off)")
p.add_argument("--hpf", type=int, default=80)
p.add_argument("--comp-threshold", type=float, default=-26.0); p.add_argument("--comp-ratio", type=float, default=2.5)
p.add_argument("--eq", help="extra ffmpeg audio filters, inserted before the gain (e.g. a mud cut: equalizer=f=250:t=q:w=1:g=-2)")
s = sub.add_parser("master"); s.add_argument("src"); s.add_argument("out")
s.add_argument("--lufs", type=float, default=-14.0); s.add_argument("--tp", type=float, default=-1.5, help="loudnorm aim; the AAC encode adds ~0.5 dB of inter-sample peak, the gate wants <= -1.0"); s.add_argument("--lra", type=float, default=11.0)
s.add_argument("--target", type=float, default=-20.0)
c = sub.add_parser("check"); c.add_argument("files", nargs="+"); c.add_argument("--master", action="store_true")
c.add_argument("--target", type=float, default=-20.0)
a = ap.parse_args()
sys.exit({"measure": cmd_measure, "apply": cmd_apply, "master": cmd_master, "check": cmd_check}[a.cmd](a))
