#!/usr/bin/env node
// transcript-normalize.mjs: any word-level transcript -> {"duration", "words": [{text, start, end}]}, the shape every
// cut and check script reads.
//
// ElevenLabs Scribe (the kit's `npm run transcribe`) interleaves {"type":"spacing"} entries and, with
// --tag-audio-events, {"type":"audio_event"} ones: paper-cut.py would read a " " as a word and a "(laughs)" as speech.
// HyperFrames/whisper output is already a word array or {words}. Both come out the same here.
//
// Usage: node transcript-normalize.mjs --in raw.json --out transcript.json [--offset 0] [--duration 44.68]
import { readFileSync, writeFileSync } from "node:fs";

const a = process.argv.slice(2), get = (k, d) => { const i = a.indexOf(k); return i >= 0 ? a[i + 1] : d; };
const inp = get("--in"), out = get("--out"), off = Number(get("--offset", 0));
if (!inp || !out) { console.error("usage: node transcript-normalize.mjs --in raw.json --out transcript.json [--offset s]"); process.exit(2); }
const raw = JSON.parse(readFileSync(inp, "utf8"));
const list = Array.isArray(raw) ? raw : raw.words || raw.segments?.flatMap(s => s.words || []) || [];
const words = list
  .filter(w => (w.type ? w.type === "word" : true))
  .map(w => ({ text: String(w.text ?? w.word ?? "").trim(), start: Number(w.start), end: Number(w.end) }))
  .filter(w => w.text && Number.isFinite(w.start) && Number.isFinite(w.end))
  .map(w => ({ text: w.text, start: +(w.start + off).toFixed(3), end: +(w.end + off).toFixed(3) }));
const duration = Number(get("--duration", raw.duration ?? (words.length ? words[words.length - 1].end : 0)));
writeFileSync(out, JSON.stringify({ duration, words }, null, 1));
console.log(`${words.length} words -> ${out} (${list.length - words.length} non-word entries dropped)`);
