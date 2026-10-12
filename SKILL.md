---
name: short-form-video-edit
description: Edit a short vertical video (Instagram Reel, TikTok, YouTube Short) end to end from raw phone takes. Before the shoot it checks the script and a test clip (framing, light, room noise); then takes raw iPhone takes (4K60 or HD30; one per script line, retakes and all) or one continuous take plus screen recordings; keeps the phone's own colour with the skin a little lighter (uniform, never washed out), cleans and levels the voice, picks the best take per line, cuts to short-form pace with smooth joins, adds active-word captions, liquid-glass overlays sized to their content, tool graphics (a chat window, app-tile pipelines), real news-article screenshots with the spoken words highlighted, optional AI B-roll, eased pushes and a "Comment WORD" CTA, renders at the source's own resolution and frame rate with HyperFrames, makes the cover, and gates colour, skin, audio, layout (every frame, per platform), pacing, captions, CTA and privacy. Use for "edit this reel", "edit this short", "cut this video", "make a reel from these takes", "add captions", or a raw .MOV to turn into a short-form video. For 16:9 long-form use a long-form editing skill instead.
---

# Short-form video editor

Turns raw iPhone takes into a finished 9:16 reel: the pre-shoot checks, take selection, the voice polish, the cut,
captions, liquid-glass overlays, real article screenshots, B-roll, camera moves, the CTA, the cover and an **MP4 at the
iPhone source's own quality: 4K60 (2160x3840 @ 60, the default) or HD30 (1080x1920 @ 30)** (see "Source profiles").
Everything renders locally through HyperFrames (Chrome + FFmpeg); only the audio goes to ElevenLabs for transcription,
and only approved AI B-roll prompts go to an image/video service.

**Where this came from.** The cut stage, the checkpoints, the beat-sync gate, "silence unless something makes a sound",
"never assume, snapshot", the AI B-roll chain and "save this to the skill" follow the workflow of WeAreNoCode's
`youtube-edit` skill (the method; the scripts here are this skill's own), and two scripts come from Nate Herk's MIT
HyperFrames student kit (see `LICENSES/` and `NOTICE.md`). The look, formats,
sizes, length, captions, colour and funnel were rewritten for short-form. `STYLE-GUIDE.md` sums up the look and
`CHANNEL.md` your channel's rules; for the look, the style guide wins. First time here: `README.md`.

**This skill keeps learning.** When a note is worth keeping, the user says **"save this to the skill"** and Claude writes
it as one plain rule in the right section below (replacing any rule it contradicts).

```bash
SK="$HOME/.claude/skills/short-form-video-edit"
KIT="$HF_KIT"                  # the hyperframes-student-kit clone (README.md): HyperFrames, gsap, Playwright, the transcriber, .env
W="$KIT/video-projects/<slug>" # one folder per video, e.g. tips-03-excel-pivot
PY=python                                                        # Windows; python3 on Mac/Linux
```

Run `npx hyperframes ...` from `$KIT` (it pins HyperFrames 0.7.x). Quote every path (a space in a folder name breaks it).
If `HF_KIT` is not set, ask the user where they cloned the kit and use that; the Node checks also take `--kit <dir>`.

## The approved baselines (start here)

**aotw-01 v4** (2026-10-11, "This version is good") is the current baseline for **the cut, the camera, the timing and
the tool graphics**: `$SK/reference/aotw-01-v4/` (`index.html` pixel-identical to the approved render with
`template/reel.css` + `reel.js`; `NOTES.md` with the beat sheet, numbers, gates and what each version fixed).
**reel-1 v3** (2026-10-07, "This video output was great") stays the reference for **the news arc and its formats** (R16
article, R13 explainer, R14 demo, R7/R5/R6): `$SK/reference/reel-1-v3/`. Read both NOTES.md before planning a reel; depart
from them only when the content needs it or the user asks. reel-1's colour is superseded (on 2026-10-11 the creator
judged it "over bright and saturated": the HLG conversion, see "Colour and skin"); the target is "C + colour kept". The
defaults they set:

- **The arc:** hook card (M, the promise + a payoff word that pops) → the proof (R16 article for news; R19 the tool's chat
  window or R10 the real build for an "Automation of the week") → the mechanism (R13 explainer, R20 pipeline) → what to do
  (R14 demo, R7 checklist, R5 pills, an R6 number chip) → a share line (S pill) → the CTA (M, one row). A "Can AI do my
  job?" swaps the source for the task and ends the middle on R12.
- **Face visible 55-80%** (reel-1 56%, aotw-01 78%: when the face is the proof, keep it up), three L panels at most,
  each with `dim()`; S/M above or beside the head, never on the face.
- **A visual change every ≤3 s**, counting motion inside panels; the promise on screen by 0.1-0.3 s.
- **Smooth cut** (aotw-01, the creator: "a lot of zoom in and joins are not very smooth"): `take-cut.py` dissolves the
  pauses it trims inside a take (0.08 s); only the joins between takes are hard cuts.
- **Calm camera:** a reframe 1.00 ↔ 1.08 at the hard joins only; eased pushes (+0.03 over 0.7 s); no snaps, no zoom-out
  mid-line (see "Camera").
- **Every payoff readable:** `hold-check.mjs` PASS (no payoff on screen under 0.5 s before its card closes).
- **Numbers measure the claim they sit under** (aotw-01: "It can't be reduced from 4:19 to 31 secs"): the picked takes as
  recorded (1:01) → the reel (0:31), never every take ever recorded.
- **Colour target: "C + colour kept"** (2026-10-11, PROVISIONAL: tune it on the next reel with the creator, then write
  the final numbers here). The picture as the iPhone shows it, a little lighter: skin = the takes' recorded median + 2,
  **never under 63%**, every take within ±0.5; **the skin's recorded saturation kept** (restored after the lift, never
  boosted past it); no grade boost. Shot with **HDR Video off** (SDR), so "recorded" is exactly what the phone shows.
