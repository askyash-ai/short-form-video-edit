#!/usr/bin/env node
// transcribe-local.mjs: free, offline word-level transcription with whisper.cpp (no ElevenLabs credits).
// Output: {"duration", "words": [{text, start, end}]}, the shape every cut and check script reads.
//
// Why not just `npx hyperframes transcribe --engine whisper`: it uses whisper.cpp's plain token timestamps, which put the
// first word ~2 s early when a take opens on silence (reel-1 IMG_9995: "Two" at 0.15 s, spoken at 2.25 s). This runs
// whisper-cli itself with DTW token alignment (`-dtw medium.en`; it only works with flash attention off, `-nfa`), then
// corrects against the audio:
//   1. DTW marks a token a little late (measured on reel-1's takes vs ElevenLabs and the waveform): every word start is
//      moved earlier by --shift (default from the measurement, see SHIFT below).
//   2. Speech regions come from ffmpeg silencedetect (-38 dB, 0.12 s). A word that starts inside a silence moves to the
//      silence's end (the real onset); a word's end is the next word's start, clipped to the start of any silence in
//      between, and the last word ends where speech ends.
//   3. The first word of each speech region starts exactly at the region's onset.
// Setup (once): whisper-cli.exe from the official whisper.cpp Windows release in ~/.cache/hyperframes/whisper/bin/Release/
// and ggml-medium.en.bin in ~/.cache/hyperframes/whisper/models/ (SKILL.md "Setup check"). Override with --whisper / --model.
//
// Usage: node transcribe-local.mjs --in <video or audio> --out transcript.json [--model medium.en] [--shift 0.15]
//        [--threads 8] [--raw raw.json] [--prompt "ChatGPT, Gemini, Claude"] [--prompt-file W/assets/script.md]
// The prompt (vocabulary or the script) is what keeps names right: without it medium.en heard reel-1's "fake ChatGPT" as
// "fake GPT". Pass the reel's script (or at least its product and tool names) every time.
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync, existsSync, rmSync } from "node:fs";
import { join } from "node:path";
import { homedir, tmpdir } from "node:os";

