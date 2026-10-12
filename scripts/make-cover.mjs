#!/usr/bin/env node
// make-cover.mjs: the reel's cover image (cover.png), built the same way as the reel so it looks like it: a frame of the
// conformed footage, the reel's liquid glass, Inter / JetBrains Mono through the HyperFrames renderer. Then it checks
// the card against the face and against both crops Instagram makes of a cover, and writes cover-crops.png (the full
// cover, the 3:4 profile-grid crop, the 4:5 feed crop, side by side) to READ before delivering.
//
//   crops   the card inside y 285-1635 (4:5 feed) and y 240-1680 (3:4 grid), x 60-1020: FAIL otherwise
//   face    the card clear of the face box (data-face from public/index.html): FAIL otherwise (pick a frame where the
//           head sits lower, or shorten the title)
//   copy    the title at most 2 lines and 6 words (WARN): a cover is read at thumbnail size
//
// Title markup: "|" breaks the line, *word* is the accent (teal; with --tone danger it is light red, warn amber).
// Usage: node make-cover.mjs --project W --at 12.4 --title "Fake AI logins|*steal* your 2FA" [--eyebrow "AI AT WORK · SECURITY"]
//        [--tone accent|danger|warn] [--top 290] [--out W/renders/cover.png] [--kit <kit dir>]
import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync, mkdirSync, copyFileSync, existsSync, readdirSync, rmSync } from "node:fs";
import { createRequire } from "node:module";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const a = process.argv.slice(2), get = (k, d) => { const i = a.indexOf(k); return i >= 0 ? a[i + 1] : d; };
const P = get("--project"), AT = get("--at"), TITLE = get("--title");
if (!P || AT === undefined || !TITLE) { console.error('usage: node make-cover.mjs --project W --at <s> --title "Line one|*accent* line two" [--eyebrow ...] [--tone accent|danger|warn]'); process.exit(2); }
const kit = get("--kit", process.env.HF_KIT || process.cwd());
if (!existsSync(join(kit, "node_modules", "playwright"))) {
  console.error(`No HyperFrames kit at ${kit}: set HF_KIT to your hyperframes-student-kit folder, pass --kit, or run from it.`);
  process.exit(2);
}
const SK = join(dirname(fileURLToPath(import.meta.url)), "..");
const PUB = join(P, "public"), OUTP = resolve(get("--out", join(P, "renders", "cover.png")));
const tone = get("--tone", "accent"), top = +get("--top", 290), eyebrow = get("--eyebrow", "");
if (!["accent", "danger", "warn"].includes(tone)) { console.error("--tone is accent, danger or warn"); process.exit(2); }
const esc = s => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const accentCls = { accent: "em", danger: "bad", warn: "warn" }[tone];
const titleHtml = TITLE.split("|").map(l => esc(l.trim()).replace(/\*([^*]+)\*/g, `<span class="${accentCls}">$1</span>`)).join("<br>");
const index = existsSync(join(PUB, "index.html")) ? readFileSync(join(PUB, "index.html"), "utf8") : "";
const face = (index.match(/data-face="([\d.,\s]+)"/) || [])[1] || "";
const tint = (index.match(/--glass-tint:\s*([^;]+);/) || [])[1] || "rgba(14,24,44,.64)";

// 1. the frame, from the conformed flat cut (its colour is the reel's colour)
const C = join(P, "cover"); rmSync(C, { recursive: true, force: true }); mkdirSync(C, { recursive: true });
const src = join(PUB, "input-video.mp4");
if (!existsSync(src)) { console.error("no " + src); process.exit(1); }
let r = spawnSync("ffmpeg", ["-nostdin", "-y", "-v", "error", "-ss", String(AT), "-i", src, "-frames:v", "1", join(C, "frame.png")], { encoding: "utf8" });
if (r.status) { console.error(r.stderr); process.exit(1); }

// 2. the page
const fill = { FACE: face, TOP: String(top), RIM: tone, TONE: tone === "accent" ? "" : tone, EYEBROW: esc(eyebrow), TITLE: titleHtml, TINT: tint };
const tpl = readFileSync(join(SK, "template", "cover.html"), "utf8")
  .replace(/<!--[\s\S]*?-->/g, "")                                    // the template's notes name the placeholders too
  .replace(/__([A-Z]+)__/g, (all, k) => (k in fill ? fill[k] : all));
