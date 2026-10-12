#!/usr/bin/env node
// color-check.mjs: the "not washed out" gate. Exit 1 = do not deliver.
//
// Washed-out output has three causes, and this checks each one:
//   1. HDR footage read as SDR. iPhone HLG fed straight in looks grey and flat. FAIL when input-video.mp4 (or the
//      render) still carries an HLG/PQ transfer, or anything but bt709 primaries/transfer/matrix, limited (tv) range,
//      yuv420p. (conform-iphone.mjs fixes the footage; the bt709 remux fixes the tags.)
//   2. The render step lifting blacks or draining colour. On face-region crops (x 240-840, y 560-1240: clear of the
//      caption band and the top cards) at up to 6 moments with no card on screen, compare the render with
//      input-video.mp4 at the same time: black level (YLOW, 10th percentile) may rise at most 8, contrast
//      (YHIGH - YLOW) may drop at most 10%, saturation (SATAVG) at most 15%.
//   3. A flat source. WARN when the source crop's saturation is under 9 or its contrast under 120: the footage itself
//      reads washed out (re-conform with --grade deep, or relight), even if the render matches it.
//   4. Skin off the footage's own tone (--skin x,y,w,h: the forehead patch skin-match.mjs used; --skin-target: its
//      SKIN_TARGET, i.e. the camera's recorded level + the small lift). The rule (2026-10-07): "the exact same skin tone
//      as the actual footage, just a tad of light, uniform". FAIL more than 4 points off the target or brighter than
//      target + 3 at the median; WARN 2.5-4 off (a single frame wanders as the head turns; the median is what counts).
//      Without --skin-target it only reports the level. Reel-1: recorded 70.5%, target 72.5%, v2 sat at ~75-77.
// Reel-1 measured for reference (2026-10-07): unconverted draft SATAVG 6.7; tonemapped ~15.
//
// Usage: node color-check.mjs --render W/renders/<slug>-v1.mp4 --public W/public [--at 1.0,5.2]
//        [--skin 330,790,240,60 --skin-target 72.5]
//        [--source other-footage.mp4] [--index other/index.html]   (for projects not laid out as W/public)
import { spawnSync } from "node:child_process";
import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";

const a = process.argv.slice(2), get = (k, d) => { const i = a.indexOf(k); return i >= 0 ? a[i + 1] : d; };
const R = get("--render"), PUB = get("--public");
if (!R || !PUB) { console.error("usage: node color-check.mjs --render out.mp4 --public W/public [--at t,t]"); process.exit(2); }
const SRC = get("--source", join(PUB, "input-video.mp4")), IDX = get("--index", join(PUB, "index.html"));
let fails = 0, warns = 0;
const line = (lvl, msg) => { console.log(`${lvl.padEnd(4)} ${msg}`); if (lvl === "FAIL") fails++; if (lvl === "WARN") warns++; };

function tags(f) {
  const r = spawnSync("ffprobe", ["-v", "error", "-select_streams", "v:0", "-show_entries",
    "stream=pix_fmt,color_range,color_primaries,color_transfer,color_space:format=duration", "-of", "json", f], { encoding: "utf8" });
  const j = JSON.parse(r.stdout); return { ...j.streams[0], duration: +j.format.duration };
}
for (const [name, f] of [["source", SRC], ["render", R]]) {
  if (!existsSync(f)) { line("FAIL", `${name}: missing ${f}`); continue; }
  const t = tags(f);
  const bad = [];
  if (["arib-std-b67", "smpte2084"].includes(t.color_transfer)) bad.push(`HDR transfer ${t.color_transfer} (run conform-iphone.mjs)`);
  for (const k of ["color_primaries", "color_transfer", "color_space"]) if (t[k] !== "bt709") bad.push(`${k}=${t[k] || "unknown"}`);
  if (t.color_range !== "tv") bad.push(`color_range=${t.color_range || "unknown"} (want tv)`);
  if (t.pix_fmt !== "yuv420p") bad.push(`pix_fmt=${t.pix_fmt}`);
  line(bad.length ? "FAIL" : "ok", `${name} tags: ${bad.length ? bad.join(", ") : "bt709 x3, tv range, yuv420p"}`);
}
if (fails) { console.log(`\n${fails} FAIL: fix the tags/footage first (see SKILL.md "Colour: never washed out").`); process.exit(1); }

// moments with no card on screen (the series tag sits above the crop and is allowed)
const dur = tags(R).duration;
let busy = [];
if (existsSync(IDX)) {
  const html = readFileSync(IDX, "utf8");
  for (const m of html.matchAll(/<div\b([^>]*\bclass="[^"]*card-host[^"]*"[^>]*)>/g)) {
    const at = m[1], id = (at.match(/\bid="([^"]+)"/) || [])[1];
    const s = +(at.match(/data-start="([\d.]+)"/) || [])[1], d = +(at.match(/data-duration="([\d.]+)"/) || [])[1];
    if (id !== "series" && Number.isFinite(s) && Number.isFinite(d)) busy.push([s - 0.2, s + d + 0.2]);
  }
}
let times = (get("--at", "") || "").split(",").filter(Boolean).map(Number);
if (!times.length) {
  for (let t = 0.6; t < dur - 0.3; t += 0.25) if (!busy.some(([s, e]) => t >= s && t <= e)) times.push(+t.toFixed(2));
  const step = Math.max(1, Math.floor(times.length / 6));
  times = times.filter((_, i) => i % step === 0).slice(0, 6);
}
if (!times.length) { line("WARN", "no moment without a card on screen: pass --at with face-only times"); process.exit(0); }

