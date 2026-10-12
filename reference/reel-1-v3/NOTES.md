# reel-1 v3: the approved baseline

**Approved 2026-10-07** ("This video output was great"). **Its colour is superseded (2026-10-11):** next to the phone's
own view of the same takes the creator called it "over bright and saturated"; reuse its layout, arc and pacing, not its
picture (SKILL.md "Colour and skin"). Start every new reel from this build's choices; change them only
when the content needs it or the user asks. The rendered file lives at
`hyperframes-student-kit/video-projects/reel-1-v3/renders/reel-1-v3.mp4`; this folder keeps the composition
(`index.html`, pixel-identical to the approved render with the skill's `template/reel.css` + `reel.js`) and the article
capture boxes (`article.json`), so the reference survives if the kit folder moves.

Topic: fake ChatGPT/Gemini/Claude/Perplexity login pop-ups stealing 2FA codes (one-off, "AI AT WORK · SECURITY").
CTA: Comment SAFE → one-page checklist. 44.8 s, 8 takes (one per script line), 119 words.

## What it is made of

| Time | Size | Format | Anchor | What happens |
|---|---|---|---|---|
| 0.10-4.50 | M | R3 hook card (danger rim) | "fake ChatGPT" | "ALERT · THIS WEEK / 2FA codes stolen"; "stolen" pops on 1.50; punch 1.04 at 2.06 |
| 0.15-3.35 | S | R2 topic tag | - | "AI AT WORK · SECURITY", live teal dot, above the hook card |
| 4.56-10.18 | L | R16 real article | "researchers have found" | BleepingComputer (Oct 6, 2026) in a glass browser: opens on the headline, scrolls to the lede at 5.70, teal marks on "fake ChatGPT, Gemini," (5.98) and "Claude, and Perplexity sites" (7.62), zoom 1.08 at 8.30, amber marks on the MFA phrase (8.84, 9.20) |
| 10.30-17.90 | L | R13 explainer | "the trick" | mock fake site; the Google-looking pop-up drops in on "pop-up" (11.60); amber ring on the URL bar on "address bar" (13.15) and on the padlock on "padlock" (14.02); dashed teal outline (15.90) + "Just HTML in the page" (16.14) on "drawn inside" |
| 17.96-20.22 | M | headline (warn rim) | "so checking the URL" | "So… / Checking the URL / isn't enough" |
| 20.10-21.20 | S | R6 number chip | "two tests" | "2" beside the head, punch 1.06 at 20.30 |
| 21.24-27.66 | L | R14 demo | "one, drag the pop-up" | REAL and FAKE windows with cursors; the real one leaves the browser (23.20) "Leaves the browser ✓", the fake one sticks at the edge (25.62) with a red pulse, "Stuck at the edge ✗" |
| 27.70-29.86 | M | headline (accent rim) | "two, let your password manager" | "TEST 2 / Let your password manager decide" |
| 29.90-33.08 | M | R7 checklist | "it reads the real address" | ✓ "Reads the real address" (30.02), ✗ "No autofill? Close the tab" (31.32) |
| 33.20-38.60 | M (row of S) | R5 pills | "best fix" | "Bookmark it" (34.00), "Don't search" (35.48), "Use a passkey" (36.82); punch 1.05 at 34.12 |
| 38.70-41.80 | S | R5 pill | "send this to a friend" | "Send to a friend" (matches the spoken word, not the script's "coworker") |
| 41.85-44.80 | M | R15 CTA | "comment" | one row "Comment [SAFE]", "the one-page checklist" under it; the face stays clear for the last line |

`dim()` behind every L stretch (4.56-17.90, 21.24-27.66). `camSet(…, 1.0)` on each jump cut (4.543, 21.233, 33.123,
38.663). Captions: 53 groups, active word teal, accent words "fake, two tests, password manager, passkey", keyword chip
"SAFE".

## The numbers that made it work

- **Face visible 56%** of the runtime; L panels 44% (three of them, the longest 7.6 s, never two L back to back without a
  face beat between, except the article → explainer pair that the dim carries as one scene).
- **A visual change every ≤3.1 s** (reel-check, counting motion inside panels); first motion at 0.10 s, the promise on
  screen at 0.10 s.
- **Skin**: recorded 70.5% median across takes → target 72.5% → outputs 72.1-72.6% per take → render median 71.1%.
- **Glass**: tint `rgba(24,38,68,.64)` from the hoodie (rgb 103,137,192, hue 217); eyebrows 27 px / 800 in the light
  tints; the remaining contrast warnings were only the tiny labels inside the mock browser.
- **Panels**: L 880 wide at left 70, top 262 (clear of the like/comment column); M at top 300 (372 under the topic tag),
  960 wide, ending above the face box (180,560,500,740); S beside the head at x 700.
- **Gates** (2026-10-07, the tools of that day): hyperframes check 0 errors; layout-check PASS (12 overlays, S/M all clear
  of the face incl. punches); reel-check PASS; colour PASS (blacks/contrast/saturation within 2 of source); verify-render
  PASS at 1080x1920, 20.3 Mb/s, 44.800 s, A/V 0, no black frames: v3 was rendered at 1080 before 4K60 became the default
  that evening. The 4K60 render of the same edit is reel-1 v4 (`video-projects/reel-1-v4/renders/reel-1-v4-4k60.mp4`:
  2160x3840, 53.6 Mb/s, PASS); re-run verify-render on v3 with `--res 1080x1920`, or it fails on size and bitrate.
  Audio: -14.0 LUFS, -1.4 dBTP.
- **Re-checked with the 2026-10-11 tools (on v4):** audio-polish master gate: room -52.4 dBFS (WARN; the voice was never
  denoised); find-joins: 13 jump cuts, 9 on the same framing either side (reel-check --joins WARN); layout-check across
  every frame: PASS on Instagram, WARN on TikTok / Shorts (L panels and some caption groups to x 950-960); the transition
  sheets show each L entrance droplet as a blob on the face for 2-3 frames. New reels fix the first two by default.

## Reuse

Copy `index.html` into a new reel's `public/` only to borrow markup (an L article, an explainer, a demo, a checklist);
re-time every `data-start` and tween from the new transcript, re-measure the face box and the glass tint, and re-capture
any article. Keep the order of the arc: hook card → source (the real article) → mechanism (explainer) → what to do (tests
/ checklist / pills) → share line → CTA.