- **Glass** = smoked, tinted from the footage's dominant tone at alpha ~.64; light-tint text colours on glass.
- **Captions** active-word teal, 1-3 words, 1320-1500 band; the spoken keyword as a solid chip.
- **Output = the source:** 4K60 takes give a 2160x3840 @ 60 reel (the default since 2026-10-07: "make it 4K60 and set that
  as default"); HD30 takes give 1080x1920 @ 30 (allowed since 2026-10-11). The composition is always laid out in
  1080x1920 CSS px with `data-fps` = the source's rate; a 4K render doubles it.
- **Gates all green** before delivery: check 0 errors, beat-check, **hold-check**, layout-check (every frame), reel-check
  (incl. joins), colour + skin, the audio gates (takes; the master's floor reading, see "Sound"), verify-render (and its
  dense + transition sheets read), the cover check.

## The fast path: one pass, about an hour (read this before every edit)

aotw-01 took ~4.5 h of wall clock for a 31 s reel. Almost all of it was avoidable: the app froze twice, all 42 takes were
measured and conformed when 10 were used, the audio needed a second pass, three renders were redone for payoffs on screen
too briefly, and the cut was redone once for smoothness. Done in this order, with these defaults, the same reel is about
an hour of machine time and two short checkpoints:

| # | Step | Command / rule | Time (4K60, 8 GB PC) |
|---|---|---|---|
| 1 | probe + transcribe the **raw** takes | ffprobe one take; ElevenLabs on every raw `.MOV`, 6 at a time (it extracts the audio itself) | ~2 min for 42 takes |
| 2 | `TAKES.md`, **Checkpoint A** | the last clean take per line; flag gaps (a missing phrase, a misheard keyword) | you |
| 3 | skin: grid + patch on one take, `skin-match.mjs` on the **picked takes only**, `--preview`, the creator picks | Stage 1 | ~3 min |
| 4 | conform the picked takes, then `audio-polish.py apply` + `check` (rumble fix ready, see "Sound") | one detached job | ~1.5 min per 7 s take |
| 5 | `take-cut.py` (smooth cut) → transcribe the flat cut → `find-joins.py` | one detached job | ~6 min |
| 6 | build: copy the approved reference's components, anchor every beat to its words, captions | Stage 5 | ~15 min |
| 7 | `hyperframes check`, beat-check, **hold-check**, layout-check, reel-check, snap-reel → **Checkpoint B** | read `snaps/sheet.png` | ~4 min |
| 8 | render → master → colour → verify, then `cover-frames.py` → the creator picks → `make-cover` (+ `cover-logo.py`) | one detached job; nothing else runs during the render | ~16 min |

**Run every heavy job detached** (`scripts/bg-job.ps1`, a job `.sh` that logs and ends with `ALLDONE`, watched with a
Monitor `tail -f | grep`). A 4K decode or encode in the foreground froze the Claude app twice on an 8 GB PC, and a
render stalled at 98% when frames were grabbed alongside it. **One heavy job at a time.** **Ask at checkpoints in plain
text**, not a pop-up question (one froze the app). Read the dense sheets and fix everything you see in one pass before
re-rendering: each render is ~13 min.

## Your channel (read before planning anything)

Read `$SK/CHANNEL.md` first: the channel's niche, audience, tone, series and any extra rules. If it is still the
template, ask the user for those five things once and write them into it. The rules below are the defaults; CHANNEL.md
may tighten them, and a request that would break one is stopped and asked about.

**Default hard rules: never break these, and stop and ask if a request would.**
1. **Dummy data only.** No real company, employer, customer, supplier, price, order/material number, internal document
   or real business-system screen, on screen, in captions or in a file in `public/`. One fictional company, reused across
   videos. `reel-check.mjs` blocks every term in `$SK/private/denylist.txt` (fill it in: one term per line).
2. **The employer is never named or shown.** Watch reflections, badges, lanyards, Teams/Outlook names, browser tabs and
   taskbars in screen recordings. Blur (`broll-conform.py --vf`) or ask.
3. **The presenter is always the real you, with your real voice:** no AI avatar standing in for you, no voice clone.
   AI B-roll is allowed through its route below: it shows a scene, never stands in for you talking, is never proof, and
   is **always labelled with the platform's AI label** when posted.
4. **One keyword CTA per video:** "Comment WORD", mapped to exactly one lead magnet, delivered by an auto-DM tool
   (ManyChat or similar). Never "link in bio", "DM me" or any cold outreach.
5. **30 to 60 seconds, never over 90.** A visual change every 2 to 4 s. Captions always burned in, mid-frame.
6. Recordings come from a personal computer only; never a work laptop or a screen with work accounts open.

**Series** (from CHANNEL.md; each video stands alone; number them). The shapes that work:

| Shape | Example series name | How it runs |
|---|---|---|
| results-first tip | "Things your boss doesn't know AI can do, #N" | open on the finished result, show the 2-3 steps, a social payoff ("send this to the coworker who still does this by hand") |
| verdict test | "Can AI do my job? Task #N" | a real task on dummy data, AI attempts it, a **Pass / Fail / Half** verdict stamp |
| build of the week | "Automation of the week #N" | one build, results first, the free template behind the keyword |

A topical one-off (news, a security alert) uses a plain tag ("AI AT WORK · SECURITY") instead of a series number.

## Stage 0: before the shoot (Checkpoint 0)

Most of a reel's quality is decided before the camera rolls. Four steps, then the user records.

**1. The brief.** Ask for or infer, then write `$W/BRIEF.md` (5 lines): series + number (or one-off), lane, the hook line,
the payoff, the CTA keyword and its lead magnet, **whether the demo data is already dummy**, and **the news source** if the
reel is about a story (the article URL: it becomes an R16 overlay). The script goes to `$W/assets/script.md` (the kit's
table: `| Clip | Line | Delivery note |`, one line = one take).

**2. The script review.** `$PY "$SK/scripts/script-check.py" --script "$W/assets/script.md" --keyword <WORD>` (length at
the creator's 2.66 words/s, hook length, lines too long for one take, numbers, the keyword in the last two lines and its
sound-alikes, counted steps), then write `$W/SCRIPT-REVIEW.md`: does line 1 make the promise in ≤12 words; the one open
loop and the line that pays it off; anything said that the screen should show instead; **3 alternative hooks** (results
first, a number, a contrarian line), each as a **full script** (only the lines around the hook change); suggested line
edits. The user approves or edits the script.

**Write it the way the creator talks** (2026-10-11, after aotw-01: "it needs to be more human. In this reel step 1,
step 2 and step 3, the way I am speaking feels a little aggressive"). The hook may be punchy; the body is a coworker
explaining something over their shoulder:
- **Never count steps out loud** ("Step one... Step two... Step three..."): it turns the creator into a lecturer.
  Use the connectors people actually say: "First I just...", "then it...", "and the bit I like is...", "so...". The
  screen can still number the steps (a chip, an eyebrow).
- Contractions, short everyday words, one small personal moment ("honestly", "the first time I tried it..."), and at
  most one line in a row that starts with an instruction. Questions work: "Why does that matter?".
- **Delivery notes** say relaxed and warm ("like you're telling a friend", "smile on...", "a little slower here"),
  not "brisk"; mark the one or two lines that carry energy (the hook, the payoff) and let the rest breathe.
- `script-check.py` WARNs on counted steps; fix them before the shoot (a recorded "Step one" cannot be edited out).
- Keep every claim recordable as said: numbers the creator will really have (aotw-01's Hook B said "15 messy takes"
  for 42), and phrasing that does not depend on a line they may drop on the day ("Here's the ops part" lost its setup
  when "I work in ops" was not said, and was trimmed).

**3. The shoot plan.** `$W/SHOOT.md`:
- **A-roll:** one row per script line (take order, delivery note, any gesture the edit will use, e.g. two fingers on "two").
- **Self-shot B-roll (optional, 2-4 shots, free, beats AI B-roll for trust):** each tied to an anchor sentence: hands
  typing on the dummy data, the phone screen, the desk wide, a walk into frame, the printout. Hold each 6-8 s, still
  phone, same light, 4K60 (or HD30 to match), portrait. These go in as R17-style L cutaways through `broll-conform.py`.
  aotw-01 shipped without any (the creator's choice): rebuilt panels (R19, R20) from the real files carried the proof.
- **Screen recordings (optional):** which app, which dummy file, what is clicked, in order (personal PC, one window,
  notifications off). When the proof is the tool itself, an R19 chat window rebuilt from the real command, the real
  file names and real frames is honest and needs no recording session.
- **Framing, light, sound** (below), and the outfit (solid mid-tone, no fine stripes or logos; the same one across days).

**4. The test clip.** The user records 5-10 s at the real spot (one script line, then 2 s of silence) and Claude runs
`$PY "$SK/scripts/test-shot.py" --in "$W/raw/test.MOV" --out "$W/testshot"` and **reads `framing.png`**. It checks the
format (4K60 or HD30), the mic (clipping, headroom, level), the room (noise floor, speech over room), the picture (blown
highlights, crushed shadows, a colour cast) and draws every zone on the frame. Fix what it flags and re-test before the
real shoot: a noisy room or a blown window cannot be fixed after.

**Recording so the cut works** (tell the user before every shoot):
- **Camera:** iPhone, portrait, main 1x lens at eye level. **4K 60 fps (default) or 1080p HD 30 fps** (see "Source
  profiles": HD has no zoom headroom). Lock focus and exposure on the face (long-press, AE/AF LOCK). **HDR Video OFF** (Settings → Camera → Record Video; the creator turned it off 2026-10-11): the takes then look exactly
  as the phone shows them and no HDR conversion can get the colour wrong.
  A second of silence at each end of every take.
- **Framing (the overlays need it):** the top of the head around y 540-620 of 1920 (~30% down: the M cards live above
  it), the eyes near y 900 (47%), the chin above y 1300 (the captions sit under it), centred, chest at the bottom. The
  test clip's `framing.png` shows it.
- **Light:** one soft key light in front, 45° to one side at face height, or face a window; never a window behind you. One
  colour of light only (daylight OR the lamp, not both). The same light for every take: skin-match evens out small
  drifts, not a new room or a cloud.
- **Sound:** DJI Mic clipped 15-20 cm under the chin, gain so a loud word peaks under -6 dBFS; fans, AC and fridge off;
  soft things in the room (rug, curtains, sofa) beat a bare one. `audio-polish.py` cleans the room; it cannot un-clip.
- **Keep the same framing and light across takes.** One script line per clip, or pause two seconds and restart the whole
  sentence. The last good take wins.
- **Say the CTA keyword clearly and exactly as written** (reel-1's best CTA take said "save" for "safe").
- Say numbers as they should appear; name tools and the news outlet out loud ("BleepingComputer reported...").
- Screen recordings: the personal PC, 1080p+, dummy data, notifications off, one app window.

## Source profiles: 4K60 or HD30

Both are iPhone sources; the reel is delivered at the source's own resolution and frame rate. Probe the first take
(`ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of csv=p=0`) and set:

| | 4K60 (default) | HD30 |
|---|---|---|
| `FPS` / composition `data-fps` | 60 | 30 |
| conform | automatic (keeps the source) | automatic (keeps the source) |
| cut encodes `-g` / `-keyint_min` | 60 | 30 |
| render | `--resolution portrait-4k --fps 60 --video-bitrate 50M --workers 1` | `--resolution portrait --fps 30 --video-bitrate 16M --workers 1` |
| `verify-render.py --res` | 2160x3840 | 1080x1920 |
| `broll-conform.py` | default (2160x3840 @ 60) | `--hd --fps 30` |
| take-join reframe / eased push / headroom | 1.00 ↔ 1.08 / +0.03 / up to 1.50 | 1.00 ↔ 1.06 / +0.02 / up to 1.12 (every zoom upscales) |
| conform time (8 GB PC) | ~1.5 min per 7 s take (aotw-01: 10 takes in 15 min) | ~15 s per 8 s take (6.6 s for a 4 s HD30 clip, 2026-10-11) |
| render time (8 GB PC) | ~13 min for 31 s (aotw-01) | a few minutes |

`reel-check.mjs` FAILs a `data-fps` that differs from `input-video.mp4` and a camera scale past the source's headroom.

## Setup check (first use, and after any update)

| Needs | Check | Install when missing |
|---|---|---|
| Node 22+ | `node -v` | nodejs.org |
| HyperFrames + Playwright (via the kit) | `cd "$KIT" && npx hyperframes --version` | `npm ci` in `$KIT` |
| Google Chrome | Playwright and renders launch it (`channel: "chrome"`) | google.com/chrome |
| FFmpeg with zscale | `ffmpeg -hide_banner -filters \| grep zscale` | Windows: `winget install Gyan.FFmpeg` (the full build); Mac: `brew install ffmpeg` |
| A transcriber: ElevenLabs key **or** whisper.cpp | `grep -c '^ELEVENLABS_API_KEY=.' "$KIT/.env"` (prints 1; never print a key), or the whisper files in Stage 2 | the user adds the key to `$KIT/.env` themselves (never paste it into the chat), or installs whisper.cpp (Stage 2, offline, free) |
| Python 3.10+ + numpy + Pillow | `$PY -c "import numpy, PIL"` | Windows: `winget install Python.Python.3.12 --scope user --override "/quiet InstallAllUsers=0 PrependPath=1"` (plain `--silent` gets cancelled); Mac: `brew install python`; then `$PY -m pip install numpy pillow` |
| auto-editor | `auto-editor --version` | `$PY -m pip install auto-editor`; its first run downloads a ~38 MB binary: let it finish (an interrupted one gives "not a valid Win32 application": delete `site-packages/auto_editor/bin/auto-editor.exe`, run again) |
| AI B-roll keys (optional) | `grep -c '^GEMINI_API_KEY=.\|^KIE_API_KEY=.' "$KIT/.env"` | the user adds them; nothing generates without a quoted cost and a yes |

Then `cd "$SK/scripts" && $PY -m unittest tests` (all must end `OK`).

## The routes

| Input | Route |
|---|---|
| **Many short iPhone takes, one per script line** (reel-1: 21 takes for 8 lines; aotw-01: 42 for 10) | transcribe each raw take → `TAKES.md` → Checkpoint A → skin-match + conform + audio-polish **the picked takes only** → `take-cut.py` (smooth flat cut) → transcribe it → find-joins (see "The fast path") |
| One continuous take with retakes inside | skin-match → conform → audio-polish → the Cut stage (paper-cut keeps the last take) → Checkpoint A → find-joins |
| Camera take + a screen recording | camera as above; the recording becomes R10 (L) scenes via `broll-conform.py` |
| A reel about a news story | as above, plus `capture-article.mjs` on the source article → R16 |
| A flat cut you already made | conform if it came off the phone → the build |
| A reel you admire | `teardown.py` on a file the user downloaded (see "Teardown") |
| Nothing recorded yet | Stage 0: brief → script-check + SCRIPT-REVIEW.md → SHOOT.md → test-shot |

Before the shoot, Checkpoint 0 (Stage 0). After it, two checkpoints; everything else runs unattended. **A, the cut:** `TAKES.md` / `PAPER-CUT.md`. **B, the plan:**
`PLAN.md` + `snaps/sheet.png` (every beat as a still, Reels UI shaded red, face box shaded teal). Then render, gates,
delivery.

## Scripts (`scripts/`)

Node (needs only Node, FFmpeg and the kit's Playwright):

| Script | Does |
|---|---|
| `skin-match.mjs` | per take: the skin level the camera recorded and where a plain tonemap puts it, on a forehead patch; prints `SKIN_TARGET` (median recorded + `--lift 2`) and a patch sheet |
| `conform-iphone.mjs` | HEVC/HLG takes → SDR H.264 **at the source's resolution and frame rate** (4K60 in → 2160x3840 @ 60), rotation applied, BT.709 tags, **skin matched to `--skin-target`** (curve verified on a frame, then on the output); `--hi` 2160x3840 |
| `transcript-normalize.mjs` | ElevenLabs / whisper JSON → `{duration, words:[{text,start,end}]}` |
| `captions.mjs` | transcript → caption groups in `index.html`; the spoken word lights up teal (default), `--em`, `--keyword`, `--band-top` |
| `capture-article.mjs` | the real article page as a phone (or desktop) screenshot + exact pixel boxes of the headline and each `--highlight` phrase |
| `layout-check.mjs` | every overlay measured every 0.1 s of its life and every caption group (Chrome, timeline seeked) against the (zoomed) face and the UI of each `--platform` (instagram, tiktok, shorts) |
| `reel-check.mjs` | size, fps vs the source, length, hook, pacing (incl. motion inside panels), zoom headroom, **jump-cut reframing (`--joins`)**, CTA, series tag, caption coverage, sound, privacy |
| `snap-reel.mjs` | a snapshot per beat → `snaps/sheet.png`, Reels UI zones shaded red |
| `color-check.mjs` | the render vs its source: tags, blacks, contrast, saturation, and **skin vs `--skin-target`** |
| `make-cover.mjs` | `cover.png` from a frame + one glass M card (`template/cover.html`), rendered through HyperFrames; checks the 4:5 feed and 3:4 grid crops and the face; writes `cover-crops.png` to read |
| `hold-check.mjs` | **every payoff readable**: each element still up when its card starts to close must have been fully visible ≥ 0.5 s (FAIL), ≥ 0.8 s (WARN); cards settled < 1 s WARN. Run before every render |

New 2026-10-11 (aotw-01): `take-cut.py` (the smooth many-takes cut: dissolves inside a take, hard cuts between takes,
4:2:0 output, `plan.json`), `cover-frames.py` (a numbered sheet of cover candidates at word ends, for the creator to
pick), `cover-logo.py` (a tool's app tile inside the cover card; the logo is yours to add to `$SK/assets/`, see README.md),
`bg-job.ps1` (runs a job script detached at BelowNormal priority).

Python, new for reels: `script-check.py` (the script's numbers, Stage 0), `test-shot.py` (the test clip: format, mic, room,
exposure, `framing.png`), `audio-polish.py` (measure / apply / check / master: the voice, see "Sound"), `find-joins.py`
(every jump cut, found in the picture → `joins.json`).

Python, the cut and the checks (each prints its usage with `-h`; shared helpers in `_cutlib.py`): `paper-cut.py`,
`hand-cut.py`, `tighten-cut.py`, `sliver.py`, `edge-audit.py`, `apply-cut.py` (frame-exact; output fps = the source's;
writes `cut-map.json`), `dead-air.py` (reads `audio.wav` or `public/input-video.mp4`), `patch-cut.py`, `phrase-times.py`,
`stutter-scan.py`, `ingest.py`, `beat-check.py`, `verify-render.py` (default `--res 2160x3840`; writes the beat, dense and
transition sheets with Pillow, no ffmpeg fonts needed), `broll-conform.py` (default 2160x3840 @ 60; `--hd`, `--fps`,
`--size WxH`), `screen-activity.py`, `teardown.py` (short-form pacing: first change, changes per 10 s, holds),
`cutlist-to-edl.py`.

## Stage 1: skin match + conform (every phone file that goes into the reel)

**Many-takes route: after Checkpoint A, on the picked takes only** (aotw-01 measured all 42 takes and froze the app;
10 were used). Transcription (Stage 2) reads the raw `.MOV`s directly, so it comes first. Run the measurement and the
conform as detached jobs (`bg-job.ps1`).

The rule (the creator, 2026-10-07): **"the exact same skin tone as the actual footage, just a tad of light (very minor),
all uniform."** Not a look, not a target from a chart: what the camera recorded, +2 points, identical on every take.
And (2026-10-11, the creator's pick "C + colour kept" on a dim take): **a dim shoot is lifted to at least 63%, and the
skin keeps its recorded colour** ("lighten up a bit but should not look fake"; the output "should be along those
lines", adjusted per reel from the raw clips). A plain lift greys the skin (53.7% -> 63% took its saturation from 37.9%
to 32.5%: washed out), so the conform restores the recorded skin saturation after the lift (x1.18 there). **Provisional:**
63% and the lift were judged on a phone screenshot; on the next reel (the first shot with HDR off) show the
`--preview` sheet, let the creator tune the target, and write the result here and in STYLE-GUIDE.md.

```bash
# 1. a gridded frame to find a flat forehead patch (no hair, brows or shine) and the face box
ffmpeg -ss 2.5 -i "$W/raw/<take>.MOV" -frames:v 1 -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,drawgrid=w=108:h=192:t=2:c=red@0.6" "$W/grid.png"
# 2. measure every take; check the patch sits on skin in the sheet
node "$SK/scripts/skin-match.mjs" --patch 330,790,240,60 --sheet "$W/patches.png" "$W/raw/"*.MOV     # -> SKIN_TARGET=72.5
# 3. PREVIEW before the long encode: the median take at plain / target-3 / target / target+3, colour kept. Show it to
#    the creator; move SKIN_TARGET if the raw clips need it (this reel's light decides, 63% is the floor, not a must)
node "$SK/scripts/conform-iphone.mjs" --preview "$W/skin-preview.png" --skin-patch 330,790,240,60 --skin-target <SKIN_TARGET> "$W/raw/<median take>.MOV"
# 4. conform every take to that one target (colour kept is the default)
node "$SK/scripts/conform-iphone.mjs" --out-dir "$W/conformed" --skin-patch 330,790,240,60 --skin-target <SKIN_TARGET> "$W/raw/"*.MOV
```

The conform keeps the source's resolution and frame rate (4K60 → 2160x3840 @ 60, HD30 → 1080x1920 @ 30; `--hd` /
`--fps N` to override) and takes ~2 min per 8 s take at 4K on an 8 GB PC. Each conform line prints `skin recorded / plain / target`, `skin sat
plain / lifted -> kept (xS)` and the output's skin level and saturation; every output within ±0.5 of the target. Reel-1:
recorded 68.8-72.8% (median 70.5), plain tonemap 73.4-75.6%, all outputs 72.1-72.6%. Write the patch, the face box
(x,y,w,h of the head incl. hair and beard, read off the gridded frame) and `SKIN_TARGET` into `$W/BRIEF.md`.

**Then the voice, on the conformed takes, before any cut** (Claude cannot hear it, so it is measured; see "Sound"):

```bash
$PY "$SK/scripts/audio-polish.py" apply --in-place "$W/conformed/"*.mp4    # every take -> -20 LUFS, the room -> -66 dBFS
$PY "$SK/scripts/audio-polish.py" check "$W/conformed/"*.mp4               # PASS before the cut; a clipped take is re-shot or dropped
```

If `check` FAILs on the noise floor, do not retry blind: measure the room by band (see "Sound": a low rumble needs the
rumble fix, which is one more apply after restoring the original audio).

## Stage 2: transcribe

```bash
# many takes: the RAW takes, before any conform (6 at a time in the background; ~2 min for 42 takes)
cd "$KIT" && node scripts/transcribe-elevenlabs.mjs "$W/raw/<take>.MOV" --output "$W/tx/<take>.raw.json" --no-diarize
# (conform keeps the timeline, so raw-take word times are the conformed takes' times too)
node "$SK/scripts/transcript-normalize.mjs" --in "$W/tx/<take>.raw.json" --out "$W/tx/<take>.json"
# ElevenLabs is the default engine (needs ELEVENLABS_API_KEY in $KIT/.env). No key? Use the offline route below.
# Offline (free, no credits; ~35 s per take on an 8 GB PC): whisper.cpp + DTW, audio-snapped, vocabulary from the script
#   node "$SK/scripts/transcribe-local.mjs" --in "$W/conformed/<take>.mp4" --out "$W/tx/<take>.json" --prompt-file "$W/assets/script.md"
# Tested on reel-1's 8 takes: 117/119 words identical, word starts median 0.03 s / 90% within 0.17 s of ElevenLabs. Not
# `npx hyperframes transcribe --engine whisper`: its timings put a take's first word ~2 s early. To install it, ask the user
# first (1.5 GB download), then: whisper-bin-x64.zip from the official
# github.com/ggml-org/whisper.cpp releases, unzipped to ~/.cache/hyperframes/whisper/bin (whisper-cli.exe in Release/; Mac/Linux: build it, pass --whisper <path>),
# and ggml-medium.en.bin (1.5 GB) from huggingface.co/ggerganov/whisper.cpp into ~/.cache/hyperframes/whisper/models.
```

Always normalize (raw Scribe output carries " " spacing entries that paper-cut reads as words).

## Stage 3: the cut

**Many takes.** Transcribe every take, match each to a script line (word overlap, not filename order), write
`$W/TAKES.md` (per line: every candidate, its text, length, a verdict: keep / false start / flubbed word / cut off /
paraphrase drift). Pick the last complete clean take; **flag a CTA take whose keyword was misheard** and **a line whose
key phrase is missing in every take** (aotw-01: "I work in ops" was never said; offer an on-screen fix, a re-shoot, or
dropping what depended on it). Checkpoint A. Then write `$W/cuts/picks.tsv` (`line<TAB>take<TAB>in<TAB>out<TAB>note`:
in = ~0.1 s before the first word, out = ~0.11 s after the last; to drop a lead-in phrase, start in the gap after it) and,
after the conform and audio polish, cut it in one detached job:

```bash
$PY "$SK/scripts/take-cut.py" --project "$W" --fps $FPS          # --plan-only first to read the plan
# per take: pauses over 0.30 s (0.25 s after a sentence) become 0.08 s dissolves, ~0.12 s of pause left, no head jump;
# between takes: hard cuts. Writes cuts/plan.json and public/input-video.mp4 (yuv420p, BT.709, keyframe every second)
```

The dead-air pass below is then already done for the many-takes route: go straight to transcribing the flat cut.

**One continuous take**: `auto-editor` speech chunks → `paper-cut.py` → Checkpoint A →
`tighten-cut.py --maxgap 0.20` → `sliver.py --fix` → `edge-audit.py --fix` (then 0 issues) → `apply-cut.py`.

**After either:** transcribe `public/input-video.mp4` → `$W/transcript.json` (flat-cut time; every check reads it),
then dead air at reel pace: nothing over 0.25 s after a sentence, 0.30 s elsewhere, trimmed to 0.12 s
(`dead-air.py "$W" --plan --max 0.30 --max-sentence 0.25 --target 0.12`, `patch-cut.py --drop-flat`, re-apply until 0).
Scan the flat transcript for the same 3-4 words twice within 7 s (a leaked retake). Target 30-60 s.

**Then the jump cuts**, found in the final flat cut's picture (the edit lists are stale once dead air is patched):
`$PY "$SK/scripts/find-joins.py" --video "$W/public/input-video.mp4"` → `$W/joins.json` (~45 s for a 4K reel). After
`take-cut.py`, keep only the hard joins in `joins.json` (match each `plan.json` take start to the nearest found cut within
0.08 s: the picture's cut lands 0.03-0.06 s later, frames round up per take); a dissolve that also shows up (score ~4-9x
against 18-38x for a hard join) is not a jump cut and gets no reframe. Store the dissolve times as `soft_dissolves`.
**Settle the cut before Stage 5**: every beat time depends on it (aotw-01's late re-cut meant re-timing all 14 cards; if
it happens anyway, re-time from anchor words with `reference/aotw-01-v4/retime.py` as the pattern, never by hand).

## Stage 4: the plan (Checkpoint B)

`$W/PLAN.md`, one row per beat: time, **size (S / M / L)**, format, the anchor phrase (exact spoken words), on-screen
words (four or fewer per line). Propose any L longer than 6 s, a verdict, an article, or AI B-roll before building.

**The hook gate:** motion by 0.5 s; the promise on screen by ~1.5 s (muted viewers); the first spoken word never covered
by a cut or a sound; results first; one open loop, paid off before the CTA.

**Face time:** aim for 50-60% of the runtime with the face visible (reel-1 v3: 56%). The face is the trust signal; L panels
are the proof. Never two L panels back to back for more than ~14 s without a face beat between.

## Stage 5: build

```bash
mkdir -p "$W/public/img" "$W/renders"
cp "$SK/template/index.html" "$SK/template/reel.css" "$SK/template/reel.js" "$W/public/" && cp "$KIT/node_modules/gsap/dist/gsap.min.js" "$W/public/"
#   fill the __PLACEHOLDERS__ (incl. __FACE__ = the face box), author beats between the BEATS markers: borrow the markup
#   and tween calls from $SK/reference/aotw-01-v4/index.html (tool graphics, flips, the frame check) and
#   $SK/reference/reel-1-v3/index.html (article, explainer, demo); every component's CSS is already in reel.css
#   glass tint from the footage (see "Liquid glass"): sample the clothing, set --glass-tint in a <style> :root override
#   __FPS__ = the source's rate (60 or 30); a camSet at every HARD join only, alternating 1.00 / 1.08 (see "Camera")
#   tool logo: cp "$SK/assets/<tool>-logo.png" "$W/public/img/" (not shipped: README.md); real take thumbnails: 240x320 face crops of the raw takes
#   TIMING (aotw-01 re-rendered 3 times for this): every card's payoff lands on the EARLIEST word that says it, and the
#   card stays up until the payoff has had >= 0.6 s at full opacity (a 0.34 s pop + reading time) before lgOut. A card
#   may outlast its sentence if the next card sits in another zone. Anchor every card to the word it enters on.
node "$SK/scripts/captions.mjs" --transcript "$W/transcript.json" --index "$W/public/index.html" --keyword <word> --em "<words>"
cd "$KIT" && npx hyperframes check "$W/public"                                                       # 0 errors
$PY "$SK/scripts/beat-check.py" --index "$W/public/index.html" --transcript "$W/transcript.json"     # every card on its word
node "$SK/scripts/hold-check.mjs" --public "$W/public"                                               # every payoff readable (FAIL < 0.5 s)
node "$SK/scripts/layout-check.mjs" --public "$W/public" --platform instagram,tiktok,shorts          # every 0.1 s: S/M off the face, captions clear, per platform
node "$SK/scripts/reel-check.mjs" --public "$W/public" --transcript "$W/transcript.json" --joins "$W/joins.json"
node "$SK/scripts/snap-reel.mjs" --project "$W"          # READ snaps/sheet.png before rendering
```

**`hyperframes check` notes:** contrast samples on text inside small mock UI (a fake browser's URL text) are expected;
anything on the glass itself under 3:1 is a real fix (darken the tint, lighten the text colour). `container_overflow` on
`#video-zoom` during a punch is expected. `gsap_exit_missing_hard_kill`: add a `tl.set(..., {opacity:0})` after the fade.
`overlapping_clips_same_track`: give one of them another `data-track-index`.

## Stage 6: render, gate, deliver

```bash
# the render flags come from "Source profiles". 4K60: the 1080x1920 composition renders at 2x, one worker on an 8 GB
# PC, a fixed bitrate (Instagram re-encodes anyway). HD30: --resolution portrait --fps 30 --video-bitrate 16M
cd "$KIT" && npx hyperframes render "$W/public" --resolution portrait-4k --fps 60 --sdr --video-bitrate 50M --workers 1 -o "$W/renders/raw.mp4"
# the master: two-pass loudnorm to -14 LUFS / -1 dBTP (linear), BT.709 tags, faststart, video copied; then its audio gate
$PY "$SK/scripts/audio-polish.py" master "$W/renders/raw.mp4" "$W/renders/<slug>-v1.mp4"              # exit 1 = do not deliver
node "$SK/scripts/color-check.mjs" --render "$W/renders/<slug>-v1.mp4" --public "$W/public" --at <face-visible times> \
  --skin <patch> --skin-target <SKIN_TARGET>                                                           # exit 1 = do not deliver
$PY "$SK/scripts/verify-render.py" --render "$W/renders/<slug>-v1.mp4" --index "$W/public/index.html" \
  --res <2160x3840|1080x1920> --joins "$W/joins.json"                                                  # + dense and transition sheets
# the cover: the CREATOR picks the frame (aotw-01: Claude's mid-word pick was rejected), then the card, then the logo
$PY "$SK/scripts/cover-frames.py" --project "$W"         # renders/cover-options.png (send it) + cover-options.txt (NN -> time)
node "$SK/scripts/make-cover.mjs" --project "$W" --at <picked time> --title "<line one>|<*accent* line two>" \
  --eyebrow "<series tag>" [--tone accent|danger|warn]                                                 # READ renders/cover-crops.png
$PY "$SK/scripts/cover-logo.py" --cover "$W/renders/cover.png" --logo "$SK/assets/<tool>-logo.png"    # when the reel is about a tool
```

Run the render chain as ONE detached job (render → master → colour → verify) and nothing else until it ends (a frame grab
during aotw-01's render stalled it at 98%). Make the cover frame sheet before the render or after it, never during.
Pick colour `--at` times where the face is visible, on the 1.00 framing and not mid-push (the colour comparison is against
the un-zoomed source; aotw-01: base 1.00 = the 1st, 3rd, 5th... take).

**Read every sheet `verify-render.py` lists** (~1 min for a 45 s 4K reel): `render-dense-NN.png` (a frame every 0.5 s)
and `render-transitions-NN.png` (5 frames around every card entrance, exit and jump cut; VERIFY.md maps each page/row to
its event). They show what the beat sheet cannot: a card flashing for a frame, a caption under a panel, a cut on the same
framing, the glass mid-morph. Reel-1 v4's sheets show each L panel's entrance droplet as a dark or white blob on the face
for 2-3 frames (3.43, 8.90, 16.62 s): that is the approved look, but say so if one reads as a glitch. **Read the sheets
element by element, not card by card**: on each card, find its last element (the flipped word, the last pipeline node,
the second checklist row) and confirm it is legible in at least one frame before the card's exit. aotw-01 shipped three
renders where the card was visible but its payoff was not.

**Deliver** `$W/renders/<slug>-vN.mp4` plus `cover.png` (`make-cover.mjs`: a frame where the face reads well and the
head sits low enough for the card; inside both the 4:5 feed and 3:4 grid crops; 2 lines / 6 words at most), `POST.md` (caption draft: hook line, 2-4 short lines, "Comment WORD and I'll send you <lead magnet>", 3-5
niche hashtags, the keyword for ManyChat/CreatorFlow, **"AI info" label: on** whenever AI B-roll is in it, **source credit**
when an article is shown: "Source: <outlet>, <date>"), and a report: what was built, every gate's result (incl. the audio numbers: master LUFS, true peak, room floor), and what was
**not** checked (Claude cannot hear: the voice's tone after the polish, clicks at joins, pacing by feel). Never claim a reel is ready to post.

## Colour and skin: the footage's own look, never washed out

1. **Record with HDR Video off (the default since 2026-10-11).** SDR takes need no conversion: what the phone shows is
   what the edit starts from. **An HLG (HDR) take is a known problem:** read raw it is washed out (skin saturation ~19%
   vs ~38%); `conform-iphone.mjs` tonemaps it (zscale + mobius, npl 100, `desat=0`), but that came out far brighter and
   warmer than the phone's own view of the same reel-1 takes: skin 73% vs 54%, the white wall 94% with a yellow-green
   tint vs 63% neutral, the hoodie 50% at saturation 56 vs 24% at 41. A standard 1000-nit conversion (`zscale npl=1000`)
   plus a neutral wall matched the wall and hoodie brightness but not the skin, and fitting was blind because the phone
   screenshot's frame was unknown. If HLG takes arrive: ask for a re-shoot with HDR off, or for a full-screen phone
   screenshot of a named take at a known second, and calibrate against that exact frame before conforming.
2. **The plain tonemap is ~4 points too bright on skin** (reel-1 v2: "I am appearing too light"). The skin match bends one
   tone-curve point so the forehead lands on the recorded level + 2 (at least 63%): whites and blacks untouched. No
   contrast or saturation boost by default (`--grade bright|deep` only on request).
3. **A lift greys the skin; the colour is put back** (2026-10-11). After the curve the conform measures the forehead's
   saturation and solves an `eq=saturation` factor (clamped 0.80-1.40) that puts it back on the plain tonemap's: lighter,
   the same colour, never richer than recorded. On reel-1 (well lit) it is x0.97, i.e. nothing; on a dim take lifted
   ~9 points, x1.18. A bigger factor (x1.27 at reel-1's 68% from a 54% take) also makes the hoodie and the wall art
   vivid: the creator chose the smaller lift over that. `--no-keep-colour` turns it off.
4. **Tags:** render with `--sdr`, remux BT.709 + `color_range tv`. Never ship HDR or untagged files to Instagram.

`color-check.mjs`: tags; render vs source black level (+8 max), contrast (-10%), saturation (-15%); skin median vs the
target (FAIL past +3 / -4); skin saturation render vs source within 2 points either way (greyer = washed out, richer =
fake; reel-1 v4: -1.7, the renderer costs a little). Leave HyperFrames frame extraction on its default (PNG extraction darkened blacks ~12).
**B-roll, screen recordings and AI clips** go through `broll-conform.py` (BT.709) before `public/`.

## Overlay sizes and the face

The user's rule (2026-10-07): **overlays are sized by what they need, and only a large overlay that needs the space may
cover the face.** Every `.card-host` declares `data-size`:

| Size | What | Where (1080x1920) | Budget |
|---|---|---|---|
| **S** | pill, chip, counter, series tag, a single label | beside the head (right: x ~690-1040 above y 1000) or above it | up to 560x132 |
| **M** | headline, stat, verdict, checklist (2 rows), tool row, CTA | the top zone, y 250 → top of the face box - 20 | up to 960 wide; height whatever fits above the face |
| **L** | article, diagram, app window, table, pipeline, screen recording, stock or AI B-roll | x 60-940, y 250-1290; **may cover the face**, always with `dim()` | up to 880x1000 |

- The face box (`data-face="x,y,w,h"` on the root) comes from the gridded frame in Stage 1. `layout-check.mjs` seeks the
  timeline every 0.1 s through every overlay's life, measures its real box, scales the face with the camera (a punch or a
  cut reframe grows the face), and FAILS an S or M that touches it at any moment, anything under the Reels header
  (y < 250), over the captions (y > 1290), or under the like/comment/share column (x > 960 below y 1000; x > 1040 above),
  and any caption group under an overlay.
- **TikTok / Shorts:** `--platform instagram,tiktok,shorts` checks the others too (WARN; the first is the primary). Their
  button columns are wider: TikTok x ≤ 940 below y 800, Shorts x ≤ 880 below y 1000. Reel-1's L panels (to x 950) and a few
  wide caption groups sit under both. Fine for an Instagram-first reel; for a cross-post that matters, narrow the L panels
  to 820 and `captions.mjs --max-chars 18`.
- If an M will not fit above the head, shorten the copy (four words), split it into S pills beside the head, or promote
  it to L if it truly needs the room. Never shrink type below 40 px to make it fit.
- No camera push or tighter reframe while an M is up if the grown face would reach it (layout-check tells you).
- **Captions band:** y 1320-1500 by default, under the chin (`--band-top` to move it). Captions stay on over L panels.

## Liquid glass (the overlay material)

Every overlay is a `.lg` element (reel.css): a smoked, saturated blur of the footage behind (`backdrop-filter: blur 20 +
saturate 1.7 + brightness .72`, plus an SVG refraction wobble), a bright specular rim on the top edge, a soft inner glow,
a teal under-glow, and a sheen that sweeps once on entrance. Variants: `.accent` (teal rim + glow), `.warn`, `.danger`.

- **Tint from the footage:** sample the clothing or the darkest large area of the shot and darken it into
  `--glass-tint` (alpha ~.64) so the glass belongs to the video: `ffmpeg -ss 15 -i input-video.mp4 -frames:v 1 -vf
  "crop=500:260:290:1560,scale=1:1:flags=area,format=rgb24" -f rawvideo - | od -An -tu1`. Reel-1: hoodie rgb(103,137,192),
  hue 217 = the brand navy's hue → `rgba(24,38,68,.64)`.
- **Smoked, not clear, on a bright room:** at alpha .40 over reel-1's white wall, white text measured 1-2.7:1. Keep alpha
  ~.6+ and text colours from the light tints (`#5eead4` teal, `#fcd34d` amber, `#fca5a5` red) on glass; the saturated
  brand colours are for fills (chips, stamps, the CTA keyword).
- **Motion (reel.js):** `lgIn(sel, t)` grows the glass from nothing → a droplet pill → the full panel (clip-path, expo.out),
  lifts 26 px, sweeps the sheen, then brings the content in (`[data-c]` children, staggered). `lgOut(sel, tEnd)` reverses it
  into a pill and closes. **Never fade glass through an ancestor's opacity** (Chrome drops backdrop-filter during the fade);
  reveal with clip-path, fade only content. `dim(t0, t1)` steps the footage back behind L panels.

## Format library (9:16)

Vary formats; never the same device twice in a row (captions excepted). Every panel is liquid glass, in the brand colours.
The CSS for every row below is in `template/reel.css`; working markup for R2-R7, R13-R16 is in the reference build.

| # | Format | Size | Use for / how it moves |
|---|---|---|---|
| R1 | **Active-word captions** | band | always on; the word being spoken lights teal, accent words stay teal, the keyword is a solid teal chip, numbers in mono |
| R2 | **Series / topic tag** | S | 0.15-3.35 s top-left, a live teal dot |
| R3 | **Hook card** | M | the promise in ≤4 words by ~0.3 s; the payoff word pops (scale) on its word |
| R4 | **Stat punch** | M | one stakes number counting up in mono teal (`count()`) |
| R5 | **Pills** | S | 1-3 words + icon, beside or above the head, each on its word (a row of them = M) |
| R6 | **Number chip** | S | "2" tests / "3" steps, beside the head; the screen numbers the steps so the voice does not have to ("Step one" read as aggressive) |
| R7 | **Checklist** | M | 2 rows, ✓ teal / ✗ red, each row popping on its word |
| R8 | **Prompt + answer window** | L | the prompt types as it is said (`type()`), answer rows land on words |
| R9 | **Table focus** | L | dummy ERP export, ≤6 rows, one row lit per word, the value in teal |
| R10 | **Screen recording** | L | the real build (dummy data) in a glass window, drift 1.00 → 1.04 |
| R11 | **Pipeline** | L | 3-5 nodes stacked vertically, a light running down as each is named |
| R12 | **Verdict stamp** | M | PASS / HALF / FAIL, the one overshoot (`back.out(2)`) |
| R13 | **Explainer diagram** | L | a mock UI that shows the mechanism (reel-1: the fake pop-up drawn inside the page, rings on "address bar" and "padlock", a dashed outline + "Just HTML in the page" on "drawn inside") |
| R14 | **Demo** | L | a before/after or a test acted out (reel-1: drag the pop-up; the real window leaves the browser, the fake one sticks at the edge, cursor included) |
| R15 | **CTA** | M | one row: "Comment" + the keyword chip, the lead magnet under it; above the head so the last line lands on the face |
| R16 | **Real news article** | L | the actual page (`capture-article.mjs`) in a glass browser with the domain in the URL pill and "Outlet · date" under it; opens on the headline, scrolls to the passage as it is spoken, the highlighter strokes the exact phrase on its word (teal; amber for the stakes), a gentle zoom into the passage |
| R17 | **Stock cutaway** | L | the person or job described, 2-3 s, Pexels portrait |
| R18 | **AI B-roll** | L | the scene the sentence describes, 2-5 s, see "AI B-roll route" |
| R19 | **Tool chat window** | L | the tool's own app look (Claude: light `#faf9f5`, the spark, "How can I help you today?") inside the glass; the real command types into the box as it is said (`type()`, aotw-01: `/short-form-video-edit`), the real files drop in as attachments on "drop in" (real take thumbnails), a count ("42 clips"), tags on the words ("retake" amber, "flub" red), the send button presses before it closes. Rebuilt from real names and files: honest, no screen recording needed |
| R20 | **App-tile pipeline** | M | "raw in, edit out": a file card (thumbnail or doc icon + name + a mono duration/size chip) → a wire that draws → the tool's app tile (white rounded square + logo) → wire → the output chip; each node on its word (aotw-01: `SKILL.md · 601-LINE SOP` → Claude; `10 of 42 takes · 1:01 RAW` → Claude → `0:31 REEL`) |

**Tool logos:** none ship with this skill (they are the tools' trademarks). The user adds a transparent PNG of the
tool's logo from its official brand or press page to `$SK/assets/<tool>-logo.png`: a small inline spark next to the
tool's name, inside R19's window header, in R20's app tile, and on the cover via `cover-logo.py`. A logo names the tool; it never implies the tool's maker endorses the reel.

**Engagement devices (use 2-3 per reel, not all):** the payoff word popping inside the hook card (or a flip: "Edits by
me 0" → "Edits by Claude ALL"); numbered chips; the active-word captions; a highlighter landing on the exact spoken words
of a real source; an acted-out demo with a cursor; a tool's chat window filling as it is described; an eased push on a
payoff word; `dim()` behind L panels so they arrive like a scene change.
`reel-check` counts motion inside panels (`pop`, `mark`, `pageTo`, `count`, `type`) as visual changes.

**Copy on screen:** ≤4 words per line, readable in under 1.5 s, numbers in JetBrains Mono, full money figures, no
sentences on cards (captions carry them), one accent word per line. **Every number measures the claim it sits under**
(aotw-01 v2 showed "4:19 raw → 0:31" under "cuts the dead air"; 4:19 was every take ever recorded, and the creator caught
it: "It can't be reduced from 4:19 to 31 secs"). Dead air cut = the picked takes as recorded → the reel; takes picked =
"10 of 42". Say where each number comes from in PLAN.md.

**Rejected:** an AI avatar or clone presenting; AI images used as proof (fake dashboards, results, screenshots); real
company or SAP screens; "link in bio", subscribe bars, end cards; neon, glitch, flash cuts, whips, elastic type, emoji
rain; a whoosh under text; solid opaque slabs over the footage (the v1/v2 look); an S or M on the face.

## News articles (R16)

```bash
cd "$KIT" && node "$SK/scripts/capture-article.mjs" --url "<article>" --out "$W/public/img" --name article --height 1800 \
  --highlight "<exact phrase 1>" --highlight "<exact phrase 2>"
```

- Use the **outlet's real page**, captured as a phone (393 px at 4.5x by default, so the ~1700 px L panel of a 4K reel
  stays sharp; boxes come back in image pixels: divide by dpr/3 for the composition's layout units). It writes
  `article.png`, `article-top.png` and `article.json` (headline and every phrase as line boxes in screenshot pixels). Put
  the boxes straight into `.mark` divs inside `.page` ($SK/reference/reel-1-v3/index.html shows the exact markup and the `pageTo` / `mark` calls).
- **Highlights = the words you say**, copied exactly from the page (the script lists any phrase it cannot find: fix the
  wording, never fake it). Check `article.png` with the boxes drawn before building.
- Consent banners: the script only ever clicks reject / necessary-only, otherwise hides them. Ads and sticky bars are
  hidden; the article text is never edited. Prefer the outlet that broke or best explains the story; credit it on screen
  (outlet + date) and in POST.md.
- **Blocked (bot check, 403, paywall): exit 3. Never work around it** (no stealth, no fake user agents beyond the phone
  layout). A Cloudflare "Just a moment" can be transient: one plain retry later is fine. Otherwise use another outlet's
  coverage (reel-1: BleepingComputer was blocked once, then loaded; The Hacker News covered the same Island research), or
  the user screenshots it on their phone and it goes in as the image.

## AI B-roll route (R18)

Generated shots of the scene a sentence describes, from an image service and an image-to-video service. Keys live in
`$KIT/.env` (`GEMINI_API_KEY` for stills, `KIE_API_KEY` for image-to-video); never print them.

- **It shows a scene, never a presenter.** It may star you (from your own reference photos) doing the thing the sentence
  describes, or nobody; never another real person; extras generic and in the background. It never talks to camera, never
  replaces a spoken line, and is never proof: no fake dashboards, revenue, screenshots, results or company UI. Screens in
  a generated shot are turned away or out of focus (generated screens show fake text).
- 2-5 s, about one per 30 s at most, never two in a row, always an L `clip` with an anchor, conformed vertical.
- **Generating costs money each time: say what a run will cost and wait for a yes, every run.** Nothing is generated
  until the shot list is approved.
- **Label it:** Instagram's "AI info" label on upload, every time; note it in POST.md.

**The chain:**
1. Shot list `$W/BROLL.md`: anchor sentence, the scene in one line, outfit (the one in the footage), camera move, length.
   Approved at Checkpoint B.
2. References (only when the shot stars you): 6-12 photos the user provides (plain wall, video light, front and
   three-quarter, one at the desk) plus 2-3 frames of the footage. The same set every time, or the face drifts. The user
   uploads their own photos to the service; Claude never posts them.
3. The still, **9:16**. Describe it in this order: who (the person in the reference photos, keeping their face and hair),
   the outfit, a single action, a concrete place, the light (window light and a time of day), the camera (35mm, eye
   height, soft background), and the finish (real skin texture, nothing written, no logos, portrait 9:16). Look at the
   face, the hands and anything written before paying for motion.
4. Motion: image-to-video, 5-8 s, no audio. Ask for one slow camera move and one small action, and rule out cuts and
   extra people (e.g. "the camera drifts in slowly while she finishes typing and glances at the monitor; one continuous
   shot, nobody else enters").
5. `$PY "$SK/scripts/broll-conform.py" --in "$W/broll/raw/<shot>.mp4" --out "$W/public/broll/<shot>.mp4" --start 0.5 --dur 4 --grade`
   (budget version: the still alone, `--in <shot>.png --dur 4 --push 1.08`), read its sheet, then into the composition
   as an L `<video class="clip">` at the root (muted, own track) inside a glass frame or full-bleed under `dim()`.

## Camera

Calm by default (aotw-01, 2026-10-11, the creator on v2: "A lot of zoom in and joins are not very smooth. Ensure that
the cuts and zoom in and outs are smooth and flow naturally"; v4 approved). v2 reframed 1.00 ↔ 1.12 at all 19 cuts (one
every 1.6 s) and punched in 0.32 s snaps; that is what read as jumpy.

- Origin at the eye line (`#video-zoom { transform-origin: 50% 47% }`; measure per shoot).
- **A reframe only where a new take starts** (the hard joins in `joins.json`): `camSet(join + 0.003, s)`, alternating `s`
  between 1.00 and 1.08 per take (1.00 / 1.06 on HD). A new line in a new framing reads as a new shot. **Pauses trimmed
  inside a take are dissolves (`take-cut.py`) and get no reframe.** Joins under an L panel are set too (harmless).
  `reel-check --joins` WARNs a hard join on the same framing either side; `layout-check` re-measures every S/M and the
  captions at the tighter framing.
- **Pushes, not punches:** `tl.to('#video-zoom', { scale: base + 0.03, duration: 0.7, ease: 'sine.inOut' }, word - 0.25)`
  on one or two payoff words per reel (aotw-01: "SOP", "quality checks"). The push is released by the next hard join's
  reframe: **never zoom out in the middle of a line**, never a 0.32 s snap.
- The tighter framing grows the face downward from the eye line: at 1.08 aotw-01's beard (y ~1385) reaches the caption
  band: `captions.mjs --band-top 1360`. M cards must end above the face top at the tightest framing they share
  (aotw-01: base 1.08 + push 0.03 → end above y ~510).
- Headroom: the 4K conform holds 150% cleanly, HD only 112% (every zoom upscales); reel-check FAILs past it. No moves while
  an L panel covers the face (nobody sees them).

## Pacing

- A visual change at least every 4 s (reel-check WARNs past 4, FAILs past 6), counting motion inside panels.
- Entrances via `lgIn` (≈0.6 s total); exits via `lgOut` into the clip end (it starts closing 0.28 s before). One hero
  element at a time.
- **The payoff holds** (aotw-01: "ALL", "0:31 REEL" and "Can't hear the audio" each showed for 0.3-0.4 s and cost three
  re-renders): the last thing a card shows needs ≥ 0.6 s at full opacity before the card starts to close. Pop it on the
  earliest word that says it (the pipeline's last node on "cuts", not "air"; the second checklist row on "what", not
  "couldn't"), and hold the card past its sentence when needed. A flip (hook "me: 0" → "Claude: ALL") counts from the
  flip. Tags dropped on a closing panel ("every mess-up" → red flub tags) need the panel held too. `hold-check.mjs`
  FAILs under 0.5 s.
- Dead air: nothing over 0.25 s after a sentence (dissolved inside a take, see "Camera").

## Sound

**The voice** (`audio-polish.py`, on the conformed takes before the cut; measured, because Claude cannot hear):
- the chain per take: high-pass 80 Hz → FFT denoise (`afftdn nf=-50`, its reduction solved per take, up to 3 measured
  tries) → a gentle de-esser (0.25) → pre-level → 2.5:1 compressor → a trim to exactly -20 LUFS. Video is copied.
- the goal: every take at -20 LUFS (within 1 LU) with the room at -66 dBFS (within 4 dB), so neither the level nor the
  background jumps at a join. Reel-1's raw takes: -31 to -33 LUFS, rooms -69 to -77 dBFS (a 9 dB jump at joins, mostly
  below 150 Hz); polished: 0.1 LU and 0.9 dB spreads, speech level unchanged.
- the master (`audio-polish.py master`, Stage 6): two-pass linear loudnorm to -14 LUFS with true peak aimed at -1.5 (the
  AAC encode adds ~0.5), then the gate: -14 ±1 LUFS, true peak ≤ -1.0, room ≤ -56 dBFS (reel-1 v4 as shipped: -52.4, a
  WARN; through the new chain: -59.4), no clipping.
- `--eq` takes extra ffmpeg filters (a mud cut `equalizer=f=250:t=q:w=1:g=-2`) only when the user hears a problem or a
  measurement shows one: never add EQ blind.
- **The rumble fix** (aotw-01, 2026-10-11): `check` FAILed every take at a floor of -48 to -51 dBFS after `apply`: the
  level boost lifted a steady room rumble at 40-80 Hz (-55 dBFS raw, ±1 dB: AC / building / traffic, not handling) that the
  80 Hz high-pass and the FFT denoise barely touch. Measure first: the RMS of a silent head (0.3-1.3 s) through
  `lowpass=150`, `150-1000`, `1000-4000`, `>4000`; if the energy sits under 150 Hz, restore each take's original audio
  (`ffmpeg -i conformed.mp4 -i raw.MOV -map 0:v:0 -map 1:a:0 -map_metadata -1 -c:v copy -c:a aac -b:a 256k ...`;
  `-map_metadata -1` drops the "audio-polish" tag that makes `apply` skip a file) and apply again with
  `--hpf 120 --eq "highpass=f=120:poles=2,agate=threshold=0.0056:ratio=2:range=0.3:attack=5:release=200:knee=3"`
  (a 4th-order cut under 120 Hz plus a gentle gate: at most -10 dB in pauses, 2:1, 200 ms release so word tails stay).
  aotw-01: floors -66.1 to -68.8, spread 2.7 dB, speech level unchanged.
- **The master's floor reading on a tight cut is not the room:** it is the 5th percentile of 50 ms windows, and a reel cut
  to 0.12 s pauses has almost no silence left, so it scores word tails and breaths (aotw-01: the same audio read -61.4
  before the dead-air trim and -41 to -44 after; the pauses' energy sat at 150-4000 Hz, the voice band, not the rumble
  band). When the takes passed `check` and the master FAILs only on the floor, report it as a metric limit, show the band
  numbers, and ask the creator to listen to the pauses on headphones. Never call it fixed without that.

**Everything else:** silence under the voice by default; a sound needs a cause on screen: typing in R8 (0.22), a cursor click (0.28), a logo pop
(0.30), the verdict stamp (0.35). Never a whoosh under copy. `<audio id=...>` at the root, every one with an id; normalise
to -3 dBFS, align the transient. Music: none baked in; the user adds licensed music in Instagram Edits.

## Traps that waste a render

- **HDR in, grey out; tonemap only, too light:** Stage 1, always.
- **Glass faded through an ancestor's opacity loses its blur:** clip-path reveals only (`lgIn`/`lgOut`).
- **A fromTo renders its from-state on a backward seek:** lgIn starts from a zero-area clip so nothing peeks early.
- **Two tweens on one element's opacity strobe:** a row inside a panel that pops on its word must not also be a `[data-c]`
  child the panel fades in (add an empty `<span data-c>` to the panel instead).
- **The second `<video>` on `input-video.mp4` does not paint;** every timed element needs `class="clip"`;
  `data-has-audio="true"` on `#bg-video`; no CSS transforms on anything GSAP moves (use the `rotate`/`translate` props).
- **Fonts:** only Inter and JetBrains Mono (bundled by the renderer).
- **Windows:** `$PY=python`; quote paths; `npx` through a shell; ffmpeg `drawtext` needs a `fontfile`; a Windows path in a
  filtergraph is quoted with the colon escaped (`file='C\:/...'`); pass `-nostdin` to ffmpeg inside loops that read stdin.
- **4K on an 8 GB PC:** x264 with automatic threads and ffmpeg's default 12 filter threads run out of memory at
  2160x3840@60 ("Generic error in an external library", "Cannot allocate memory", HEVC "Could not find ref"). Every 4K
  encode uses `-x264-params threads=4:rc-lookahead=10` (the conform also caps `-threads 4 -filter_threads 2`); renders
  use `--workers 1`; close other heavy apps and never run two 4K jobs at once.
- **FFmpeg 9 removed `-filter_complex_script`:** `-/filter_complex file.txt`.
- **iPhone files are VFR and rotated:** the conform fixes both; never `-c copy` a phone file into `public/`.
- **Snapshots are seconds, renders are minutes:** read `snaps/sheet.png` before every render.
- **ffmpeg's `-ac 1` downmix adds identical channels** (+3 dB, fake clipping at 1.25): measure stereo by averaging the
  channels yourself (`audio-polish.py` does).
- **`afftdn`'s `nf` is not the measured dBFS floor:** set to the measured -66 it removed ~1.5 dB; `nf=-50` removed 12-20 dB
  with the speech level unchanged.
- **One `-movflags` per ffmpeg output:** a second one silently replaces the first (`+write_colr` lost, untagged colour).
- **An ffmpeg `select` over ~100+ frame numbers fails to parse:** decode once and pick frames in Python (verify-render).

Added 2026-10-11 (aotw-01, each one cost real time):
- **A heavy job in the foreground freezes the Claude app** (twice: skin-match over 42 4K takes, then a pop-up question
  during a job). Every conform, cut, render or 4K scan goes through `bg-job.ps1` (detached, BelowNormal priority, logs to
  a file, watched by a Monitor); checkpoints are asked in plain text.
- **A render stalls when anything else decodes 4K** ("Sequential drawElement capture stalled: no frame progress for
  60000 ms", at frame 1849/1880, while cover frames were being grabbed). Nothing else runs during a render; a stall is
  re-run as is.
- **`xfade` hands x264 4:4:4 frames** (the source became `yuv444p`; `color-check` refused it): `format=yuv420p` at the end
  of the filtergraph or `-pix_fmt yuv420p` (take-cut.py does both).
- **A GSAP timeline is a thenable:** Playwright's `waitForFunction(() => window.__timelines.reel)` waits forever for the
  paused timeline to "resolve". Return a boolean: `() => !!(window.__timelines && ...)`.
- **`audio-polish apply` skips a file tagged "audio-polish"** and re-applying to polished audio stacks the chain: restore
  the original audio from the raw take with `-map_metadata -1`, then apply once.
- **The transcriber's tokens change between runs** ("mess up" then "mess-up." as one word): anchor lookups normalize
  (lowercase, strip punctuation and hyphens) and fail loudly when a phrase is missing.
- **Re-encoding `input-video.mp4` makes `beat-check` call the transcript stale** (mtime). If only the pixel format
  changed and the audio was copied, `touch transcript.json`; otherwise re-transcribe.
- **Shell quoting:** heredocs through Git Bash mangled `\b` (into a backspace) and `\n` in inline Python. Write helper
  scripts to a file and run them; never edit a skill script through an inline heredoc with backslashes.

## Sourcing assets

- **Dummy data:** a CSV/XLSX of 20-40 fictional rows in `$W/assets/demo-data/`, used by both the recording and R9.
- **Tool logos:** the brand's press kit or its site's `<svg>`; white variants for dark glass. Kept in `$SK/assets/`
  (none ship with the skill).
- **Stock:** Pexels, portrait, real people, no readable logos, nobody looking into the lens.
- **Screen recordings:** crop to the window, blur anything personal, `broll-conform.py --size 880x...` into an L window.
- **Fictional domains in diagrams:** `*.example` (reel-1: `ai-ads-portal.example`), never a guessed real domain.

## Teardown (learning from reels that work)

Every few reels: `$PY "$SK/scripts/teardown.py" --video <file> --out "$KIT/video-projects/_teardown/<ref>/"` on a file the
user downloaded themselves (never scrape Instagram). Count by eye: seconds to the first change, changes per 10 s, face
time, panel sizes, caption style, where the CTA lands. Each real gap becomes one rule here.

## Keeping the skill yours

- After every delivery: the note → fix the composition (one number) or the rule (one line) → snapshot → render.
- After every reel: update "The fast path" times with what this one really took, and turn each re-render's cause into
  a check or a default (aotw-01's became take-cut.py, hold-check.mjs and cover-frames.py).
- **"Save this to the skill":** one plain rule in the right section; look changes also go into `STYLE-GUIDE.md` and
  `template/reel.css`. A contradicting rule replaces the old one.
- **A result the user calls great becomes a reference:** `$SK/reference/<slug>/` with its `index.html` (reel-specific CSS
  reduced to overrides, reusable components moved into `template/reel.css`), any capture data, and a `NOTES.md` (beat
  sheet, the numbers, gate results). Prove the move changed nothing: snapshot the original and the reference at 6-8 beats
  and compare with `ffmpeg -lavfi psnr` (reel-1 v3: identical, PSNR inf, at all 8). Then update "The approved baseline".
- Your denylist (`$SK/private/denylist.txt`) never goes into a shared copy of this skill; share the empty template.
