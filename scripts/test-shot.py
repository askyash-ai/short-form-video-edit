#!/usr/bin/env python3
"""test-shot.py: a 5-10 s test clip, checked BEFORE the real shoot, so a bad room, a hot mic or a framing that leaves no
room for the cards is caught while it is still free to fix. Say one script line, then stay silent for 2 s.

  format    portrait; 4K60 (2160x3840 @ 60, the default) or HD30 (1080x1920 @ 30) both pass, anything else WARNs;
            HDR (HLG) WARNs: record with HDR Video off (its conversion came out too bright and warm on reel-1)
  audio     clipping FAIL (nothing after the shoot fixes it); true peak over -3 dBTP WARN (no headroom);
            speech under -36 LUFS WARN (mic too far / gain too low); room floor over -55 dBFS FAIL, over -62 WARN
            (fans, AC, fridge, traffic: the master lifts it ~17 dB); speech-to-room under 30 dB WARN
  picture   on a tonemapped frame: clipped highlights (Y > 250) over 4% of the frame WARN (a window or lamp blowing out),
            crushed shadows (Y < 6) over 4% WARN, a colour cast on the brightest tenth of the frame (a white wall should be
            neutral) WARN; with --patch x,y,w,h (forehead, in 1080x1920 px) the skin level, WARN outside 55-80%
  framing   framing.png: the frame with every zone drawn on it. READ IT: the top of the head should sit around y 540-620
            (the M cards live above it, from y 250), the eyes near y 900, the chin above the caption band (y 1320), and
            nothing you care about in the red zones (the Reels header, the bottom UI, the button column). The grey lines
            are the 4:5 feed crop (y 285 / 1635) and the 3:4 profile-grid crop (y 240 / 1680).

Writes framing.png and TEST-SHOT.md into --out (default: next to the clip). Exit 1 on any FAIL.
Usage: python test-shot.py --in W/raw/test.MOV [--out W/testshot] [--patch 330,790,240,60] [--at 2.5]
"""
import argparse, importlib.util, json, os, subprocess, sys

import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--in", dest="src", required=True)
ap.add_argument("--out")
ap.add_argument("--patch", help="forehead patch x,y,w,h in 1080x1920 px (from the gridded frame), for the skin level")
ap.add_argument("--at", type=float, default=None, help="frame time (default: 40%% into the clip)")
a = ap.parse_args()
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("audio_polish_measure", os.path.join(here, "audio-polish.py"))
OUT = a.out or os.path.join(os.path.dirname(os.path.abspath(a.src)), "testshot")
os.makedirs(OUT, exist_ok=True)

lines, fails, warns = [], 0, 0
def say(lvl, area, msg):
    global fails, warns
    lines.append((lvl, area, msg)); fails += lvl == "FAIL"; warns += lvl == "WARN"

# ---- format --------------------------------------------------------------------------------------------------
p = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
    "stream=codec_type,width,height,r_frame_rate,color_transfer:stream_side_data=rotation:format=duration", "-of", "json", a.src],
    capture_output=True, text=True, check=True).stdout)
v = next(s for s in p["streams"] if s.get("codec_type") == "video")
has_audio = any(s.get("codec_type") == "audio" for s in p["streams"])
rot = abs(int(float(next((d["rotation"] for d in v.get("side_data_list", []) if "rotation" in d), 0)))) % 180
w, h = (v["height"], v["width"]) if rot == 90 else (v["width"], v["height"])
n, d = [int(x) for x in v["r_frame_rate"].split("/")]
fps = round(n / d) if d else 0
dur = float(p["format"].get("duration", 0))
hdr = v.get("color_transfer") in ("arib-std-b67", "smpte2084")
prof = "4K60" if (min(w, h), fps) == (2160, 60) else "HD30" if (min(w, h), fps) == (1080, 30) else None
if w > h:
    say("FAIL", "format", "%dx%d is landscape: hold the phone upright" % (w, h))
else:
    if hdr:
        say("WARN", "format", "HDR (HLG) video: turn HDR Video OFF (Settings > Camera > Record Video) so the takes look as the phone shows them")
    say("ok" if prof else "WARN", "format", "%dx%d @ %d fps%s%s" % (w, h, fps, ", HDR" if hdr else ", SDR (HDR off: good)",
        " = %s" % prof if prof else ": the skill expects 4K60 (default) or HD30; set the camera to one of them"))
    if prof == "HD30":
        say("ok", "format", "HD30: punch-ins and the jump-cut reframing are capped at 1.08-1.12 (no 4K headroom)")
if dur < 4:
    say("WARN", "format", "only %.1f s: record one line and 2 s of silence" % dur)

# ---- audio ---------------------------------------------------------------------------------------------------
if not has_audio:
    say("FAIL", "audio", "no audio track: is the DJI Mic receiver plugged in and selected?")
