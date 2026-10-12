#!/usr/bin/env node
// layout-check.mjs: every overlay and every caption measured where it really lands, for its WHOLE time on screen,
// against the face and each platform's UI. Exit 1 on FAIL.
//
// Opens W/public/index.html in Chrome (Playwright from the HyperFrames kit) and seeks the timeline every 0.1 s through
// each .card-host's life (from entrance + 0.62 s, when the liquid-glass morph is done, to 0.32 s before its end, when
// lgOut starts), measuring the union of its .lg boxes each time. A camera move, a punch or an alternating jump-cut
// framing in the middle of a card is caught where it happens, not only at the card's first settled frame. Each caption
// group is measured 0.1 s after it appears. The face box comes from data-face="x,y,w,h" on the root (the head incl. hair
// and beard, on the un-zoomed frame) and is scaled with the camera at each moment (#video-zoom scale around its
// transform-origin).
//
//   size      every overlay declares data-size s|m|l (FAIL without one)
//   face      S and M must not touch the face at any moment (FAIL, with the worst overlap and when); L may cover it
//             (reported; WARN when #dim is under 0.3 then, so the footage does not step back)
//   budget    S up to 560x132, M up to 960 wide (WARN past those: it probably wants the next size up)
//   zones     per platform (below). The first --platform is the primary (FAIL); the others WARN, since the composition
//             is made for the primary.
//   captions  inside the platform's caption-safe area; never under an overlay at the same moment (FAIL); over the
//             (zoomed) chin by more than 60 px: WARN (move --band-top down, or frame looser)
//
//   platform   top   overlay bottom  caption bottom  right edge (overlays and captions)
//   instagram  250   1290            1500            1040; 960 below y 1000 (like / comment / share / audio column)
//   tiktok     200   1290            1550            1040; 940 below y 800 (TikTok's column starts higher)
//   shorts     250   1290            1530            1040; 880 below y 1000 (Shorts' wider column)
// The UIs move a little every year and third-party guides disagree by ~100 px; these are the safe ends of 2026's figures.
//
// Usage: node layout-check.mjs --public W/public [--platform instagram[,tiktok,shorts]] [--step 0.1] [--kit <kit dir>]
import { existsSync } from "node:fs";
import { createRequire } from "node:module";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const a = process.argv.slice(2), get = (k, d) => { const i = a.indexOf(k); return i >= 0 ? a[i + 1] : d; };
const PUB = get("--public"); if (!PUB) { console.error("usage: node layout-check.mjs --public W/public [--platform instagram,tiktok,shorts]"); process.exit(2); }
const kit = get("--kit", process.env.HF_KIT || process.cwd());
if (!existsSync(join(kit, "node_modules", "playwright"))) {
  console.error(`No HyperFrames kit at ${kit}: set HF_KIT to your hyperframes-student-kit folder, pass --kit, or run from it.`);
  process.exit(2);
}
const STEP = +get("--step", 0.1);
const ZONES = {
  instagram: { top: 250, bottom: 1290, capBottom: 1500, right: 1040, colRight: 960, colY: 1000 },
  tiktok:    { top: 200, bottom: 1290, capBottom: 1550, right: 1040, colRight: 940, colY: 800 },
  shorts:    { top: 250, bottom: 1290, capBottom: 1530, right: 1040, colRight: 880, colY: 1000 },
};
const PLATFORMS = get("--platform", "instagram").split(",").map(s => s.trim().toLowerCase()).filter(Boolean);
for (const p of PLATFORMS) if (!ZONES[p]) { console.error(`unknown platform ${p} (instagram, tiktok, shorts)`); process.exit(2); }
const { chromium } = createRequire(join(kit, "package.json"))("playwright");

let browser;
try { browser = await chromium.launch({ channel: "chrome", headless: true }); } catch { browser = await chromium.launch({ headless: true }); }
const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
const errors = [];
page.on("pageerror", e => errors.push(String(e)));
await page.goto(pathToFileURL(resolve(PUB, "index.html")).href, { waitUntil: "load" });
await page.waitForFunction(() => window.__timelines && Object.keys(window.__timelines).length, null, { timeout: 15000 });

