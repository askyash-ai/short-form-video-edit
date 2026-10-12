# aotw-01 v4: the approved baseline (2026-10-11)

**Approved 2026-10-11** ("This version is good"). Automation of the week #1, Hook A: "I didn't edit a single frame of
this reel. Claude did." CTA: "Drop me a follow, comment SKILL" → the skill. 31.56 s, 4K60 (iPhone 16 Pro, HDR off),
10 takes picked from 42. The render: `hyperframes-student-kit/video-projects/aotw-01-ops-sop/renders/aotw-01-A-v4.mp4`.

`index.html` here is pixel-identical to that render's composition with the skill's `template/reel.css` + `reel.js`
(PSNR inf at 7 beats, 2026-10-11). Assets it expects in `public/img/`: `claude-logo.png` (not shipped: add your own, see README.md), `qc-frame.jpg`
(a 360x640 frame of the reel), `takes/IMG_*.jpg` (240x320 face crops of real takes). Also here: `picks.tsv` (the take
picks, `take-cut.py`'s input), `plan.json` (its output), `joins.json` (the 9 hard joins as found in the picture) and
`retime.py` (re-times every beat from anchor words after a re-cut; see "Re-timing" below).

## How it got here (what the skill now does by default)

| Version | Note from the creator | Fix, now the default |
|---|---|---|
| v1 | (the "0:31" payoff on screen 0.4 s) | `hold-check.mjs` before every render |
| v2 | thumbnail expression disliked | `cover-frames.py`: a numbered sheet of candidates at word ends, the creator picks |
| v2 | "A lot of zoom in and joins are not very smooth" | `take-cut.py`: dissolves inside a take, hard cuts only between takes; reframe 1.00 ↔ 1.08 at take joins only; eased pushes |
| v2 | "It can't be reduced from 4:19 to 31 secs" | numbers measure the claim they sit under: picked takes as recorded (1:01) → reel (0:31), not every take |
| v2 | Claude logo graphics wanted (a reference reel's "Raw in. Edit out.") | R19 chat window + R20 app-tile pipeline, Claude tile on the cover (`cover-logo.py`) |
| v3 | (three payoffs 0.3-0.4 s again) | the generator holds every card until its payoff has had its time |
| v4 | "This version is good" | this reference |
| after | "step 1, step 2 and step 3 ... feels a little aggressive" | script rules: say steps like a coworker; `script-check` WARNs on counted steps |

## Beat sheet (flat-cut time)

| Time | Size | What | On the word |
|---|---|---|---|
| 0.10-3.55 | M + S | series tag · `Edits by me [0]` → `✳ Edits by Claude [ALL]` (spark = the Claude logo) | "frame", "Claude did" |
| 3.60-4.48 | S | ✗ `Not an editor` | "editor" |
| 4.50-5.83 | M | R20: `SKILL.md · 601-LINE SOP` → wire → Claude tile; eased push 1.08 → 1.11 | "wrote", "Claude", "SOP" |
| 5.96-9.36 | L | R19: Claude chat window, `/short-form-video-edit` types, 12 real takes drop in as attachments, "42 clips" counts, amber `retake` / red `flub` tags, send presses | "drop in", "every retake", "every mess-up" |
| 9.50-13.10 | M | R20: `10 of 42 takes · 1:01 RAW` → Claude tile → `0:31 REEL` | "picks", "best", "line", "cuts" |
| 12.64-13.62 | S | `3` chip beside the head | "Step three" |
| 13.68-17.16 | M | `Built by Claude / Captions + these cards / timed to the exact word` | "captions", "these", "exact" |
| 17.28-19.81 | M | `Quality gates`, eased push 1.08 → 1.11 | "quality" |
| 19.94-23.54 | L | a frame of this reel in a phone: Instagram UI zones red, face boxed teal, `✓ Face clear`, `✓ Buttons clear` | "every frame", "face", "Instagram" |
| 23.68-25.66 | M | R7: ✓ `Every frame checked` · ✗ `Can't hear the audio` | "tells", "what" |
| 25.70-27.82 | S | `Send to a friend` | "friend" |
| 28.30-31.56 | S + M | `+ Follow` → `Following ✓` · R15 `Comment [SKILL]` | "follow", "comment" |

## The numbers

- **Cut:** 10 takes, 9 hard joins (take boundaries, found at 3.117 5.850 9.367 12.500 17.183 19.833 23.567 25.133
  27.867 s), 10 dissolves of 0.08 s inside takes (pauses over 0.30 s / 0.25 s after a sentence, 0.10 s kept each side).
  find-joins also flagged 2 dissolves over a big head move (scores 4.3x and 8.9x against 18-38x): not jump cuts.
- **Camera:** 1.00 / 1.08 alternating per take (camSet at each hard join + 0.003); eased pushes +0.03 over 0.7 s
  (`sine.inOut`) on "SOP" and "quality"; nothing under the L panels.
- **Face visible ~78%** (the two L panels, 3.4 s and 3.6 s). Higher than reel-1's 56%: the face is the proof here.
- **Skin:** recorded 56.6-66.2% (head angle to a window) → target 63.4 (median 61.4 + 2) → conformed 63.0-63.5 →
  render median 61.4 at the sampled frames (WARN at 16.0 s: 60.9, a turned head), saturation -1.9.
- **Audio:** room rumble 40-80 Hz at -55 dBFS raw; polished with `--hpf 120 --eq "highpass=f=120:poles=2,agate=..."`
  (see SKILL.md "Sound"): takes -20.0 LUFS, floors -66.1 to -68.8, spread 2.7 dB. Master -14.0 LUFS / -1.4 dBTP; the
  master floor gate reads -44.4 (a FAIL that is the metric, not the room: no silence left in a tight cut).
- **Glass tint:** navy hoodie rgb(45,58,76) → `rgba(22,32,50,.64)`. Captions band-top 1360 (the beard reaches y ~1385).
- **Face box** 130,570,570,815; skin patch 380,825,200,50.
- **Gates:** hyperframes check 0 errors, 39/39 contrast; beat-check 13/13; layout-check PASS (WARN only TikTok/Shorts:
  L panels to x 950); reel-check PASS; colour PASS; verify-render PASS (49.6 Mb/s, 31.567 s, A/V in sync, 0 black frames).
- **hold-check (written after v4) on this composition:** 7 FAIL at the 0.7 s first draft, which set the calibration:
  "ALL" 0.57 s and the SOP tile 0.60 s passed the creator's eye; "Quality gates" 0.30 s, "Buttons clear" 0.42 s and the
  red flub tags 0.02-0.12 s are too short. At the calibrated defaults (FAIL < 0.5, WARN < 0.8) those last three FAIL:
  fix them in the next reel (pop on an earlier word, or hold the card).
- **Time spent:** ~4.5 h of wall clock, mostly avoidable: two app freezes, conforming and measuring all 42 takes, the
  audio retry, three re-renders for short payoffs and one re-cut for smoothness. The fast path in SKILL.md is the fix.

## Re-timing after a re-cut

`retime.py W` rebuilds `public/index.html` from a saved copy of the markup (`cuts3/index-v2.html` in this project) and
the new transcript: every card's start and end and every tween are found by anchor words (`ws("phrase", after)`), the
reframes by `cuts/plan.json` matched to `joins.json`. Use it as the pattern when a cut changes after the build: never
re-type times by hand. Better still, settle the cut before Stage 5 (take-cut.py's defaults are the approved cut).