function stats(f, t) {
  const r = spawnSync("ffmpeg", ["-v", "error", "-ss", String(t), "-i", f, "-frames:v", "1", "-vf",
    "scale=1080:1920,crop=600:680:240:560,signalstats,metadata=print:file=-", "-f", "null", "-"], { encoding: "utf8" });
  const g = k => +((r.stdout + r.stderr).match(new RegExp(`signalstats\\.${k}=([\\d.]+)`)) || [])[1];
  return { ylow: g("YLOW"), yhigh: g("YHIGH"), sat: g("SATAVG") };
}
const fmt = s => `black ${s.ylow} contrast ${s.yhigh - s.ylow} sat ${s.sat.toFixed(1)}`;
for (const t of times) {
  const s = stats(SRC, t), r = stats(R, t);
  const why = [];
  if (r.ylow - s.ylow > 8) why.push(`blacks lifted +${r.ylow - s.ylow}`);
  if ((r.yhigh - r.ylow) < 0.9 * (s.yhigh - s.ylow)) why.push("contrast down >10%");
  if (r.sat < 0.85 * s.sat) why.push("saturation down >15%");
  line(why.length ? "FAIL" : "ok", `t=${t.toFixed(2)}  source ${fmt(s)} | render ${fmt(r)}${why.length ? "  <- " + why.join(", ") : ""}`);
  if (s.sat < 9 || s.yhigh - s.ylow < 120) line("WARN", `t=${t.toFixed(2)}  the source itself is flat (sat ${s.sat.toFixed(1)}, contrast ${s.yhigh - s.ylow}): re-conform with --grade strong or relight`);
}
const skin = get("--skin");
if (skin) {
  const [x, y, w, h] = skin.split(",").map(Number);
  const target = get("--skin-target") ? +get("--skin-target") : null;
  const levels = [];
  for (const t of times) {
    const r = spawnSync("ffmpeg", ["-v", "error", "-ss", String(t), "-i", R, "-frames:v", "1", "-vf",
      `scale=1080:1920,crop=${w}:${h}:${x}:${y},signalstats,metadata=print:file=-`, "-f", "null", "-"], { encoding: "utf8" });
    const y0 = +((r.stdout + r.stderr).match(/signalstats\.YAVG=([\d.]+)/) || [])[1];
    const lv = (y0 - 16) / 2.19; levels.push(lv);
    const off = target == null ? 0 : lv - target;
    const lvl = target == null ? "info" : Math.abs(off) > 4 ? "WARN" : Math.abs(off) > 2.5 ? "WARN" : "ok";
    line(lvl, `t=${t.toFixed(2)}  skin ${lv.toFixed(1)}%${target == null ? "" : ` (target ${target}, ${off >= 0 ? "+" : ""}${off.toFixed(1)})`}`);
  }
  if (target != null && levels.length) {
    const med = [...levels].sort((p, q) => p - q)[Math.floor(levels.length / 2)], off = med - target;
    line(Math.abs(off) > 4 || off > 3 ? "FAIL" : "ok", `skin median ${med.toFixed(1)}% vs target ${target} (${off >= 0 ? "+" : ""}${off.toFixed(1)})` +
      (off > 3 ? "  <- too light: re-run skin-match and conform with its SKIN_TARGET" : off < -4 ? "  <- too dark" : ""));
  }
  // colour kept (2026-10-11): the conform restored the skin's recorded saturation; the render must not move it either way
  // (greyer = washed out, richer = "looks fake"). HSV (max-min)/max on the patch, render vs the conformed source.
  const skinSat = (f, t) => {
    const r = spawnSync("ffmpeg", ["-v", "error", "-ss", String(t), "-i", f, "-frames:v", "1", "-vf",
      `scale=1080:1920,crop=${w}:${h}:${x}:${y},format=rgb24`, "-f", "rawvideo", "-"], { maxBuffer: 1 << 26 });
    const b = r.stdout; let sum = 0, n = 0;
    for (let i = 0; i + 2 < b.length; i += 3) {
      const mx = Math.max(b[i], b[i + 1], b[i + 2]), mn = Math.min(b[i], b[i + 1], b[i + 2]);
      if (mx > 0) { sum += (mx - mn) / mx; n++; }
    }
    return n ? (sum / n) * 100 : NaN;
  };
  const diffs = times.map(t => skinSat(R, t) - skinSat(SRC, t)).filter(Number.isFinite).sort((p, q) => p - q);
  if (diffs.length) {
    const md = diffs[Math.floor(diffs.length / 2)];
    line(Math.abs(md) > 2 ? "FAIL" : "ok", `skin saturation render vs source ${md >= 0 ? "+" : ""}${md.toFixed(1)} points (want within 2: the recorded colour, kept)` +
      (md < -2 ? "  <- greyer: washed out" : md > 2 ? "  <- richer than recorded: reads as fake" : ""));
  }
}
console.log(`\n${fails ? fails + " FAIL: do not deliver." : "PASS: render keeps the source's blacks, contrast and colour."}${warns ? ` ${warns} WARN.` : ""}`);
process.exit(fails ? 1 : 0);