const a = process.argv.slice(2), get = (k, d) => { const i = a.indexOf(k); return i >= 0 ? a[i + 1] : d; };
const IN = get("--in"), OUT = get("--out");
if (!IN || !OUT) { console.error("usage: node transcribe-local.mjs --in media --out transcript.json [--model medium.en] [--shift s]"); process.exit(2); }
const model = get("--model", "medium.en");
const WHISPER = get("--whisper", process.env.HYPERFRAMES_WHISPER_PATH || join(homedir(), ".cache", "hyperframes", "whisper", "bin", "Release", "whisper-cli.exe"));
const MODEL = get("--model-path", join(homedir(), ".cache", "hyperframes", "whisper", "models", `ggml-${model}.bin`));
// SHIFT: DTW's lateness, measured on reel-1 (2026-10-08). Overridable per call; re-measure with --raw if it drifts.
const SHIFT = +get("--shift", 0.15), THREADS = get("--threads", "8");
let PROMPT = get("--prompt", "");
// --prompt-file: a SHORT vocabulary list pulled from the script (names, product words, acronyms, anything with a digit or an
// inner capital). Never the whole script: given reel-1's full script as a prompt, medium.en hallucinated "07" and stopped.
if (get("--prompt-file")) {
  const txt = readFileSync(get("--prompt-file"), "utf8");
  const vocab = new Set();
  for (const sent of txt.split(/[.!?\n|]+/)) {
    const ws = sent.trim().split(/[\s,;:()"“”—–]+/).map(w => w.replace(/^[^A-Za-z0-9]+|[^A-Za-z0-9]+$/g, "")).filter(Boolean);
    ws.forEach((w, i) => {
      const special = (/\d/.test(w) && /[A-Za-z]/.test(w)) || /[a-z][A-Z]/.test(w) || (/^[A-Z]{2,}$/.test(w) && w.length <= 6);
      const proper = i > 0 && /^[A-Z][a-z]{2,}$/.test(w);
      if (special || proper) vocab.add(w);
    });
  }
  // then the script's longer, less common words (reel-1: "padlock" came out "pad log" without it), longest first
  const COMMON = new Set("about after again because before between browser change checking every friend google login moves offered people really record search searching should something someone things through window".split(" "));
  const longw = [...new Set(txt.toLowerCase().match(/\b[a-z][a-z-]{5,}\b/g) || [])].filter(w => !COMMON.has(w) && ![...vocab].some(v => v.toLowerCase() === w))
    .sort((p, q) => q.length - p.length);
  let list = [...vocab];
  for (const w of longw) { if ((list.join(", ") + ", " + w).length > 230) break; list.push(w); }
  PROMPT = [PROMPT, list.join(", ")].filter(Boolean).join(", ");
}
PROMPT = PROMPT.slice(0, 240);   // a vocabulary hint, not a passage
for (const [what, p] of [["whisper-cli", WHISPER], ["model", MODEL]]) if (!existsSync(p)) { console.error(`missing ${what}: ${p} (see SKILL.md setup)`); process.exit(2); }

const tmp = mkdtempSync(join(tmpdir(), "tlocal-"));
const wav = join(tmp, "a.wav");
let r = spawnSync("ffmpeg", ["-nostdin", "-y", "-v", "error", "-i", IN, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav], { encoding: "utf8" });
if (r.status) { console.error("ffmpeg could not read " + IN + "\n" + r.stderr); process.exit(1); }
const duration = +spawnSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", wav], { encoding: "utf8" }).stdout.trim();

// 1. whisper.cpp with DTW token alignment
r = spawnSync(WHISPER, ["-m", MODEL, "-f", wav, "-l", "en", "-dtw", model, "-nfa", "-ojf", "-of", join(tmp, "w"), "-t", THREADS, "-np", ...(PROMPT ? ["--prompt", PROMPT] : [])], { encoding: "utf8" });
if (r.status) { console.error("whisper-cli failed:\n" + (r.stderr || r.stdout).slice(-800)); process.exit(1); }
const j = JSON.parse(readFileSync(join(tmp, "w.json"), "utf8"));
const toks = j.transcription.flatMap(s => s.tokens).filter(t => !/^\[.*\]$|^<\|.*\|>$/.test(t.text.trim()) && t.text.trim() !== "");
const bad = toks.filter(t => !(t.t_dtw >= 0)).length;
if (bad === toks.length) { console.error("DTW timestamps missing (is -nfa supported by this whisper-cli?)"); process.exit(1); }
// a few tokens without a DTW time (seen with long prompts): fill from the neighbours
toks.forEach((t, i) => {
  if (t.t_dtw >= 0) return;
  const prev = toks.slice(0, i).reverse().find(x => x.t_dtw >= 0), next = toks.slice(i + 1).find(x => x.t_dtw >= 0);
  t.t_dtw = prev && next ? (prev.t_dtw + next.t_dtw) / 2 : (prev || next).t_dtw;
});
if (bad) console.error(`note: ${bad} token(s) had no DTW time, filled from neighbours`);
if (get("--raw")) writeFileSync(get("--raw"), JSON.stringify(toks.map(t => ({ text: t.text, t: t.t_dtw / 100 })), null, 1));
// tokens -> words: a token starting with a space starts a new word; punctuation and sub-word pieces join the previous one
const words = [];
for (const t of toks) {
  const txt = t.text, at = t.t_dtw / 100;
  if (!words.length || /^\s/.test(txt) && /[A-Za-z0-9$£€]/.test(txt)) words.push({ text: txt.trim(), start: at });
  else words[words.length - 1].text += txt.trim();
}

// 2. speech regions from the audio
const sd = spawnSync("ffmpeg", ["-nostdin", "-v", "info", "-i", wav, "-af", "silencedetect=noise=-38dB:d=0.12", "-f", "null", "-"], { encoding: "utf8" }).stderr;
const sil = [];   // [start, end] of each silence
let open = null;
for (const m of sd.matchAll(/silence_(start|end): ([\d.]+)/g)) {
  if (m[1] === "start") open = +m[2]; else { sil.push([open ?? 0, +m[2]]); open = null; }
}
if (open != null) sil.push([open, duration]);
const inSilence = t => sil.find(([s, e]) => t >= s && t < e);

// 3. correct: shift, push out of silences, first word of a region = its onset, ends from the next start / silences
for (const w of words) w.start = Math.max(0, w.start - SHIFT);
// a word that lands inside a silence belongs to the nearer side: the tail of the speech before it (reel-1 IMG_9988:
// "them" spoken at 3.74 s, DTW put it 0.0x s into the following 1 s pause; pushing it to the pause's end made it 1.1 s
// late) or the onset after it
words.forEach((w, i) => {
  const s = inSilence(w.start); if (!s) return;
  if (w.start - s[0] < s[1] - w.start && s[0] > 0) w.start = Math.max(i ? words[i - 1].start + 0.06 : 0, s[0] - 0.14);
  else w.start = s[1];
});
for (const [, e] of sil) {                      // the first word after each silence starts at the onset
  const first = words.find(w => w.start >= e - 0.25);
  if (first && first.start - e < 0.6) first.start = e;
}
for (let i = 1; i < words.length; i++) if (words[i].start < words[i - 1].start + 0.04) words[i].start = words[i - 1].start + 0.04;
words.forEach((w, i) => {
  const next = i + 1 < words.length ? words[i + 1].start : duration;
  const gap = sil.find(([s, e]) => s > w.start && s < next);   // a silence before the next word ends this one
  w.end = gap ? gap[0] : next;
  if (i === words.length - 1) { const tail = sil.find(([s]) => s > w.start); w.end = tail ? tail[0] : duration; }
  w.end = Math.max(w.end, w.start + 0.06);
});
const out = { duration: +duration.toFixed(3), engine: `whisper.cpp ${model} + DTW, shift ${SHIFT}, audio-snapped`,
  words: words.map(w => ({ text: w.text, start: +w.start.toFixed(3), end: +w.end.toFixed(3) })) };
writeFileSync(OUT, JSON.stringify(out, null, 1));
rmSync(tmp, { recursive: true, force: true });
console.log(`${PROMPT ? "prompt: " + PROMPT + "\n" : ""}${out.words.length} words -> ${OUT} (${out.engine}):${out.words.map(w => w.text).join(" ").slice(0, 120)}`);
