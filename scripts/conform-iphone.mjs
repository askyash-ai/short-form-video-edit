#!/usr/bin/env node
// conform-iphone.mjs: iPhone (or any camera) takes -> edit-ready SDR clips AT THE SOURCE'S RESOLUTION AND FRAME RATE,
// with the footage's own skin tone.
//
// RESOLUTION AND FPS MATCH THE SOURCE (default since 2026-10-07: "make it 4K60 and set that as default"). A 4K take
// (2160 px or more across in portrait) comes out 2160x3840; anything smaller comes out 1080x1920. The frame rate is the
// source's own, rounded to a standard rate (59.94 -> 60, 29.97 -> 30, 24/25 kept), capped at 60. The reel composition
// is laid out at 1080x1920 CSS px and rendered at 2x (--resolution portrait-4k) at the same fps, so nothing in the
// layout changes. --hd forces 1080x1920, --hi forces 2160x3840, --fps N forces a rate.
//
// iPhone 16 Pro records HEVC 10-bit HLG (color_transfer arib-std-b67, BT.2020), stored landscape with a rotation tag.
// Read as SDR it comes out washed out (grey, desaturated: the BT.2020 colours shown as BT.709). This tonemaps HLG/PQ to
// BT.709 (zscale + mobius, npl 100, desat 0: correct colour, no saturation boost), applies the rotation, fills the frame
// (crop, never letterbox), CFR at the chosen rate, and writes H.264 CRF 16, a keyframe every second, full BT.709 tags,
// AAC 48 kHz. (8-bit SDR on purpose: Instagram's own HDR handling is what turns reels grey.)
//
// SKIN MATCH (the default for HDR takes). The plain tonemap lands skin ~4 points brighter than the camera recorded it
// (reel-1: recorded forehead 70.5%, tonemap 74.5%: "I am appearing too light"). The creator's rule (2026-10-07): "the
// exact same skin tone as the actual footage, just a tad of light (very minor), all uniform". So per take this measures
// the skin patch after the tonemap and bends a one-point tone curve through it so the patch lands on --skin-target
// (default: that take's own recorded level + --lift 2). Pass the uniform target from skin-match.mjs (median recorded +
// lift) so every take in a reel lands on the same skin level. Blacks and whites stay where the tonemap put them. The
// curve is checked on a frame and corrected (up to 3 passes) until the patch is within 0.5 point, then encoded and
// measured again on the output. (Measured on a 1080x1920 view of the frame, so the patch is in 1080 px either way.)
//
// COLOUR KEPT (the default since 2026-10-11, the creator's pick "C + colour kept"). Lifting the tone curve also greys
// the skin: on a dim take lifted from 53.7% to 63%, skin saturation fell from 37.9% to 32.5%, the washed-out look the
// creator rejects. So after the curve, the skin patch's saturation (HSV, (max-min)/max, averaged) is measured and an
// eq=saturation factor solved (up to 3 passes, clamped 0.80-1.40) so it lands back on the saturation the plain tonemap
// gave the same patch: the recorded colour, lighter, never boosted past it. --no-keep-colour turns it off.
//
// PREVIEW (Stage 1, before the long encode): --preview out.png renders the first take's frame four ways: the plain
// tonemap, the target -3, the target, the target +3 (each with the colour kept), labelled, side by side. Read it with
// the creator and pick; nothing is encoded.
//
// Usage:
//   node skin-match.mjs --patch 330,790,240,60 TAKE.MOV ...          -> prints SKIN_TARGET=<pct>
//   node conform-iphone.mjs --out-dir W/conformed --skin-patch 330,790,240,60 --skin-target <pct> TAKE.MOV ...
//   node conform-iphone.mjs --preview W/skin-preview.png --skin-patch ... --skin-target <pct> TAKE.MOV   (no encode)
//   options: --lift 2 (when no --skin-target), --skin-at 2.5 (the frame to measure), --no-skin-match, --no-keep-colour,
//            --grade none|bright|deep (an extra look on top; default none), --hd | --hi, --fps N,
//            --npl 100, --crf 16, --allow-landscape
import { spawnSync } from "node:child_process";
import { mkdirSync, existsSync } from "node:fs";
import { basename, extname, join } from "node:path";

