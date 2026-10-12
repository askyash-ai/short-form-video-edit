#!/usr/bin/env node
// reel-check.mjs: the brand and format gate for one reel composition. Exit 1 on any FAIL.
//
//   size      root is 1080x1920; data-fps matches input-video.mp4 (60 for a 4K60 source, 30 for HD30)
//   length    FAIL over 90 s; WARN outside 30-60 s
//   hook      something moves by 0.5 s (a card, the series tag or a camera op), and a card or line says the promise by 2.0 s
//   pacing    a visual change (card entrance, camera op, cutaway) at least every 4 s; WARN past 4 s, FAIL past 6 s.
//             Caption groups do not count: they change constantly and are not a visual beat.
//   cta       exactly one #cta with data-keyword, starting in the last 8 s, keyword spoken in the transcript
//   series    a #series tag in the first second (WARN only: a one-off topic may skip it)
//   captions  every spoken word sits inside a caption group's window (muted viewing is the default on Instagram)
//   sound     WARN on any audio file named like a whoosh/swish (never under copy)
//   joins     with --joins W/joins.json (find-joins.py): every jump cut on a face beat needs a camSet within 0.05 s
//             that CHANGES the framing (>= 0.05 from the scale just before it): the same framing either side reads as a
//             glitch. A cut under an L panel is hidden and skipped. WARN only (a deliberate hard cut is a choice).
//   headroom  no camera scale past the source's headroom: 1.50 for a 4K source, 1.12 for HD (FAIL: a soft picture)
//   privacy   FAIL when any term in the private denylist (employer, real customers, real product codes...) appears in the
//             composition, the transcript or any text file in public/. Denylist: <skill>/private/denylist.txt, one term
//             per line, # for comments. It never leaves this machine; keep it out of anything you share.
//
// Usage: node reel-check.mjs --public W/public [--transcript W/transcript.json] [--joins W/joins.json] [--denylist path]
import { readFileSync, existsSync, readdirSync, statSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { join, dirname, extname } from "node:path";
import { fileURLToPath } from "node:url";

const a = process.argv.slice(2), get = (k, d) => { const i = a.indexOf(k); return i >= 0 ? a[i + 1] : d; };
const PUB = get("--public"); if (!PUB) { console.error("usage: node reel-check.mjs --public W/public [--transcript t.json]"); process.exit(2); }
const IDX = join(PUB, "index.html"), TR = get("--transcript"), JOINS = get("--joins");
const DENY = get("--denylist", join(dirname(fileURLToPath(import.meta.url)), "..", "private", "denylist.txt"));
const html = readFileSync(IDX, "utf8");
let fails = 0, warns = 0;
const out = (lvl, area, msg) => { console.log(`${lvl.padEnd(4)} ${area.padEnd(9)} ${msg}`); if (lvl === "FAIL") fails++; if (lvl === "WARN") warns++; };
const attr = (s, k) => (s.match(new RegExp(`\\b${k}="([^"]*)"`)) || [])[1];

// size + length
const root = (html.match(/<div\b[^>]*data-composition-id="[^"]*"[^>]*>/) || [""])[0];
const W = +attr(root, "data-width"), H = +attr(root, "data-height"), FPS = +attr(root, "data-fps"), D = +attr(root, "data-duration");
out(W === 1080 && H === 1920 ? "ok" : "FAIL", "size", `${W}x${H}${FPS ? " @ " + FPS + " fps" : ""} (want 1080x1920)`);
// the source behind the composition: its frame rate and its zoom headroom
const SRC = join(PUB, "input-video.mp4");
let srcH = 0, srcFps = 0;
if (existsSync(SRC)) {
  const pr = spawnSync("ffprobe", ["-v", "error", "-select_streams", "v:0", "-show_entries", "stream=height,r_frame_rate", "-of", "csv=p=0", SRC], { encoding: "utf8" });
  const [h, r] = (pr.stdout || "").trim().split(",");
  const [n, d] = String(r || "0/1").split("/").map(Number);
  srcH = +h || 0; srcFps = d ? Math.round(n / d) : 0;
  if (srcFps) out(FPS === srcFps ? "ok" : "FAIL", "fps", `data-fps ${FPS || "missing"}, input-video.mp4 ${srcFps} fps (${srcH >= 3840 ? "4K" : "HD"} source)${FPS === srcFps ? "" : ": set data-fps to the source's rate"}`);
}
out(!(D > 0) || D > 90 ? "FAIL" : D < 30 || D > 60 ? "WARN" : "ok", "length", `${D} s (brand: 30-60 s, never over 90)`);

// beats: every timed .clip that is not a caption group, plus camera ops in the script
const beats = [];
for (const m of html.matchAll(/<(div|video|img)\b([^>]*)>/g)) {
  const at = m[2], cls = attr(at, "class") || "", s = attr(at, "data-start");
  if (!cls.split(/\s+/).includes("clip") || s === undefined || /\bcg\b/.test(cls)) continue;
  beats.push({ t: +s, what: "#" + (attr(at, "id") || m[1]), host: /card-host/.test(cls), anchor: attr(at, "data-anchor") });
}
const script = (html.match(/<script>([\s\S]*?)<\/script>/g) || []).join("\n").replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
for (const m of script.matchAll(/\b(punch|creep|camSet)\(\s*([\d.]+)/g)) if (+m[2] > 0) beats.push({ t: +m[2], what: m[1] + "()" });
// motion inside a panel counts as a visual change too (a highlight landing, a page scrolling, an item popping in):
// reel.js helpers called as helper('selector', time, ...)
for (const m of script.matchAll(/\b(pop|mark|pageTo|count|type|lgIn)\(\s*(['"`])([^'"`]*)\2\s*,\s*([\d.]+)/g))
  beats.push({ t: +m[4], what: `${m[1]}(${m[3]})`, inner: m[1] !== "lgIn" });
beats.sort((x, y) => x.t - y.t);
const first = beats.find(b => b.t <= 0.5);
out(first ? "ok" : "FAIL", "hook", first ? `first motion at ${first.t} s (${first.what})` : "nothing moves in the first 0.5 s: the first frame must already be working");
const promise = beats.find(b => b.host && b.what !== "#series" && b.what !== "#cta" && b.t <= 2.0);
out(promise ? "ok" : "WARN", "hook", promise ? `promise on screen by ${promise.t} s (${promise.what})` : "no card by 2.0 s: muted viewers need the promise on screen early");
const times = [0, ...beats.map(b => b.t), D].filter(t => t >= 0 && t <= D);
let worst = 0, at = 0;
for (let i = 1; i < times.length; i++) { const g = times[i] - times[i - 1]; if (g > worst) { worst = g; at = times[i - 1]; } }
const gaps = [];
for (let i = 1; i < times.length; i++) if (times[i] - times[i - 1] > 4) gaps.push(`${times[i - 1].toFixed(1)}-${times[i].toFixed(1)}`);
out(worst > 6 ? "FAIL" : worst > 4 ? "WARN" : "ok", "pacing",
  `${beats.length} visual changes, longest still stretch ${worst.toFixed(1)} s at ${at.toFixed(1)}${gaps.length ? " (over 4 s: " + gaps.join(", ") + ")" : ""}`);

// camera: scale over time from camSet / punch / creep (reel.js defaults 1.0 / 1.1 / 1.06), for the joins and headroom
const camOps = [];
for (const m of script.matchAll(/\b(camSet|punch)\(\s*([\d.]+)\s*(?:,\s*([\d.]+))?/g))
  camOps.push({ t: +m[2], op: m[1], s: m[3] !== undefined ? +m[3] : m[1] === "punch" ? 1.1 : 1.0 });
for (const m of script.matchAll(/\bcreep\(\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+))?/g))
  camOps.push({ t: +m[2], op: "creep", s: m[3] !== undefined ? +m[3] : 1.06 });
camOps.sort((x, y) => x.t - y.t);
const scaleAt = t => { let s = 1.0; for (const c of camOps) if (c.t <= t) s = c.s; return s; };
const limit = srcH >= 3840 ? 1.5 : 1.12;
const maxS = Math.max(1, ...camOps.map(c => c.s));
if (srcH) out(maxS <= limit + 1e-6 ? "ok" : "FAIL", "headroom", `largest camera scale ${maxS.toFixed(2)} (a ${srcH >= 3840 ? "4K" : "HD"} source holds ${limit.toFixed(2)})`);
if (JOINS) {
  const J = JSON.parse(readFileSync(JOINS, "utf8")).joins || [];
  const L = [...html.matchAll(/<div\b([^>]*\bclass="[^"]*card-host[^"]*"[^>]*)>/g)].map(m => m[1])
    .filter(at => attr(at, "data-size") === "l").map(at => [+attr(at, "data-start"), +attr(at, "data-start") + +attr(at, "data-duration")]);
  const bad = [], hidden = [];
  for (const j of J) {
    if (j >= D - 0.05) continue;
    if (L.some(([s, e]) => j >= s + 0.3 && j <= e - 0.3)) { hidden.push(j); continue; }
    const set = camOps.find(c => c.op === "camSet" && Math.abs(c.t - j) <= 0.05);
    const before = scaleAt(j - 0.06);
    if (!set) bad.push(`${j.toFixed(2)} (no camSet)`);
    else if (Math.abs(set.s - before) < 0.05) bad.push(`${j.toFixed(2)} (${before.toFixed(2)} -> ${set.s.toFixed(2)})`);
  }
  out(bad.length ? "WARN" : "ok", "joins", `${J.length} jump cuts, ${hidden.length} under L panels, ${J.length - hidden.length - bad.length} reframed` +
    (bad.length ? `; same framing either side at ${bad.join(", ")}: camSet(cut + 0.003, ${srcH >= 3840 ? "1.12" : "1.08"}) alternating with 1.0` : ""));
}

// CTA
const ctas = [...html.matchAll(/<div\b([^>]*\bid="cta"[^>]*)>/g)];
let kw = "";
if (ctas.length !== 1) out("FAIL", "cta", `${ctas.length} #cta elements (want exactly one)`);
else {
  const c = ctas[0][1]; kw = (attr(c, "data-keyword") || "").trim(); const s = +attr(c, "data-start");
  if (!kw || /__/.test(kw)) out("FAIL", "cta", "no data-keyword on #cta");
  else out(s >= D - 8 ? "ok" : "WARN", "cta", `"Comment ${kw}" at ${s} s${s >= D - 8 ? "" : " (want the last 8 s, after the payoff)"}`);
}
if (/__[A-Z_]+__/.test(html)) out("FAIL", "template", "unfilled placeholders: " + [...new Set(html.match(/__[A-Z_]+__/g))].join(" "));

// series tag
const series = beats.find(b => b.what === "#series");
out(series && series.t <= 1 ? "ok" : "WARN", "series", series ? `series tag at ${series.t} s` : "no #series tag (fine for a one-off; the three series should carry it)");

// transcript-based checks
let words = [];
if (TR && existsSync(TR)) {
  const raw = JSON.parse(readFileSync(TR, "utf8")); words = (Array.isArray(raw) ? raw : raw.words).filter(w => !w.type || w.type === "word");
  const norm = s => String(s).toLowerCase().replace(/[^a-z0-9]+/g, "");
  if (kw) out(words.some(w => norm(w.text) === norm(kw)) ? "ok" : "FAIL", "cta",
    words.some(w => norm(w.text) === norm(kw)) ? `keyword "${kw}" is spoken` : `keyword "${kw}" is never spoken (a misheard keyword kills the funnel: re-record the CTA line)`);
  const groups = [...html.matchAll(/<div\b([^>]*\bclass="cg clip"[^>]*)>/g)].map(m => [+attr(m[1], "data-start"), +attr(m[1], "data-start") + +attr(m[1], "data-duration")]);
  const miss = words.filter(w => { const mid = (+w.start + +w.end) / 2; return !groups.some(([s, e]) => mid >= s && mid <= e); });
  out(!groups.length ? "FAIL" : miss.length ? "FAIL" : "ok", "captions",
    !groups.length ? "no caption groups: run captions.mjs" : miss.length ? `${miss.length} spoken words outside any caption: ${miss.slice(0, 6).map(w => `"${w.text}"@${(+w.start).toFixed(2)}`).join(" ")}` : `${groups.length} groups cover all ${words.length} words`);
} else out("WARN", "captions", "no --transcript: caption coverage and keyword not checked");

// sound
for (const m of html.matchAll(/<audio\b([^>]*)>/g)) {
  const src = attr(m[1], "src") || "";
  if (/whoosh|swish|swoosh/i.test(src)) out("WARN", "sound", `${src}: whooshes never sit under copy`);
  if (!attr(m[1], "id")) out("FAIL", "sound", `${src}: <audio> without an id is silent in the render`);
}

// privacy denylist
if (existsSync(DENY)) {
  const terms = readFileSync(DENY, "utf8").split(/\r?\n/).map(s => s.trim()).filter(s => s && !s.startsWith("#"));
  const files = [IDX, ...(TR && existsSync(TR) ? [TR] : [])];
  const walk = d => { for (const f of readdirSync(d)) { const p = join(d, f); if (statSync(p).isDirectory()) walk(p); else if ([".html", ".json", ".csv", ".txt", ".md", ".svg"].includes(extname(p).toLowerCase()) && p !== IDX) files.push(p); } };
  walk(PUB);
  const hits = [];
  for (const f of files) { const s = readFileSync(f, "utf8").toLowerCase(); for (const t of terms) if (s.includes(t.toLowerCase())) hits.push(`"${t}" in ${f}`); }
  out(hits.length ? "FAIL" : "ok", "privacy", hits.length ? hits.join("; ") : `${terms.length} denylist terms, none found in ${files.length} files`);
} else out("WARN", "privacy", `no denylist at ${DENY}: create it with your employer and any real names/codes to block`);

console.log(`\n${fails ? fails + " FAIL" : "PASS"}${warns ? `, ${warns} WARN` : ""}`);
process.exit(fails ? 1 : 0);
