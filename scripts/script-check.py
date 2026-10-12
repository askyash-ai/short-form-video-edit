#!/usr/bin/env python3
"""script-check.py: the numbers on a reel script before anyone records it. Claude still writes the judgement
(SCRIPT-REVIEW.md: the hook, the open loop, the payoff, 3 hook variants); this gives it facts to stand on.

  length    estimated runtime at the creator's pace (reel-1: 119 words in 44.8 s = 2.66 words/s, --wps): FAIL over 90 s,
            WARN outside 30-60 s
  hook      line 1 over 12 words WARN (the promise must land by ~1.5 s; 12 words is ~4.5 s spoken)
  lines     a line over 25 words WARN: hard to deliver in one clean take, split it (one line = one take)
  numbers   lines with digits, listed: say them exactly as they should appear on screen
  tone      "Step one / step two / step three" (or "Step 1"): WARN. Counting steps out loud turns the creator into a
            lecturer; on aotw-01 (2026-10-11) the creator heard their own "Step one... Step two..." as "a little aggressive".
            Say it like a coworker ("First I drop in...", "Then it...", "And the part I like..."); the screen can still
            number the steps.
  keyword   --keyword WORD: spoken in the last two lines (FAIL otherwise); WARN when it has a common sound-alike that a
            transcriber or a viewer will mishear (reel-1: "safe" was heard as "save"), or is under 4 letters

Script format: the kit's markdown table (its "Line" column), or one spoken line per line of the file; blank lines, "#" headings and lines in [brackets] (directions)
are skipped. Usage: python script-check.py --script W/assets/script.md [--keyword SAFE] [--wps 2.66]
"""
import argparse, re, sys

SOUNDALIKES = {
    "safe": "save", "save": "safe", "edit": "edits / ed it", "lead": "led", "flow": "flo / though", "sheet": "she", "data": "dater",
    "prompt": "promptly", "tool": "two / cool", "list": "lisp", "fix": "six / fics", "copy": "coffee", "free": "three",
    "guide": "guy", "plan": "plane", "build": "billed", "code": "coat / goad", "map": "nap", "check": "chuck",
    "steps": "stepps", "file": "while", "mail": "male", "sale": "sail", "week": "weak", "right": "write",
}
ap = argparse.ArgumentParser()
ap.add_argument("--script", required=True)
ap.add_argument("--keyword")
ap.add_argument("--wps", type=float, default=2.66, help="words per second (reel-1: 2.66)")
a = ap.parse_args()

raw = open(a.script, encoding="utf-8").read().splitlines()
# the kit's scripts are a markdown table (| Clip | Line | Delivery note |): read its "Line" column when there is one
cells = [[c.strip() for c in l.strip().strip("|").split("|")] for l in raw if l.strip().startswith("|")]
head = next((i for i, r in enumerate(cells) if any(c.lower() in ("line", "script", "spoken", "says") for c in r)), None)
if head is not None:
    col = next(j for j, c in enumerate(cells[head]) if c.lower() in ("line", "script", "spoken", "says"))
    lines = [r[col] for r in cells[head + 1:] if len(r) > col and not re.fullmatch(r":?-{2,}:?", r[col])]
else:
    lines = [l.strip().lstrip("-*0123456789.) ").strip() for l in raw]
    lines = [l for l in lines if l and not l.startswith("#") and not (l.startswith("[") and l.endswith("]"))]
lines = [re.sub(r"[*_`]", "", l).strip() for l in lines if l.strip()]
words = lambda s: re.findall(r"[A-Za-z0-9][A-Za-z0-9'%$.,-]*", s)
fails = warns = 0
def say(lvl, area, msg):
    global fails, warns
    print("%-4s %-8s %s" % (lvl, area, msg)); fails += lvl == "FAIL"; warns += lvl == "WARN"

if not lines:
    say("FAIL", "script", "no spoken lines found in %s" % a.script); sys.exit(1)
n = [len(words(l)) for l in lines]
total, est = sum(n), sum(n) / a.wps
say("FAIL" if est > 90 else "WARN" if not 30 <= est <= 60 else "ok", "length",
    "%d words in %d lines = ~%.0f s at %.2f words/s (brand: 30-60 s)" % (total, len(lines), est, a.wps))
say("WARN" if n[0] > 12 else "ok", "hook", "line 1 is %d words (~%.1f s): \"%s\"" % (n[0], n[0] / a.wps, lines[0][:90]))
for i, (l, k) in enumerate(zip(lines, n), 1):
    if k > 25:
        say("WARN", "lines", "line %d is %d words (~%.0f s): split it, one line = one take" % (i, k, k / a.wps))
for i, l in enumerate(lines, 1):
    if re.search(r"\d", l):
        say("ok", "numbers", "line %d: %s  -> say it exactly as it should read on screen" % (i, ", ".join(re.findall(r"[$]?\d[\d,.%]*\w*", l))))
steps = [i for i, l in enumerate(lines, 1) if re.search(r"\bstep (one|two|three|four|five|[1-9])\b", l, re.I)]
if steps:
    say("WARN", "tone", "\"Step one / step two\" on line%s %s: reads as a lecture (\"a little aggressive\", aotw-01). "
        "Say it the way you'd tell a coworker: \"First I...\", \"Then it...\", \"And the bit I like...\"; let the screen number the steps"
        % ("s" if len(steps) > 1 else "", ", ".join(map(str, steps))))
if a.keyword:
    kw = a.keyword.lower()
    tail = " ".join(lines[-2:]).lower()
    say("ok" if re.search(r"\b%s\b" % re.escape(kw), tail) else "FAIL", "keyword",
        "\"%s\" %s the last two lines" % (a.keyword, "is in" if re.search(r"\b%s\b" % re.escape(kw), tail) else "is NOT in"))
    if kw in SOUNDALIKES:
        say("WARN", "keyword", "\"%s\" sounds like \"%s\": say it slowly and clearly, or pick a word with no twin" % (a.keyword, SOUNDALIKES[kw]))
    if len(kw) < 4:
        say("WARN", "keyword", "\"%s\" is short: easy to mistype in a comment and to mishear" % a.keyword)
print("\nper line: " + " | ".join("%d: %dw ~%.1fs" % (i, k, k / a.wps) for i, k in enumerate(n, 1)))
print("%s%s" % ("PASS" if not fails else "%d FAIL" % fails, ", %d WARN" % warns if warns else ""))
sys.exit(1 if fails else 0)