const argv = process.argv.slice(2);
const opt = { outDir: null, grade: "none", size: "source", npl: 100, fps: null, crf: 16, allowLandscape: false, inputs: [],
  patch: "330,790,240,60", target: null, lift: 2, at: 2.5, match: true, keepColour: true, preview: null };
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === "--out-dir") opt.outDir = argv[++i];
  else if (a === "--hi") opt.size = "4k";
  else if (a === "--hd") opt.size = "hd";
  else if (a === "--grade") opt.grade = argv[++i];
  else if (a === "--npl") opt.npl = Number(argv[++i]);
  else if (a === "--fps") opt.fps = Number(argv[++i]);
  else if (a === "--crf") opt.crf = Number(argv[++i]);
  else if (a === "--allow-landscape") opt.allowLandscape = true;
  else if (a === "--skin-patch") opt.patch = argv[++i];
  else if (a === "--skin-target") opt.target = Number(argv[++i]);
  else if (a === "--lift") opt.lift = Number(argv[++i]);
  else if (a === "--skin-at") opt.at = Number(argv[++i]);
  else if (a === "--no-skin-match") opt.match = false;
  else if (a === "--no-keep-colour") opt.keepColour = false;
  else if (a === "--preview") opt.preview = argv[++i];
  else if (a.startsWith("--")) { console.error("unknown option " + a); process.exit(2); }
  else opt.inputs.push(a);
}
if ((!opt.outDir && !opt.preview) || !opt.inputs.length) {
  console.error("usage: node conform-iphone.mjs --out-dir DIR [--skin-patch x,y,w,h] [--skin-target pct] [--hd|--hi] [--fps N] FILE ...");
  process.exit(2);
}
if (opt.outDir) mkdirSync(opt.outDir, { recursive: true });
const GRADES = { none: "", bright: "eq=contrast=1.06:saturation=1.10,", deep: "eq=contrast=1.04:gamma=0.95,"};
if (!(opt.grade in GRADES)) { console.error("--grade is none, bright or deep"); process.exit(2); }
const [px, py, pw, ph] = opt.patch.split(",").map(Number);
const FILL = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920";