const data = await page.evaluate((STEP) => {
  const tl = Object.values(window.__timelines)[0];
  const root = document.querySelector("[data-composition-id]");
  const face0 = (root.dataset.face || "").split(",").map(Number);
  const D = +root.dataset.duration;
  const zoom = document.querySelector("#video-zoom");
  const dimEl = document.querySelector("#dim");
  const union = rects => {
    rects = rects.filter(r => r.width && r.height);
    if (!rects.length) return null;
    return { x: Math.min(...rects.map(b => b.left)), y: Math.min(...rects.map(b => b.top)),
             r: Math.max(...rects.map(b => b.right)), b: Math.max(...rects.map(b => b.bottom)) };
  };
  const faceNow = () => {
    if (face0.length !== 4 || !face0.every(Number.isFinite)) return null;
    const sc = +gsap.getProperty(zoom, "scale") || 1;
    const [ox, oy] = getComputedStyle(zoom).transformOrigin.split(" ").map(parseFloat);
    const [fx, fy, fw, fh] = face0;
    return { x: ox + (fx - ox) * sc, y: oy + (fy - oy) * sc, r: ox + (fx + fw - ox) * sc, b: oy + (fy + fh - oy) * sc, sc };
  };
  const hosts = [...document.querySelectorAll(".card-host[data-start]")].map(h => ({
    el: h, id: h.id, size: h.dataset.size || "", s: +h.dataset.start, e: +h.dataset.start + +h.dataset.duration }));
  const groups = [...document.querySelectorAll(".cg[data-start]")].map(g => ({
    el: g, id: g.id, s: +g.dataset.start, e: +g.dataset.start + +g.dataset.duration }));
  const visibleHosts = t => hosts.filter(h => t >= h.s + 0.62 && t <= h.e - 0.32);
  const samples = [];
  const at = t => {
    tl.seek(t, false);
    return { t, face: faceNow(), dim: +getComputedStyle(dimEl || document.body).opacity || 0 };
  };
  for (const h of hosts) {
    const t0 = Math.min(h.s + 0.62, h.e - 0.05, D - 0.05), t1 = Math.max(t0, Math.min(h.e - 0.32, D - 0.05));
    const n = Math.min(120, Math.max(1, Math.floor((t1 - t0) / STEP) + 1));
    for (let k = 0; k < n; k++) {
      const s = at(t0 + (n === 1 ? 0 : (t1 - t0) * k / (n - 1)));
      s.host = h.id; s.box = union([...h.el.querySelectorAll(".lg")].map(e => e.getBoundingClientRect()));
      samples.push(s);
    }
  }
  const caps = [];
  for (const g of groups) {
    const s = at(Math.min(g.s + 0.1, g.e - 0.01));
    s.cap = g.id; s.box = union([...g.el.querySelectorAll(".w")].map(e => e.getBoundingClientRect()));
    s.under = visibleHosts(s.t).map(h => ({ id: h.id, box: union([...h.el.querySelectorAll(".lg")].map(e => e.getBoundingClientRect())) }))
      .filter(o => o.box);
    caps.push(s);
  }
  return { D, hosts: hosts.map(({ el, ...h }) => h), samples, caps };
}, STEP);
await browser.close();

let fails = 0, warns = 0;
const say = (lvl, id, msg) => { console.log(`${lvl.padEnd(4)} ${String(id).padEnd(14)} ${msg}`); if (lvl === "FAIL") fails++; if (lvl === "WARN") warns++; };
const overlap = (r, f, pad = 8) => Math.round(Math.max(0, Math.min(r.r, f.r - pad) - Math.max(r.x, f.x + pad)) *
                                                Math.max(0, Math.min(r.b, f.b - pad) - Math.max(r.y, f.y + pad)));
const fmt = r => `${Math.round(r.r - r.x)}x${Math.round(r.b - r.y)} at (${Math.round(r.x)},${Math.round(r.y)})`;
const zoneHits = (r, z, cap) => {
  const out = [];
  if (r.y < z.top) out.push(`top ${Math.round(r.y)} < ${z.top}`);
  if (!cap && r.b > z.bottom) out.push(`bottom ${Math.round(r.b)} > ${z.bottom} (captions)`);
  if (cap && r.b > z.capBottom) out.push(`bottom ${Math.round(r.b)} > ${z.capBottom} (the platform's caption / username area)`);
  if (r.x < 40) out.push(`left ${Math.round(r.x)} < 40`);
  if (r.r > z.right || (r.b > z.colY && r.r > z.colRight)) out.push(`right ${Math.round(r.r)} under the buttons (max ${r.b > z.colY ? z.colRight : z.right})`);
  return out;
};
for (const e of errors) say("FAIL", "page", "script error: " + e.slice(0, 160));

