#!/usr/bin/env node
// capture-article.mjs: the exact news article, as it really looks, for the R16 article overlay.
//
// Opens the URL in Chrome (Playwright from the HyperFrames kit), as a phone (393 px wide at 3x, so the page uses its
// own mobile layout, which fits a 9:16 reel) or a desktop (1280 px at 2x). Then:
//   - cookie / consent banners: clicks only a "reject / decline / necessary only" button; if there is none, the banner
//     is hidden with CSS. It never accepts.
//   - fixed and sticky clutter (ad rails, sticky video players, newsletter pop-ups) is hidden so the article reads
//     clean; the page itself is untouched (no text edits, no rebuilt layout: this is the real page).
//   - screenshots the top --height CSS px of the page (default 2200: headline, byline, hero, first paragraphs) at the
//     device scale, plus a viewport-only "top" shot for a cover or a glance.
//   - records, in SCREENSHOT pixels: the headline's box and every --highlight phrase's line boxes (exact text matches,
//     whitespace-insensitive), the og:title, site name, publish date, and the final URL. The overlay draws its
//     highlighter on exactly those boxes.
// Blocked (HTTP >= 400, a bot check, a captcha, a paywall interstitial): exits 3 and says so. Do not work around it
// (no fake user agents, no stealth plugins). Use another outlet's coverage of the same story, or the user takes the
// screenshot on their phone and it goes in as an image.
//
// Usage: node capture-article.mjs --url <article> --out W/public/img --name article
//        [--mode mobile|desktop] [--dpr 4.5] [--height 2200] [--highlight "phrase one" --highlight "phrase two"] [--kit <kit dir>]
// Writes <name>.png (the page), <name>-top.png (first screen), <name>.json (boxes + metadata).
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";

const args = process.argv.slice(2);
const one = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const many = k => args.flatMap((v, i) => (args[i - 1] === k ? [v] : []));
const url = one("--url"), outDir = one("--out"), name = one("--name", "article");
const mode = one("--mode", "mobile"), height = +one("--height", 2200), highlights = many("--highlight");
// device scale: 4.5 (mobile) for a 4K reel, where the L panel is ~1700 px wide; boxes come out in these image pixels.
// For the composition, divide by (dpr / 3) to get the page's 3x layout units, which stay the same at any dpr.
const dprArg = one("--dpr");
const kit = one("--kit", process.env.HF_KIT || process.cwd());
if (!existsSync(join(kit, "node_modules", "playwright"))) {
  console.error(`No HyperFrames kit at ${kit}: set HF_KIT to your hyperframes-student-kit folder, pass --kit, or run from it.`);
  process.exit(2);
}
if (!url || !outDir) { console.error("usage: node capture-article.mjs --url URL --out DIR [--name article] [--highlight phrase]"); process.exit(2); }
const { chromium } = createRequire(join(kit, "package.json"))("playwright");
mkdirSync(outDir, { recursive: true });