function probe(f) {
  const r = spawnSync("ffprobe", ["-v", "error", "-select_streams", "v:0", "-show_entries",
    "stream=width,height,color_transfer,color_primaries,r_frame_rate:stream_side_data=rotation:format=duration",
    "-of", "json", f], { encoding: "utf8" });
  if (r.status) throw new Error("ffprobe failed on " + f + ": " + r.stderr);
  const j = JSON.parse(r.stdout), s = j.streams[0] || {};
  const rot = Math.abs(Number((s.side_data_list || []).find(d => "rotation" in d)?.rotation || 0)) % 180;
  const [n, d] = String(s.r_frame_rate || "30/1").split("/").map(Number);
  return {
    w: rot === 90 ? s.height : s.width, h: rot === 90 ? s.width : s.height,
    trc: s.color_transfer || "unknown", fps: s.r_frame_rate, rate: d ? n / d : 30, dur: Number(j.format?.duration || 0),
  };
}
// a standard output rate from the source's: 59.94 -> 60, 29.97 -> 30, 23.976 -> 24; never above 60
const stdRate = r => Math.min(60, [24, 25, 30, 48, 50, 60].reduce((b, c) => (Math.abs(c - r) < Math.abs(b - r) ? c : b), 30));
// skin level (luma, % of the legal range) on the patch of one frame, after the given filters
function skin(f, pre, t) {
  const r = spawnSync("ffmpeg", ["-nostdin", "-v", "error", "-ss", String(t), "-i", f, "-frames:v", "1", "-vf",
    `${pre ? pre + "," : ""}${FILL},crop=${pw}:${ph}:${px}:${py},format=yuv420p,signalstats,metadata=print:file=-`, "-f", "null", "-"],
    { encoding: "utf8" });
  const y = +((r.stdout + r.stderr).match(/signalstats\.YAVG=([\d.]+)/) || [])[1];
  return (y - 16) / 2.19;
}
const curve = (x, y) => `curves=all='0/0 ${(x / 100).toFixed(4)}/${(y / 100).toFixed(4)} 1/1'`;
// skin saturation (HSV (max-min)/max, % averaged over the patch) of one frame after the given filters
function skinSat(f, pre, t) {
  const r = spawnSync("ffmpeg", ["-nostdin", "-v", "error", "-ss", String(t), "-i", f, "-frames:v", "1", "-vf",
    `${pre ? pre + "," : ""}${FILL},crop=${pw}:${ph}:${px}:${py},format=rgb24`, "-f", "rawvideo", "-"], { maxBuffer: 1 << 26 });
  const b = r.stdout; let sum = 0, n = 0;
  for (let i = 0; i + 2 < b.length; i += 3) {
    const mx = Math.max(b[i], b[i + 1], b[i + 2]), mn = Math.min(b[i], b[i + 1], b[i + 2]);
    if (mx > 0) { sum += (mx - mn) / mx; n++; }
  }
  return n ? (sum / n) * 100 : NaN;
}
// the look for one take: a one-point curve that puts the patch on `target`, then (colour kept) the saturation factor
// that puts the patch's saturation back on the plain tonemap's. Returns the filter string and what it measured.
function solveLook(f, tone, t, target) {
  const base = skin(f, tone, t);
  let y = target, got = base;
  for (let pass = 0; pass < 3; pass++) {
    got = skin(f, [tone, curve(base, y)].filter(Boolean).join(","), t);
    if (Math.abs(got - target) <= 0.5) break;
    y += target - got;
  }
  const lifted = [tone, curve(base, y)].filter(Boolean).join(",");
  const ref = skinSat(f, tone, t);
  let s = 1, sat = skinSat(f, lifted, t);
  const satLifted = sat;
  if (opt.keepColour && Number.isFinite(ref) && Number.isFinite(sat)) {
    for (let pass = 0; pass < 3 && Math.abs(sat - ref) > 0.5; pass++) {
      s = Math.min(1.4, Math.max(0.8, s * ref / sat));
      sat = skinSat(f, `${lifted},eq=saturation=${s.toFixed(3)}`, t);
    }
  }
  const eqs = opt.keepColour && Math.abs(s - 1) > 0.005 ? `eq=saturation=${s.toFixed(3)},` : "";
  return { filter: curve(base, y) + "," + eqs, base, got, ref, satLifted, sat, s };
}

