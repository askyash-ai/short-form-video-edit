# Style guide (short-form video)

The look this skill builds. Change a row here and tell Claude "update the short-form-video-edit skill to match"; it updates
`SKILL.md` and the tokens in `template/reel.css`. Where this guide and the skill disagree on the look, this guide wins. **This is the author's look: change any row to make it yours.**

**Mood:** a well-run ops dashboard floating on your own footage. Competent, clear, data-first: a coworker showing you
something useful, not a hype reel. **Approved baselines:** **aotw-01 v4** (2026-10-11, "This version is good") for the
cut, the camera, the timing and the tool graphics (`reference/aotw-01-v4/`), and **reel-1 v3** (2026-10-07, "This video
output was great") for the news formats (`reference/reel-1-v3/`). New reels start from their choices.

## Your voice (the script)

| | |
|---|---|
| Tone | a coworker explaining something over your shoulder: contractions, everyday words, one small personal moment |
| Steps | **never counted out loud** ("Step one, step two..." read as "a little aggressive", 2026-10-11): "First I just...", "then it...", "and the bit I like..."; the screen numbers them |
| Energy | the hook and the payoff carry it; the rest is relaxed and warm, never brisk or barked |
| Claims | only what you will really say on the day, with numbers you will really have |

## You on camera

| | |
|---|---|
| Skin tone | **what the camera recorded, plus a very small lift (+2 points), never under 63% (a dim shoot is lifted to it), identical on every take** (`skin-match.mjs` → `conform-iphone.mjs --skin-target`; preview first with `--preview`) |
| Skin colour | **the recorded colour, kept**: a lift greys skin, so its saturation is restored to the recorded value; never boosted past it ("lighten up a bit but should not look fake", 2026-10-11) |
| Colour | the footage's own colour, as the phone shows it (recorded with HDR Video off), no contrast or saturation boost; never washed out, never fake. Target "C + colour kept" (provisional, tuned on the next reel) |
| Face time | 50-60% of the reel; only large panels may cover the face |
| Delivery | **the iPhone source's own quality: 4K (2160x3840) at 60 fps by default, or HD (1080x1920) at 30 fps**; never downscaled (4K60 since 2026-10-07, HD30 allowed since 2026-10-11) |
| Voice | cleaned and levelled per take (rumble, room and harsh "s" down, -20 LUFS each), mastered to -14 LUFS / -1 dBTP; the room never jumps at a cut |

## Colours

| Token | Hex | Role |
|---|---|---|
| `--ops-accent` | `#2dd4bf` | teal: fills (keyword chip, ✓, PASS), glass under-glow |
| `--ops-accent-2` | `#5eead4` | light teal: accent text on glass, the active caption word |
| `--ops-warn` / text `#fcd34d` | `#f59e0b` | amber: risk, HALF, the stakes highlighter |
| `--ops-danger` / text `#fca5a5` | `#ef4444` | red: late, failed, fake, FAIL only |
| `--ops-text` | `#f8fafc` | text on glass |
| `--glass-tint` | `rgba(14,24,44,.64)` default | smoked navy; per reel, darken the footage's own dominant tone (reel-1: the hoodie → `rgba(24,38,68,.64)`) |

On glass, text uses the light tints (teal `#5eead4`, amber `#fcd34d`, red `#fca5a5`); the saturated colours are for fills.
One accent word per line. Red is never decoration.

## Liquid glass

| | |
|---|---|
| Material | smoked blur of the footage (blur 20, saturate 1.7, brightness .72) + a faint refraction, a bright specular rim on the top edge, soft inner glow, teal under-glow |
| Radius | 34 px panels, full pills for S |
| Entrance | grows from nothing → droplet pill → panel (0.62 s, expo.out), lifts 26 px, one sheen sweep, then content in order |
| Exit | back into a pill and closed, into the end of its window |
| Behind L panels | the footage dims (navy radial wash) |

## Sizes

| | Max | Where | Face |
|---|---|---|---|
| S | 560 x 132 | beside or above the head | never covers it |
| M | 960 wide, fits above the head | the top zone | never covers it |
| L | 880 x 1000 | x 60-940, y 250-1290 | may cover it, with the dim |

## Type

| | |
|---|---|
| Headlines | Inter 900, 66 px, -1.5 px tracking |
| Captions | Inter 900, 70 px, white with a dark shadow; the spoken word lights teal; 1-3 words a group; y 1320-1500 |
| Numbers, eyebrows, URLs | JetBrains Mono, tabular digits; eyebrows 27 px / 800 / letter-spaced |

## Motion and camera

| | |
|---|---|
| Pace | a visual change every 2-4 s (panel motion counts); 30-60 s total |
| Overshoot | only the verdict stamp, the hook's payoff word and chips (`back.out`) |
| Cuts | **smooth** (2026-10-11): a pause trimmed inside a take is a 0.08 s dissolve; only a new take is a hard cut |
| Camera | origin at the eye line; **a gentle reframe only where a new take starts** (1.00 ↔ 1.08 on 4K, 1.00 ↔ 1.06 on HD); one or two **eased pushes** (+0.03 over 0.7 s) on payoff words; no snaps, no zoom-out mid-line, no moves under L panels |
| Payoffs | the last thing each card shows stays readable ≥ 0.6 s before the card closes |

## Sources, tools and B-roll

Real news pages captured as they are (phone layout), the spoken phrase highlighted, outlet + date on screen. Tools shown
as themselves: the tool's own chat window (Claude: light, the spark) with the real command and real files, and app-tile
pipelines ("raw in, edit out"); the tool's logo next to its name. AI B-roll shows a scene, never a presenter or proof,
and is always labelled "AI info" on Instagram. Every number on screen measures exactly the claim it sits under.

## Cover

**A frame the creator picks** from a numbered sheet of relaxed moments (word ends, not mid-word), a light navy wash, one
liquid-glass M card above the head: eyebrow (the series tag) + the promise in 2 lines / 6 words, one accent word, and the
tool's app tile on the right when the reel is about a tool (aotw-01: the Claude tile). Inside both crops Instagram makes
of it (4:5 feed y 285-1635, 3:4 grid y 240-1680). `cover-frames.py`, `make-cover.mjs`, `cover-logo.py`.

## Sound

Silence under the voice; typing, clicks, a logo pop and the verdict stamp only when something on screen makes them. No
whooshes. Music, if any, added in Instagram Edits from its licensed library.
