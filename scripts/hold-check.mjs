#!/usr/bin/env node
// hold-check.mjs: every payoff stays on screen long enough to be read, BEFORE anything is rendered. Exit 1 on FAIL.
//
// Added 2026-10-11 after aotw-01 needed three re-renders for the same fault: a card's last element (the hook's "ALL",
// the "0:31 REEL" node, the "Can't hear the audio" row) popped on its word 0.3-0.4 s before the card began to close.
//
// Opens W/public/index.html in Chrome (the kit's Playwright), seeks the timeline every --step s (0.05) through each
// .card-host's life and reads the effective opacity (the element's x its ancestors' up to the card) of every element
// with an id inside it. A PAYOFF is an element that is still visible when the card starts to close (lgOut begins
// 0.28 s before the card's end); its hold is from the moment it first reaches full opacity to that moment.
//   hold      FAIL under --min (0.5 s), WARN under --warn (0.8 s), counted from FULL opacity (a pop takes 0.34 s).
//             Calibrated on aotw-01 v4 (approved): the hook's "ALL" 0.57 s and the SOP tile 0.60 s passed the creator's eye
//             (WARN); "Quality gates" 0.30 s, "Buttons clear" 0.42 s and the flub tags 0.02-0.12 s are the FAILs to avoid. Fix: pop it on an earlier word, or keep the card up
//             longer (another card may share the window if it sits in another zone), never shorten the entrance.
//   card      WARN when a card is settled (entrance done at +0.62 s) for under 1.0 s before it starts to close.
// Elements swapped out before the card closes (a flip's first state, "+ Follow" before "Following") are not payoffs.
//
// Usage: node hold-check.mjs --public W/public [--min 0.5] [--warn 0.8] [--step 0.05] [--kit <kit dir>]
import { existsSync } from "node:fs";
import { createRequire } from "node:module";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const a = process.argv.slice(2), get = (k, d) => { const i = a.indexOf(k); return i >= 0 ? a[i + 1] : d; };
const PUB = get("--public"); if (!PUB) { console.error("usage: node hold-check.mjs --public W/public [--min 0.7]"); process.exit(2); }
const kit = get("--kit", process.env.HF_KIT || process.cwd());
if (!existsSync(join(kit, "node_modules", "playwright"))) {
  console.error(`No HyperFrames kit at ${kit}: set HF_KIT to your hyperframes-student-kit folder, pass --kit, or run from it.`);
  process.exit(2);
}
const MIN = +get("--min", 0.5), WARN = +get("--warn", 0.8), STEP = +get("--step", 0.05), EXIT = 0.28, SETTLE = 0.62;
const { chromium } = createRequire(join(kit, "package.json"))("playwright");

let browser;
try { browser = await chromium.launch({ channel: "chrome", headless: true }); } catch { browser = await chromium.launch({ headless: true }); }
const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
await page.goto(pathToFileURL(resolve(PUB, "index.html")).href, { waitUntil: "load" });
// a GSAP timeline is a thenable: return a boolean, or waitForFunction waits for the (paused) timeline to "resolve"
await page.waitForFunction(() => !!(window.__timelines && Object.keys(window.__timelines).length), null, { timeout: 15000 });

const res = await page.evaluate(({ STEP, EXIT }) => {
  const tl = Object.values(window.__timelines)[0];
  const cards = [...document.querySelectorAll(".card-host[data-start][data-duration]")].map(h => ({
    id: h.id, s: +h.dataset.start, e: +h.dataset.start + +h.dataset.duration, host: h,
    els: [...h.querySelectorAll("[id]")].map(el => ({ id: el.id, el, first: null, atExit: 0 })),
  }));
  const eff = (el, host) => { let o = 1; for (let n = el; n && n !== host; n = n.parentElement) o *= +getComputedStyle(n).opacity; return o; };
  for (const c of cards) {
    const exitAt = c.e - EXIT;
    for (let t = c.s; t <= exitAt + 1e-6; t += STEP) {
      tl.seek(t, false);
      for (const x of c.els) {
        const o = eff(x.el, c.host);
        if (o >= 0.99 && x.first === null) x.first = t;
        if (o < 0.99 && x.first !== null && t < exitAt - STEP) x.first = null;   // went away again: not settled yet
      }
    }
    tl.seek(exitAt - 0.01, false);
    for (const x of c.els) x.atExit = eff(x.el, c.host);
  }
  return cards.map(c => ({ id: c.id, s: c.s, e: c.e, els: c.els.map(x => ({ id: x.id, first: x.first, atExit: x.atExit })) }));
}, { STEP, EXIT });
await browser.close();

let fails = 0, warns = 0;
for (const c of res) {
  const exitAt = c.e - EXIT, settled = exitAt - (c.s + SETTLE);
  if (settled < 1.0) { warns++; console.log(`WARN card  #${c.id}  settled for only ${settled.toFixed(2)} s (${c.s.toFixed(2)}-${c.e.toFixed(2)})`); }
  for (const x of c.els) {
    if (x.atExit < 0.99 || x.first === null) continue;                    // swapped out, or never fully shown
    const hold = exitAt - x.first;
    if (hold < MIN) { fails++; console.log(`FAIL hold  #${x.id} in #${c.id}: on screen ${hold.toFixed(2)} s before the card closes at ${exitAt.toFixed(2)} (want >= ${MIN})`); }
    else if (hold < WARN) { warns++; console.log(`WARN hold  #${x.id} in #${c.id}: ${hold.toFixed(2)} s (want >= ${WARN})`); }
  }
}
console.log(`\n${fails ? fails + " FAIL" : "PASS"}${warns ? ", " + warns + " WARN" : ""} (${res.length} cards, ${res.reduce((n, c) => n + c.els.length, 0)} elements)`);
process.exit(fails ? 1 : 0);