let failed = 0;
for (const f of opt.inputs) {
  if (!existsSync(f)) { console.error("missing " + f); failed++; continue; }
  const p = probe(f);
  if (p.w > p.h && !opt.allowLandscape) {
    console.error(`REFUSED ${f}: displays ${p.w}x${p.h} (landscape). A screen recording goes through broll-conform.py, not this; ` +
      "a landscape camera take needs --allow-landscape (it crops the centre third).");
    failed++; continue;
  }
  const four = opt.size === "4k" || (opt.size === "source" && Math.min(p.w, p.h) >= 2160);
  const [W, H] = four ? [2160, 3840] : [1080, 1920];
  const fps = opt.fps || stdRate(p.rate);
  const hdr = p.trc === "arib-std-b67" || p.trc === "smpte2084";
  const tone = hdr
    ? `zscale=t=linear:npl=${opt.npl},format=gbrpf32le,zscale=p=bt709,tonemap=mobius:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p`
    : "";
  const t = Math.min(opt.at, Math.max(0, p.dur / 2));
  let match = "", note = "", look = null;
  if (opt.match) {
    const recorded = skin(f, "", t);
    const target = opt.target ?? +(recorded + opt.lift).toFixed(1);
    if (opt.preview) {
      // four looks of this one frame, side by side; nothing is encoded
      const FONT = process.platform === "win32" ? "fontfile=/Windows/Fonts/arialbd.ttf:" : "";
      const variants = [["plain tonemap", null], [`skin ${(target - 3).toFixed(1)}`, target - 3], [`skin ${target.toFixed(1)} (target)`, target],
        [`skin ${(target + 3).toFixed(1)}`, target + 3]];
      const tiles = [];
      for (const [label, tg] of variants) {
        const lk = tg === null ? null : solveLook(f, tone, t, tg);
        const pre = [tone, lk ? lk.filter.replace(/,$/, "") : ""].filter(Boolean).join(",");
        const sat = skinSat(f, pre, t);
        const lab = `${label}${lk && Math.abs(lk.s - 1) > 0.005 ? "  sat x" + lk.s.toFixed(2) : ""}  (skin sat ${sat.toFixed(0)})`;
        const out = opt.preview.replace(/\.png$/i, "") + `-${tiles.length}.png`;
        const r = spawnSync("ffmpeg", ["-nostdin", "-y", "-v", "error", "-ss", String(t), "-i", f, "-frames:v", "1", "-vf",
          `${pre ? pre + "," : ""}${FILL},drawbox=x=${px}:y=${py}:w=${pw}:h=${ph}:color=cyan@0.5:t=3,scale=540:960,` +
          `drawtext=${FONT}text='${lab.replace(/[':%()]/g, " ")}':x=12:y=12:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=6`, out], { encoding: "utf8" });
        if (r.status) { console.error(r.stderr); process.exit(1); }
        tiles.push(out);
      }
      const r = spawnSync("ffmpeg", ["-nostdin", "-y", "-v", "error", ...tiles.flatMap(x => ["-i", x]), "-filter_complex",
        `hstack=${tiles.length}`, opt.preview], { encoding: "utf8" });
      if (r.status) { console.error(r.stderr); process.exit(1); }
      console.log(`preview ${opt.preview}: ${basename(f)} at ${t}s, recorded skin ${recorded.toFixed(1)}%, target ${target.toFixed(1)}% (+/-3 either side, colour ${opt.keepColour ? "kept" : "not kept"})`);
      process.exit(0);
    }
    look = solveLook(f, tone, t, target);
    match = look.filter;
    note = `skin recorded ${recorded.toFixed(1)}% / plain ${look.base.toFixed(1)}% -> target ${target.toFixed(1)}%` +
      (opt.keepColour ? `; skin sat plain ${look.ref.toFixed(1)}% / lifted ${look.satLifted.toFixed(1)}% -> kept ${look.sat.toFixed(1)}% (x${look.s.toFixed(2)})` : "");
  }
  const vf = `${tone ? tone + "," : ""}${match}${GRADES[opt.grade]}format=yuv420p,scale=${W}:${H}:force_original_aspect_ratio=increase:flags=lanczos,crop=${W}:${H},fps=${fps}`;
  const out = join(opt.outDir, basename(f, extname(f)) + ".mp4");
  // 4K on an 8 GB machine: the HLG tonemap works on ~100 MB float frames, and ffmpeg's default of one filter thread per
  // core (12 here) ran out of memory. Cap the decoder, filter and encoder threads and shorten x264's lookahead.
  const lowMem = W >= 2160 ? ["-threads", "4", "-filter_threads", "2"] : [];
  const r = spawnSync("ffmpeg", ["-nostdin", "-y", "-v", "error", ...lowMem, "-i", f, "-map", "0:v:0", "-map", "0:a:0?", "-vf", vf,
    "-c:v", "libx264", "-crf", String(opt.crf), "-preset", "fast", "-g", String(fps), "-keyint_min", String(fps),
    // x264 at 2160x3840@60 with automatic threads fails here ("Generic error in an external library": out of memory)
    ...(W >= 2160 ? ["-x264-params", "threads=4:rc-lookahead=10"] : []),
    "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv",
    "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-movflags", "+faststart", out], { encoding: "utf8" });
  if (r.status) { console.error(`FAILED ${f}: ${r.stderr.trim().split("\n").slice(-3).join(" | ")}`); failed++; continue; }
  const final = opt.match ? `, output skin ${skin(out, "", t).toFixed(1)}% sat ${skinSat(out, "", t).toFixed(1)}%` : "";
  console.log(`${basename(f)} -> ${out}  ${p.w}x${p.h} ${p.fps} ${p.trc}${hdr ? " (tonemapped)" : ""} -> ${W}x${H} ${fps}fps` +
    `${note ? "; " + note + final : ""}${opt.grade !== "none" ? "; grade " + opt.grade : ""}`);
}
process.exit(failed ? 1 : 0);