else:
    ap_mod = importlib.util.module_from_spec(spec)
    src = open(spec.origin, encoding="utf-8").read()
    src = src[: src.index("ap = argparse.ArgumentParser(")]          # the measuring half only, not its CLI
    exec(compile(src, spec.origin, "exec"), ap_mod.__dict__)
    m = ap_mod.measure(a.src)
    snr = m["speech"] - m["floor"]
    say("FAIL" if m["clipped"] else "ok", "audio", "%d clipped samples%s" % (m["clipped"], ": lower the mic gain (DJI Mic: gain -6 or 'safety track' on)" if m["clipped"] else ""))
    say("WARN" if m["true_peak"] > -3 else "ok", "audio", "true peak %.1f dBTP%s" % (m["true_peak"], ": too hot, a laugh or a stressed word will clip" if m["true_peak"] > -3 else ""))
    say("WARN" if m["lufs"] < -36 else "ok", "audio", "speech %.1f LUFS%s" % (m["lufs"], ": quiet; clip the mic 15-20 cm under the chin" if m["lufs"] < -36 else ""))
    fl = m["floor"]
    say("FAIL" if fl > -55 else "WARN" if fl > -62 else "ok", "audio",
        "room %.1f dBFS%s" % (fl, ": noisy; fans / AC / fridge off, windows shut, soft things in the room" if fl > -62 else " (quiet room)"))
    say("WARN" if snr < 30 else "ok", "audio", "speech %.0f dB over the room%s" % (snr, ": move the mic closer or quieten the room" if snr < 30 else ""))

# ---- picture -------------------------------------------------------------------------------------------------
t = a.at if a.at is not None else max(0.0, dur * 0.4)
tone = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=mobius:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,"
        if hdr else "")
fill = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", "%.2f" % t, "-i", a.src, "-frames:v", "1", "-vf",
                      tone + fill + ",format=rgb24", "-f", "rawvideo", "-"], capture_output=True).stdout
if len(raw) != 1080 * 1920 * 3:
    say("FAIL", "picture", "could not read a frame at %.2f s" % t)
else:
    img = np.frombuffer(raw, np.uint8).reshape(1920, 1080, 3).astype(np.float32)
    Y = 0.2126 * img[..., 0] + 0.7152 * img[..., 1] + 0.0722 * img[..., 2]
    hi, lo = float((Y > 250).mean() * 100), float((Y < 6).mean() * 100)
    say("WARN" if hi > 4 else "ok", "picture", "%.1f%% clipped highlights%s" % (hi, ": a window or lamp is blowing out; turn the phone or lock exposure on your face (long-press AE/AF lock)" if hi > 4 else ""))
    say("WARN" if lo > 4 else "ok", "picture", "%.1f%% crushed shadows%s" % (lo, ": add light from the front" if lo > 4 else ""))
    top = img[Y >= np.percentile(Y, 90)]
    r_, g_, b_ = top.mean(0)
    cast = (r_ - b_) / max(1.0, top.mean()) * 100
    say("WARN" if abs(cast) > 8 else "ok", "picture", "brightest tenth R-B %+.0f%% (%s)%s" % (cast, "warm" if cast > 0 else "cool",
        ": mixed light? one colour of light only (daylight OR the lamp), every take" if abs(cast) > 8 else ""))
    if a.patch:
        x, y, pw, ph = [int(s) for s in a.patch.split(",")]
        sk = float(Y[y:y + ph, x:x + pw].mean() / 255 * 100)
        say("WARN" if not 55 <= sk <= 80 else "ok", "picture", "skin %.1f%%%s" % (sk, ": too dark, more light on the face" if sk < 55 else ": too bright, less light or lock exposure" if sk > 80 else ""))

    # framing sheet: the zones the edit needs, drawn on the frame
    boxes = [  # x, y, w, h, colour@alpha, fill(t=fill) or line thickness
        (0, 0, 1080, 250, "red@0.35", "fill"), (0, 1500, 1080, 420, "red@0.35", "fill"), (960, 1000, 120, 500, "red@0.35", "fill"),
        (60, 250, 960, 300, "0x2dd4bf@0.9", "6"), (60, 1320, 900, 180, "yellow@0.9", "6"),
        (0, 285, 1080, 1350, "white@0.6", "3"), (0, 240, 1080, 1440, "gray@0.8", "3"),
    ]
    vf = ",".join("drawbox=x=%d:y=%d:w=%d:h=%d:color=%s:t=%s" % b for b in boxes)
    vf += ",drawgrid=w=108:h=192:t=1:c=white@0.25"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-ss", "%.2f" % t, "-i", a.src, "-frames:v", "1", "-vf",
                    tone + fill + "," + vf, os.path.join(OUT, "framing.png")], check=True)
    say("ok", "framing", "framing.png written: read it (teal = where M cards go, above your head; yellow = captions; red = platform UI)")

md = ["# Test shot: %s" % os.path.basename(a.src), "", "**%s**" % ("PASS" if not fails else "%d FAIL" % fails) + (", %d WARN" % warns if warns else ""), "",
      "| | Area | Result |", "|---|---|---|"] + ["| %s | %s | %s |" % l for l in lines] + [
      "", "Framing: `framing.png`. Head top ~y 540-620 (under the teal M zone), eyes ~y 900, chin above the yellow caption band,",
      "the same framing and light for every take. Fix anything above, record a new test clip, then shoot."]
open(os.path.join(OUT, "TEST-SHOT.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
for l in lines:
    print("%-4s %-8s %s" % l)
print("\n%s%s -> %s" % ("PASS" if not fails else "%d FAIL" % fails, ", %d WARN" % warns if warns else "", os.path.join(OUT, "TEST-SHOT.md")))
sys.exit(1 if fails else 0)