writeFileSync(join(C, "index.html"), tpl);
copyFileSync(join(SK, "template", "reel.css"), join(C, "reel.css"));
copyFileSync(join(kit, "node_modules", "gsap", "dist", "gsap.min.js"), join(C, "gsap.min.js"));

// 3. measure the card (Chrome via the kit's Playwright) and check it
const { chromium } = createRequire(join(kit, "package.json"))("playwright");
let browser;
try { browser = await chromium.launch({ channel: "chrome", headless: true }); } catch { browser = await chromium.launch({ headless: true }); }
const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
await page.goto(pathToFileURL(join(C, "index.html")).href, { waitUntil: "load" });
const m = await page.evaluate(() => {
  const b = document.querySelector("#card .lg").getBoundingClientRect();
  const head = document.querySelector("#card .head");
  const lh = parseFloat(getComputedStyle(head).lineHeight) || 86;
  return { x: b.left, y: b.top, r: b.right, b: b.bottom, lines: Math.round(head.getBoundingClientRect().height / lh) };
});
await browser.close();

let fails = 0, warns = 0;
const say = (lvl, area, msg) => { console.log(`${lvl.padEnd(4)} ${area.padEnd(6)} ${msg}`); if (lvl === "FAIL") fails++; if (lvl === "WARN") warns++; };
const box = `${Math.round(m.r - m.x)}x${Math.round(m.b - m.y)} at (${Math.round(m.x)},${Math.round(m.y)})`;
const inCrop = m.y >= 285 && m.b <= 1635 && m.x >= 60 && m.r <= 1020;
say(inCrop ? "ok" : "FAIL", "crops", `card ${box}${inCrop ? " inside the 4:5 feed and 3:4 grid crops" : ": outside y 285-1635 / x 60-1020, a crop cuts it"}`);
if (face) {
  const [fx, fy, fw, fh] = face.split(",").map(Number);
  const o = Math.max(0, Math.min(m.r, fx + fw - 8) - Math.max(m.x, fx + 8)) * Math.max(0, Math.min(m.b, fy + fh - 8) - Math.max(m.y, fy + 8));
  say(o ? "FAIL" : "ok", "face", o ? `the card covers ${Math.round(o)} px² of the face: a shorter title (one line), or a frame where the head sits lower; the card cannot move up past y 285 (the feed crop)` : "card clear of the face");
} else say("WARN", "face", "no data-face in public/index.html: face not checked");
const words = TITLE.replace(/[|*]/g, " ").split(/\s+/).filter(Boolean).length;
say(m.lines > 2 || words > 6 ? "WARN" : "ok", "copy", `${m.lines} line(s), ${words} words${m.lines > 2 || words > 6 ? ": a cover is read at thumbnail size, 2 lines / 6 words at most" : ""}`);

// 4. render through HyperFrames (bundled fonts), then the crop preview
const snap = join(C, "snap");
r = spawnSync(`npx hyperframes snapshot "${C}" --at 0.5 --no-end --describe false -o "${snap}"`, { shell: true, encoding: "utf8", cwd: kit });
const png = existsSync(snap) ? readdirSync(snap).filter(f => f.endsWith(".png")).sort()[0] : null;
if (r.status || !png) { console.error("snapshot failed:\n" + (r.stdout || "") + (r.stderr || "")); process.exit(1); }
mkdirSync(dirname(OUTP), { recursive: true });
copyFileSync(join(snap, png), OUTP);
const crops = OUTP.replace(/\.png$/i, "") + "-crops.png";
r = spawnSync("ffmpeg", ["-nostdin", "-y", "-v", "error", "-i", OUTP, "-filter_complex",
  "[0]scale=1080:1920,split=3[a][b][c];[a]scale=405:720[full];[b]crop=1080:1440:0:240,scale=540:720[grid];" +
  "[c]crop=1080:1350:0:285,scale=576:720[feed];[full][grid][feed]hstack=3", "-frames:v", "1", crops], { encoding: "utf8" });
if (r.status) { console.error(r.stderr); process.exit(1); }
console.log(`\n${fails ? fails + " FAIL" : "PASS"}${warns ? `, ${warns} WARN` : ""} -> ${OUTP}\nREAD ${crops} (full | 3:4 profile grid | 4:5 feed)`);
process.exit(fails ? 1 : 0);
