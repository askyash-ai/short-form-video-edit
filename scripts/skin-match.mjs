#!/usr/bin/env node
// skin-match.mjs: measure the skin tone the camera actually recorded in every take, and the level the conform produces,
// so conform-iphone.mjs can reproduce the footage's own skin tone (plus a very small lift) identically across takes.
//
// "The actual footage" = the HLG signal itself. HLG is built to be backward compatible: its signal level on a skin patch
// is what a viewer sees as that skin's brightness. The plain tonemap lands skin brighter than that (reel-1: forehead
// signal ~65%, tonemap ~75%: "I am appearing too light"), and darkening by eye overshoots. This measures both per take
// on a forehead patch and prints the target (median signal level across takes + --lift, default 2 points) that
// conform-iphone.mjs --skin-target then hits on every take, so the cut reads as one continuous shot.
//
// FLOOR (2026-10-11): a dim shoot is lifted further. The creator picked "C + colour kept" on a take recorded at 53.7%:
// skin at ~63%, its colour kept (conform-iphone.mjs restores the saturation). So the target is never under --floor
// (default 63): max(median + lift, floor). A well-lit shoot (reel-1: 70.5 -> 72.5) is untouched by it. Look at
// conform-iphone.mjs --preview before encoding and move the target per reel if the raw clips need it.
//
// Usage: node skin-match.mjs --patch 330,790,240,60 [--at 2.5] [--lift 2] [--floor 63] [--sheet out.png] TAKE.MOV ...
//   --patch  x,y,w,h on the 1080x1920 frame: a flat, evenly lit forehead patch (no hair, brows or shine). Check it on
//            the --sheet, which draws the patch on every take.
// Prints one line per take and a final line: SKIN_TARGET=<percent>. Exit 1 when a take's patch is not on skin
// (saturation under 15: wall or hair).
import { spawnSync } from "node:child_process";

const a = process.argv.slice(2);
const get = (k, d) => { const i = a.indexOf(k); if (i < 0) return d; const v = a[i + 1]; a.splice(i, 2); return v; };
const patch = get("--patch"), at = +get("--at", 2.5), lift = +get("--lift", 2), floor = +get("--floor", 63), sheet = get("--sheet");
const takes = a;
if (!patch || !takes.length) { console.error("usage: node skin-match.mjs --patch x,y,w,h [--at s] [--lift 2] [--sheet png] TAKE ..."); process.exit(2); }
const [x, y, w, h] = patch.split(",").map(Number);
const FILL = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920";
export const TONEMAP = "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=mobius:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p";

function stats(file, pre) {
  const r = spawnSync("ffmpeg", ["-nostdin", "-v", "error", "-ss", String(at), "-i", file, "-frames:v", "1", "-vf",
    `${pre ? pre + "," : ""}${FILL},crop=${w}:${h}:${x}:${y},format=yuv420p,signalstats,metadata=print:file=-`, "-f", "null", "-"], { encoding: "utf8" });
  const g = k => +((r.stdout + r.stderr).match(new RegExp(`signalstats\\.${k}=([\\d.]+)`)) || [])[1];
  return { pct: (g("YAVG") - 16) / 2.19, sat: g("SATAVG") };
}
function trc(file) {
  return spawnSync("ffprobe", ["-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_transfer", "-of", "csv=p=0", file],
    { encoding: "utf8" }).stdout.split(/[,\r\n]/)[0].trim();   // MOV side data adds a trailing ","
}

const rows = [];
let bad = 0;
for (const f of takes) {
  const hdr = ["arib-std-b67", "smpte2084"].includes(trc(f));
  const sig = stats(f, "");                 // the recorded signal (HLG code values read as-is: the camera's skin level)
  const tm = hdr ? stats(f, TONEMAP) : sig;  // where the plain tonemap puts it
  const onSkin = tm.sat >= 15;
  if (!onSkin) bad++;
  rows.push({ f, hdr, sig: sig.pct, tm: tm.pct });
  console.log(`${f.split(/[\\/]/).pop().padEnd(16)} ${hdr ? "HLG" : "SDR"}  recorded skin ${sig.pct.toFixed(1)}%  plain tonemap ${tm.pct.toFixed(1)}%` +
    `${onSkin ? "" : "  <- patch is not on skin (sat " + tm.sat.toFixed(1) + "): move --patch"}`);
}
if (sheet) {
  const ins = takes.flatMap(f => ["-ss", String(at), "-i", f]);
  const per = takes.map((_, i) => `[${i}:v]${FILL},drawbox=x=${x}:y=${y}:w=${w}:h=${h}:color=cyan:t=6,scale=270:-2[v${i}]`).join(";");
  spawnSync("ffmpeg", ["-nostdin", "-y", "-v", "error", ...ins, "-filter_complex",
    `${per};${takes.map((_, i) => `[v${i}]`).join("")}hstack=${takes.length}`, "-frames:v", "1", sheet]);
  console.log("patch sheet: " + sheet);
}
const sorted = rows.map(r => r.sig).sort((p, q) => p - q);
const median = sorted[Math.floor(sorted.length / 2)];
const target = +Math.max(median + lift, floor).toFixed(1);
console.log(`recorded skin median ${median.toFixed(1)}%, spread ${(sorted[sorted.length - 1] - sorted[0]).toFixed(1)} points; lift +${lift}` +
  (median + lift < floor ? `; a dim shoot: lifted to the ${floor}% floor (colour kept by the conform)` : ""));
console.log(`SKIN_TARGET=${target}`);
process.exit(bad ? 1 : 0);
