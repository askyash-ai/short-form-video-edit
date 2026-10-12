#!/usr/bin/env node
// captions.mjs: transcript.json -> burned-in caption groups, written into the reel's index.html between the
// CAPTIONS:START / CAPTIONS:END markers (one HTML block, one JS block). Re-running replaces both, so a retime is free.
//
// Groups: 1-3 words (--max-words), at most --max-chars characters, broken at punctuation and at any pause over
// --gap s. A group shows from its first word (minus --lead) until the next group starts (or its last word + 0.25 s),
// so the band is never empty mid-sentence and never shows two groups. Trailing . and , are dropped; ? and ! stay.
// Words in --em get the accent colour; any token with a digit is set in mono (numbers read as data); the CTA
// keyword (--keyword) becomes a solid accent chip. By default the word being spoken lights up teal (the active word)
// and goes back to white on the next word: the eye follows the voice. --no-active turns that off; --karaoke instead
// dims each group's words until they are spoken.
// --band-top moves the caption band (default 1320 px in reel.css; measure the chin on a frame and sit ~30 px under it).
//
// Usage: node captions.mjs --transcript W/transcript.json --index W/public/index.html
//        [--max-words 3] [--max-chars 22] [--gap 0.35] [--lead 0.04] [--em "ChatGPT,two tests"] [--keyword SAFE]
//        [--no-active] [--karaoke] [--band-top 1320] [--from 0] [--to <duration>]
import { readFileSync, writeFileSync } from "node:fs";

const a = process.argv.slice(2);
const get = (k, d) => { const i = a.indexOf(k); return i >= 0 ? a[i + 1] : d; };
const has = k => a.includes(k);
const T = get("--transcript"), IDX = get("--index");
if (!T || !IDX) { console.error("usage: node captions.mjs --transcript transcript.json --index public/index.html [...]"); process.exit(2); }
const maxWords = +get("--max-words", 3), maxChars = +get("--max-chars", 22), gap = +get("--gap", 0.35), lead = +get("--lead", 0.04);
const from = +get("--from", 0), to = +get("--to", Infinity), bandTop = get("--band-top");
const norm = s => s.toLowerCase().replace(/[^a-z0-9']+/g, " ").trim();
const em = (get("--em", "") || "").split(",").map(norm).filter(Boolean);
const keyword = norm(get("--keyword", ""));
const karaoke = has("--karaoke"), active = !has("--no-active");

const raw = JSON.parse(readFileSync(T, "utf8"));
const words = (Array.isArray(raw) ? raw : raw.words).filter(w => !w.type || w.type === "word")
  .map(w => ({ text: String(w.text).trim(), start: +w.start, end: +w.end }))
  .filter(w => w.text && w.start >= from && w.start < to);
if (!words.length) { console.error("no words in range"); process.exit(1); }

// mark emphasis spans (single words or phrases) on the word list
const flags = words.map(() => "");
const toks = words.map(w => norm(w.text));
for (const phrase of em) {
  const p = phrase.split(" ");
  for (let i = 0; i + p.length <= toks.length; i++)
    if (p.every((t, k) => toks[i + k] === t)) for (let k = 0; k < p.length; k++) flags[i + k] = "em";
}
toks.forEach((t, i) => { if (keyword && t === keyword) flags[i] = "kw"; });

const groups = [];
let cur = [];
const flush = () => { if (cur.length) groups.push(cur); cur = []; };
words.forEach((w, i) => {
  const chars = cur.reduce((n, j) => n + words[j].text.length + 1, 0) + w.text.length;
  const prev = cur.length ? words[cur[cur.length - 1]] : null;
  if (cur.length && (cur.length >= maxWords || chars > maxChars || (prev && w.start - prev.end > gap) || /[.?!,:;]$/.test(prev.text)))
    flush();
  if (flags[i] === "kw") { flush(); cur.push(i); flush(); return; }   // the keyword stands alone
  cur.push(i);
});
flush();

const esc = s => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const clean = s => s.replace(/[.,;:]+$/, "").replace(/^["“]|["”]$/g, "");
const r2 = x => Math.round(x * 100) / 100;
let html = "", js = "";
groups.forEach((g, n) => {
  const t0 = Math.max(0, r2(words[g[0]].start - lead));
  const nextIn = n + 1 < groups.length ? Math.max(0, r2(words[groups[n + 1][0]].start - lead)) : Infinity;
  const t1 = Math.min(nextIn, r2(words[g[g.length - 1]].end + 0.25));
  const dur = r2(Math.min(Math.max(0.3, t1 - t0), nextIn - t0));   // the 0.3 s floor never runs into the next group
  const spans = g.map((j, k) => {
    const txt = flags[j] === "kw" ? clean(words[j].text).toUpperCase() : clean(words[j].text);
    const cls = ["w", flags[j], /\d/.test(txt) ? "num" : ""].filter(Boolean).join(" ");
    return `<span class="${cls}" id="cw-${n}-${k}">${esc(txt)}${k < g.length - 1 ? " " : ""}</span>`;
  }).join("");
  html += `  <div id="cg-${n}" class="cg clip" data-start="${t0}" data-duration="${dur}" data-track-index="20"><div class="cg-inner">${spans}</div></div>\n`;
  js += `tl.fromTo('#cg-${n} .cg-inner',{opacity:0,y:14},{opacity:1,y:0,duration:0.16,ease:'power2.out'},${t0});\n`;
  if (karaoke) g.forEach((j, k) => {
    if (k) js += `tl.fromTo('#cw-${n}-${k}',{opacity:0.45},{opacity:1,duration:0.08},${r2(words[j].start)});\n`;
  });
  if (active) g.forEach((j, k) => {
    if (flags[j]) return;                                  // accent and keyword words keep their own colour
    const on = r2(words[j].start), off = r2(k + 1 < g.length ? words[g[k + 1]].start : t0 + dur);
    if (off - on < 0.06) return;
    js += `tl.fromTo('#cw-${n}-${k}',{color:'#ffffff'},{color:'#5eead4',duration:0.05},${on});` +
          `tl.to('#cw-${n}-${k}',{color:'#ffffff',duration:0.08},${off});\n`;
  });
});

let src = readFileSync(IDX, "utf8");
const swap = (s, open, close, body) => {
  const i = s.indexOf(open), j = s.indexOf(close);
  if (i < 0 || j < i) { console.error(`markers ${open} / ${close} not found in ${IDX}`); process.exit(1); }
  return s.slice(0, i + open.length) + "\n" + body + s.slice(j);
};
src = swap(src, "<!-- CAPTIONS:START -->", "<!-- CAPTIONS:END -->", html);
src = swap(src, "/* CAPTIONS:START */", "/* CAPTIONS:END */", js);
if (bandTop) src = src.replace(/<div id="captions"[^>]*>/, `<div id="captions" style="top:${parseInt(bandTop)}px">`);
writeFileSync(IDX, src);
const longest = Math.max(...groups.map(g => g.map(j => words[j].text).join(" ").length));
console.log(`${groups.length} caption groups from ${words.length} words -> ${IDX} (longest ${longest} chars` +
  `${em.length ? `, ${flags.filter(f => f === "em").length} accent words` : ""}${keyword ? `, keyword ${flags.includes("kw") ? "found" : "NOT SPOKEN"}` : ""})`);