for (const h of data.hosts) {
  const ss = data.samples.filter(s => s.host === h.id && s.box);
  if (!ss.length) { say("WARN", "#" + h.id, `no .lg element visible between ${h.s.toFixed(2)} and ${h.e.toFixed(2)} s`); continue; }
  const span = `${ss[0].t.toFixed(2)}-${ss[ss.length - 1].t.toFixed(2)} s, ${ss.length} samples`;
  const first = ss[0].box, w = Math.round(first.r - first.x), hh = Math.round(first.b - first.y);
  if (!/^[sml]$/.test(h.size)) { say("FAIL", "#" + h.id, `no data-size s|m|l (${fmt(first)})`); continue; }
  const S = h.size.toUpperCase();
  let zoneBad = false;
  PLATFORMS.forEach((p, i) => {
    const hit = ss.map(s => ({ s, z: zoneHits(s.box, ZONES[p], false) })).find(x => x.z.length);
    if (hit) { zoneBad = zoneBad || i === 0; say(i === 0 ? "FAIL" : "WARN", "#" + h.id, `${S} ${p}: ${hit.z.join(", ")} at ${hit.s.t.toFixed(2)} s (${fmt(hit.s.box)})`); }
  });
  const withFace = ss.filter(s => s.face);
  if (!withFace.length) { say("WARN", "#" + h.id, `${S} ${fmt(first)}: no data-face on the root, face not checked`); continue; }
  const worst = withFace.map(s => ({ s, o: overlap(s.box, s.face) })).sort((x, y) => y.o - x.o)[0];
  const zoomNote = s => s.face.sc !== 1 ? ` (camera ${s.face.sc.toFixed(2)}x)` : "";
  if (h.size !== "l" && worst.o > 0)
    say("FAIL", "#" + h.id, `${S} covers ${worst.o} px² of the face at ${worst.s.t.toFixed(2)} s${zoomNote(worst.s)} (${fmt(worst.s.box)}): move it beside/above the head, frame looser at that cut, or make it L if it truly needs the space`);
  else if (h.size === "l") {
    const undimmed = withFace.find(s => overlap(s.box, s.face) > 0 && s.dim < 0.3);
    say(undimmed ? "WARN" : "ok", "#" + h.id, `L ${fmt(first)} ${span}${worst.o ? ", covers the face (allowed for L)" : ""}${undimmed ? `; not dimmed at ${undimmed.t.toFixed(2)} s: add dim()` : ""}`);
  } else if (!zoneBad) say("ok", "#" + h.id, `${S} ${fmt(first)} clear of the face for its whole life (${span})${worst.s.face.sc !== 1 ? ", incl. camera moves" : ""}`);
  if (h.size === "s" && (w > 560 || hh > 132)) say("WARN", "#" + h.id, `S is ${w}x${hh} (budget 560x132): is it really an M?`);
  if (h.size === "m" && w > 960) say("WARN", "#" + h.id, `M is ${w} wide (budget 960)`);
}

// captions
const caps = data.caps.filter(c => c.box);
if (caps.length) {
  let capBad = 0;
  PLATFORMS.forEach((p, i) => {
    const hits = caps.map(c => ({ c, z: zoneHits(c.box, ZONES[p], true) })).filter(x => x.z.length);
    if (hits.length) { capBad += i === 0; say(i === 0 ? "FAIL" : "WARN", "captions", `${p}: ${hits.length} group(s) outside the safe area, e.g. #${hits[0].c.cap} at ${hits[0].c.t.toFixed(2)} s: ${hits[0].z.join(", ")}`); }
  });
  const under = caps.flatMap(c => c.under.filter(o => overlap(c.box, o.box, 0) > 0).map(o => `#${c.cap} under #${o.id} at ${c.t.toFixed(2)} s`));
  if (under.length) { capBad++; say("FAIL", "captions", `${under.length} caption group(s) under an overlay: ${under.slice(0, 4).join("; ")}`); }
  const chin = caps.filter(c => c.face && c.face.b - c.box.y > 60).map(c => `${c.t.toFixed(1)} s (${Math.round(c.face.b - c.box.y)} px, camera ${c.face.sc.toFixed(2)}x)`);
  if (chin.length) say("WARN", "captions", `over the chin by more than 60 px at ${chin.length} group(s): ${chin.slice(0, 5).join(", ")}${chin.length > 5 ? " ..." : ""} (--band-top lower, or a looser framing there)`);
  if (!capBad) say("ok", "captions", `${caps.length} groups inside the ${PLATFORMS[0]} caption area, none under an overlay`);
} else say("WARN", "captions", "no caption groups found (captions.mjs not run yet?)");

console.log(`\n${fails ? fails + " FAIL" : "PASS"}${warns ? `, ${warns} WARN` : ""} (${data.hosts.length} overlays, ${data.samples.length} overlay samples, ${caps.length} caption groups; ${PLATFORMS.join(", ")})`);
process.exit(fails ? 1 : 0);