const MOBILE = { viewport: { width: 393, height: 852 }, deviceScaleFactor: 4.5, isMobile: true, hasTouch: true,
  userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1" };
const DESKTOP = { viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2 };
const ctxOpts = { ...(mode === "desktop" ? DESKTOP : MOBILE), ...(dprArg ? { deviceScaleFactor: +dprArg } : {}), locale: "en-US", colorScheme: "light", javaScriptEnabled: true };

let browser;
try { browser = await chromium.launch({ channel: "chrome", headless: true }); }
catch { browser = await chromium.launch({ headless: true }); }
const ctx = await browser.newContext(ctxOpts);
const page = await ctx.newPage();
const resp = await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
// check for a block BEFORE waiting on anything: a bot-check page keeps reloading itself, and evaluating on it throws
const blocked = async () => {
  const status = resp ? resp.status() : 0;
  const title = await page.title().catch(() => "");
  const body = await page.evaluate(() => document.body?.innerText.slice(0, 1500) || "").catch(() => "");
  const bot = /just a moment|attention required|access denied|verif(y|ying) (that )?you are (a )?human|captcha|are you a robot|subscribe to continue/i;
  return status >= 400 || bot.test(title + " " + body) ? `${status} "${title.slice(0, 60)}"` : null;
};
const quit = async why => {
  console.error(`BLOCKED (${why}): ${url}\nThe site refuses automated browsers. Do not work around it. Use another outlet's coverage of the same ` +
    "story, or have the user screenshot it on their phone and pass the image in.");
  await browser.close(); process.exit(3);
};
let why = await blocked(); if (why) await quit(why);
await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
await page.waitForTimeout(1500);
why = await blocked(); if (why) await quit(why);

// consent: reject/necessary-only if offered (also inside consent iframes); otherwise hide
const REJECT = /^(reject( all)?|decline( all)?|deny|only (strictly )?necessary|necessary only|use necessary cookies only|refuse( all)?|disagree)$/i;
let consent = "none seen";
// a bot-check page can close or replace itself mid-load: treat any "closed" error from here on as a block
process.on("unhandledRejection", async e => { if (/closed/i.test(String(e))) await quit("page closed itself during load"); else throw e; });
if (page.isClosed()) await quit("page closed itself during load");
for (const frame of page.frames()) {
  const btns = await frame.$$("button, [role=button], a").catch(() => []);
  for (const b of btns) {
    const t = ((await b.innerText().catch(() => "")) || "").trim();
    if (REJECT.test(t) && (await b.isVisible().catch(() => false))) { await b.click().catch(() => {}); consent = `clicked "${t}"`; break; }
  }
  if (consent !== "none seen") break;
}
await page.waitForTimeout(800).catch(() => {});
if (page.isClosed()) await quit("page closed itself during load");
why = await blocked(); if (why) await quit(why);

// hide fixed/sticky clutter and consent layers; never change the article's own text
const hidden = await page.evaluate(() => {
  let n = 0;
  for (const el of document.querySelectorAll("body *")) {
    const cs = getComputedStyle(el);
    const fixed = cs.position === "fixed" || cs.position === "sticky";
    const consentish = /(cookie|consent|gdpr|onetrust|didomi|cmp|privacy-banner|newsletter|subscribe-modal|paywall)/i.test(el.id + " " + el.className);
    if ((fixed && el.getBoundingClientRect().height < window.innerHeight * 0.9) || (consentish && fixed)) { el.style.setProperty("display", "none", "important"); n++; }
  }
  document.documentElement.style.overflow = "auto"; document.body.style.overflow = "auto";
  return n;
});
await page.evaluate(() => window.scrollTo(0, 0));
await page.waitForTimeout(500);

const meta = await page.evaluate(({ phrases }) => {
  const m = s => document.querySelector(s)?.getAttribute("content") || null;
  const h1 = document.querySelector("article h1, main h1, h1");
  const box = el => { const r = el.getBoundingClientRect(); return { x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height }; };
  // exact phrase -> line rects, matched across text nodes inside the smallest block that contains it
  const norm = s => s.replace(/\s+/g, " ").toLowerCase();
  const found = {};
  for (const phrase of phrases) {
    const want = norm(phrase).trim(); found[phrase] = [];
    const blocks = [...document.querySelectorAll("h1, h2, h3, p, li, blockquote, figcaption")].filter(b => norm(b.innerText).includes(want));
    const block = blocks.sort((a, b) => a.innerText.length - b.innerText.length)[0];
    if (!block) continue;
    const walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT);
    const nodes = []; let text = "";
    while (walker.nextNode()) { const n = walker.currentNode; nodes.push({ n, start: text.length }); text += n.data; }
    // build a normalised index map so whitespace runs match single spaces
    let flat = "", map = [];
    for (let i = 0; i < text.length; i++) { const c = /\s/.test(text[i]) ? " " : text[i].toLowerCase(); if (c === " " && flat.endsWith(" ")) continue; flat += c; map.push(i); }
    const at = flat.indexOf(want); if (at < 0) continue;
    const s = map[at], e = map[at + want.length - 1] + 1;
    const pos = k => { const hit = nodes.filter(x => x.start <= k).pop(); return [hit.n, Math.min(k - hit.start, hit.n.data.length)]; };
    const range = document.createRange(); range.setStart(...pos(s)); range.setEnd(...pos(e));
    found[phrase] = [...range.getClientRects()].filter(r => r.width > 2).map(r => ({ x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height }));
  }
  const time = document.querySelector("time[datetime]")?.getAttribute("datetime") || m('meta[property="article:published_time"]');
  return { title: m('meta[property="og:title"]') || document.title, site: m('meta[property="og:site_name"]'), published: time,
    headline: h1 ? { text: h1.innerText.trim(), ...box(h1) } : null, highlights: found, pageHeight: document.documentElement.scrollHeight };
}, { phrases: highlights });

const dpr = ctxOpts.deviceScaleFactor, vw = ctxOpts.viewport.width;
const clipH = Math.min(height, meta.pageHeight);
await page.screenshot({ path: join(outDir, `${name}.png`), clip: { x: 0, y: 0, width: vw, height: clipH }, fullPage: true });
await page.screenshot({ path: join(outDir, `${name}-top.png`) });
const px = r => ({ x: Math.round(r.x * dpr), y: Math.round(r.y * dpr), w: Math.round(r.w * dpr), h: Math.round(r.h * dpr) });
const out = {
  url, finalUrl: page.url(), domain: new URL(page.url()).hostname.replace(/^www\./, ""), site: meta.site, title: meta.title,
  published: meta.published, capturedAt: new Date().toISOString(), mode, size: [vw * dpr, Math.round(clipH * dpr)], dpr,
  headline: meta.headline ? { text: meta.headline.text, ...px(meta.headline) } : null,
  highlights: Object.fromEntries(Object.entries(meta.highlights).map(([k, v]) => [k, v.map(px)])), consent, hiddenFixed: hidden,
};
writeFileSync(join(outDir, `${name}.json`), JSON.stringify(out, null, 1));
await browser.close();
const missing = Object.entries(out.highlights).filter(([, v]) => !v.length).map(([k]) => k);
console.log(`${out.domain}: "${out.headline?.text || out.title}" -> ${join(outDir, name + ".png")} (${out.size.join("x")})` +
  `; consent ${consent}; ${hidden} fixed elements hidden; ${Object.keys(out.highlights).length - missing.length}/${highlights.length} highlights found` +
  (missing.length ? `\nNOT FOUND on the page (use the exact wording): ${missing.map(m => `"${m}"`).join(", ")}` : ""));
process.exit(missing.length ? 1 : 0);
