#!/usr/bin/env node
// snap-reel.mjs: one snapshot per beat of a reel, tiled into W/snaps/sheet.png with the Instagram UI zones shaded,
// so Checkpoint B is one image: every card moment, its timestamp, and whether anything sits under the Reels UI.
//
// Moments: every .card-host data-start + 0.6 s (the entrance has landed), the CTA + 1.2 s, any --at extras, and
// --every N s across the whole reel when given. Shaded red: top 0-250 (Reels header), bottom 1500-1920 (caption,
// handle, audio), right 960-1080 (like / comment / share column). Text in red is text the viewer cannot read.
//
// Usage: node snap-reel.mjs --project W [--at 3.2,8.0] [--every 3] [--cols 4]
import { spawnSync } from "node:child_process";
import { readFileSync, readdirSync, mkdirSync, rmSync, existsSync } from "node:fs";
import { join } from "node:path";

const a = process.argv.slice(2), get = (k, d) => { const i = a.indexOf(k); return i >= 0 ? a[i + 1] : d; };
const P = get("--project"); if (!P) { console.error("usage: node snap-reel.mjs --project W [--at t,t] [--every s]"); process.exit(2); }
const PUB = join(P, "public"), html = readFileSync(join(PUB, "index.html"), "utf8");
const D = +(html.match(/data-composition-id="[^"]*"[^>]*data-duration="([\d.]+)"/) || html.match(/data-duration="([\d.]+)"/))[1];
const cols = +get("--cols", 4);
// ffmpeg on Windows has no fontconfig: drawtext needs an explicit font file
// (drive-less: "C:" inside a filtergraph needs fragile escaping; this path resolves on the current drive)
const FONT = process.platform === "win32" ? "fontfile=/Windows/Fonts/arial.ttf:" : "";
let ts = [];
for (const m of html.matchAll(/<div\b([^>]*\bclass="[^"]*card-host[^"]*"[^>]*)>/g)) {
  const s = +(m[1].match(/data-start="([\d.]+)"/) || [])[1]; const id = (m[1].match(/\bid="([^"]+)"/) || [])[1];
  if (Number.isFinite(s)) ts.push(s + (id === "cta" ? 1.2 : 0.6));
}
ts.push(...(get("--at", "") || "").split(",").filter(Boolean).map(Number));
const every = +get("--every", 0); if (every > 0) for (let t = 0.5; t < D; t += every) ts.push(t);
ts = [...new Set(ts.map(t => +Math.min(Math.max(t, 0.05), D - 0.05).toFixed(2)))].sort((x, y) => x - y);

const raw = join(P, "snaps", "raw"); rmSync(raw, { recursive: true, force: true }); mkdirSync(raw, { recursive: true });
const r = spawnSync(`npx hyperframes snapshot "${PUB}" --at ${ts.join(",")} --no-end --describe false -o "${raw}"`, { shell: true, encoding: "utf8" });
if (r.status) { console.error(r.stdout + r.stderr); process.exit(1); }
const pngs = readdirSync(raw).filter(f => f.endsWith(".png")).sort();
if (!pngs.length) { console.error("no snapshots written to " + raw); process.exit(1); }

// shade the UI zones and stamp the time on each frame, then tile
const zone = "drawbox=x=0:y=0:w=1080:h=250:color=red@0.28:t=fill,drawbox=x=0:y=1500:w=1080:h=420:color=red@0.28:t=fill," +
  "drawbox=x=960:y=250:w=120:h=1250:color=red@0.28:t=fill";
const args = ["-y", "-v", "error"]; pngs.forEach(f => args.push("-i", join(raw, f)));
let n = pngs.length; while (n % cols) { args.push("-i", join(raw, pngs[pngs.length - 1])); n++; }
const per = Array.from({ length: n }, (_, i) =>
  `[${i}]scale=1080:1920,${zone},scale=270:480,drawtext=${FONT}text='${i < ts.length ? ts[i].toFixed(2) : ""}s':x=8:y=8:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6[v${i}]`).join(";");
args.push("-filter_complex", `${per};${Array.from({ length: n }, (_, i) => `[v${i}]`).join("")}concat=n=${n}:v=1:a=0,tile=${cols}x${n / cols}`,
  "-frames:v", "1", join(P, "snaps", "sheet.png"));
const f = spawnSync("ffmpeg", args, { encoding: "utf8" });
if (f.status) { console.error(f.stderr); process.exit(1); }
console.log(`${pngs.length} snapshots at ${ts.join(", ")} s -> ${join(P, "snaps", "sheet.png")} (red = under the Reels UI)`);
