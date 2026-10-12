"""retime.py W : rebuild W/public/index.html beat timings from W/transcript.json (anchor words) and W/cuts3/plan.json
(hard joins). Starts from W/cuts3/index-v2.html (the approved v2 markup); camera = reframe 1.00 <-> 1.08 at hard joins
only, slow eased pushes on two payoff words; soft (dissolve) cuts get no camera change."""
import json, os, re, subprocess, sys

W = sys.argv[1]
words = json.load(open(os.path.join(W, "transcript.json")))["words"]
plan = json.load(open(os.path.join(W, "cuts3", "plan.json")))
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                            os.path.join(W, "public", "input-video.mp4")], capture_output=True, text=True).stdout)
D = int(dur * 100) / 100.0
toks = [re.sub(r"[^a-z0-9']", "", w["text"].lower()) for w in words]

def ws(phrase, after=0.0):
    """start of the first word of phrase (first match starting at/after `after`)"""
    p = [re.sub(r"[^a-z0-9']", "", x) for x in phrase.lower().split()]
    for i in range(len(toks) - len(p) + 1):
        if toks[i:i + len(p)] == p and words[i]["start"] >= after - 1e-6:
            return round(words[i]["start"], 2)
    raise SystemExit("anchor not found: " + phrase)

J = [round(p["start"], 3) for p in plan[1:]]          # 9 hard joins (take boundaries), flat-cut time
# verify the plan's joins against the picture (find-joins writes joins.json)
fj = json.load(open(os.path.join(W, "joins.json")))["joins"]
for j in J:
    near = min(fj, key=lambda x: abs(x - j)) if fj else None
    if near is None or abs(near - j) > 0.08:
        print("WARN hard join %.3f not matched in joins.json (nearest %s)" % (j, near))
    else:
        J[J.index(j)] = near

T = {}
T["series"] = (0.15, J[0] - 0.03)
T["hook"] = (0.10, 3.55)
T["noted"] = (ws("editor") - 0.06, ws("so I wrote") + 0.16)
T["sop"] = (ws("I wrote"), J[1] - 0.02)
T["step1"] = (ws("step one"), J[2] - 0.01)
T["step2"] = (ws("step two"), ws("step three") + 0.48)
T["three"] = (ws("step three") + 0.02, ws("captions") - 0.06)
T["step3"] = (ws("captions"), ws("before it hands") - 0.12)
T["gates"] = (ws("before it hands"), J[5] - 0.02)
T["qc"] = (ws("it checks every"), ws("then it tells") - 0.14)
T["report"] = (ws("then it tells"), ws("friend") - 0.08)
T["send"] = (ws("friend") - 0.04, ws("drop me") - 0.16)
T["follow"] = (ws("follow") - 0.04, D)
T["cta"] = (ws("comment") - 0.02, D)

html = open(os.path.join(W, "cuts3", "index-v2.html"), encoding="utf-8").read()
for k, (a, b) in T.items():
    html, n = re.subn(r'(<div id="%s" class="card-host[^>]*?data-start=")[\d.]+(" data-duration=")[\d.]+' % k,
                      lambda m: "%s%.2f%s%.2f" % (m.group(1), a, m.group(2), b - a), html)
    assert n == 1, k
html = re.sub(r'(data-composition-id="reel" data-start="0" data-duration=")[\d.]+', r"\g<1>%.2f" % D, html)
html = re.sub(r'(<video id="bg-video"[^>]*?data-duration=")[\d.]+', r"\g<1>%.2f" % D, html, flags=re.S)
html = re.sub(r"const D = [\d.]+;", "const D = %.2f;" % D, html)
html = re.sub(r"lgOut\('#series \.lg', [\d.]+\);", "lgOut('#series .lg', %.2f);" % T["series"][1], html)
html = re.sub(r"lgIn\('#cta \.lg', [\d.]+\);", "lgIn('#cta .lg', %.2f);" % T["cta"][0], html)

base = [1.00, 1.08] * 5                               # per take; reframe only at the 9 hard joins
w = {k: ws(v) for k, v in {"frame": "single frame", "claude": "claude did", "sop": "sop", "drop": "drop in", "retake": "every retake",
                            "mess": "messup", "best": "best take", "cuts": "cuts the", "these": "these graphics",
                            "exact": "exact word", "quality": "quality checks", "every": "every frame", "face": "my face",
                            "insta": "instagram", "tells": "tells me", "couldnt": "couldn't", "follow": "follow"}.items()}
w["frame"] = ws("frame"); w["claude"] = ws("claude did"); w["every"] = ws("every", ws("it checks")); w["mess"] = ws("messup")
w["retake"] = ws("retake"); w["best"] = ws("best"); w["cuts"] = ws("cuts"); w["these"] = ws("these"); w["exact"] = ws("exact")
w["quality"] = ws("quality"); w["face"] = ws("face", ws("it checks")); w["insta"] = ws("instagram"); w["tells"] = ws("tells")
w["couldnt"] = ws("couldn't"); w["drop"] = ws("drop in")

def push(t, s):   # a slow eased push, released by the next cut (no zoom-out mid-line)
    return "tl.to('#video-zoom', { scale: %.2f, duration: 0.7, ease: 'sine.inOut' }, %.2f);" % (s, t)

B = []
B.append("// camera: a reframe only where a new take starts (9 hard joins), 1.00 <-> 1.08; the 10 dissolves inside a take get none")
B.append(" ".join("camSet(%.3f, %.2f);" % (j + 0.003, base[i + 1]) for i, j in enumerate(J)))
B.append("")
B.append("// hook")
B.append("lgIn('#hook .lg', 0.10);")
B.append("pop('#hk-me', 0.20, { y: 10, scale: 0.96 });")
B.append("pop('#hk-me .val', %.2f, { scale: 1.5, y: 0 });" % w["frame"])
B.append("tl.to('#hk-me', { opacity: 0, y: -16, duration: 0.16, ease: 'power2.in' }, %.2f);" % (w["claude"] - 0.14))
B.append("pop('#hk-cl', %.2f, { y: 16, scale: 0.94 });" % w["claude"])
B.append("pop('#hk-cl .val', %.2f, { scale: 1.45, y: 0 });" % (w["claude"] + 0.16))
B.append("lgOut('#hook .lg', %.2f);" % T["hook"][1])
B.append("")
B.append("// line 2")
B.append("lgIn('#noted .lg', %.2f); lgOut('#noted .lg', %.2f);" % T["noted"])
B.append("lgIn('#sop .lg', %.2f);" % T["sop"][0])
B.append("pop('#sop-f', %.2f, { x: -16, scale: 0.96 });" % (T["sop"][0] + 0.16))
wc = ws("claude", T["sop"][0])
B.append("tl.fromTo('#sop-w', { scaleX: 0 }, { scaleX: 1, duration: 0.35, ease: 'power2.inOut' }, %.2f);" % ws("wrote"))
B.append("pop('#sop-t', %.2f, { scale: 0.6, y: 0 });" % wc)
B.append(push(w["sop"] - 0.25, base[1] + 0.03))
B.append("lgOut('#sop .lg', %.2f);" % T["sop"][1])
B.append("")
B.append("// step 1 (L)")
B.append("dim(%.2f, %.2f);" % T["step1"])
B.append("lgIn('#step1 .lg', %.2f);" % T["step1"][0])
B.append("type('#cw-cmd', %.2f, 34);" % (T["step1"][0] + 0.30))
B.append(" ".join("pop('#at%d', %.2f, { y: -40, scale: 0.8 });" % (i + 1, w["drop"] + 0.04 * i) for i in range(12)))
B.append("pop('#cw-n-wrap', %.2f, { y: 6 }); count('#cw-n', %.2f, 42, 0.8);" % (w["drop"], w["drop"]))
B.append(" ".join("pop('#tg%d', %.2f);" % (i + 1, w["retake"] - 0.06 + 0.06 * i) for i in range(4)))
B.append(" ".join("pop('#tg%d', %.2f);" % (i + 5, w["mess"] - 0.06 + 0.06 * i) for i in range(4)))
B.append("tl.to('#cw-send', { scale: 0.84, duration: 0.1, yoyo: true, repeat: 1, ease: 'power2.inOut' }, %.2f);" % (T["step1"][1] - 0.55))
B.append("lgOut('#step1 .lg', %.2f);" % T["step1"][1])
B.append("")
B.append("// step 2 (M)")
B.append("lgIn('#step2 .lg', %.2f);" % T["step2"][0])
B.append("pop('#s2-f', %.2f, { x: -16, scale: 0.96 });" % (T["step2"][0] + 0.30))
B.append("tl.fromTo('#s2-w1', { scaleX: 0 }, { scaleX: 1, duration: 0.35, ease: 'power2.inOut' }, %.2f);" % ws("picks"))
B.append("pop('#s2-t', %.2f, { scale: 0.6, y: 0 });" % w["best"])
B.append("tl.fromTo('#s2-w2', { scaleX: 0 }, { scaleX: 1, duration: 0.35, ease: 'power2.inOut' }, %.2f);" % ws("line"))
B.append("pop('#s2-o', %.2f, { scale: 1.3, y: 0 });" % w["cuts"])
B.append("lgOut('#step2 .lg', %.2f);" % T["step2"][1])
B.append("")
B.append("// step 3")
B.append("lgIn('#three .lg', %.2f); lgOut('#three .lg', %.2f);" % T["three"])
B.append("lgIn('#step3 .lg', %.2f);" % T["step3"][0])
B.append("pop('#s3-cards', %.2f, { scale: 1.2, y: 0 });" % w["these"])
B.append("pop('#s3-sub', %.2f, { y: 10 });" % w["exact"])
B.append("lgOut('#step3 .lg', %.2f);" % T["step3"][1])
B.append("")
B.append("// quality gates")
B.append("lgIn('#gates .lg', %.2f);" % T["gates"][0])
B.append("pop('#g-gates', %.2f, { scale: 1.3, y: 0 }); %s" % (w["quality"], push(w["quality"] - 0.25, base[5] + 0.03)))
B.append("lgOut('#gates .lg', %.2f);" % T["gates"][1])
B.append("")
B.append("// frame check (L)")
B.append("dim(%.2f, %.2f);" % T["qc"])
B.append("lgIn('#qc .lg', %.2f);" % T["qc"][0])
e = w["every"]
B.append("pop('#z1', %.2f, { scale: 1 }); pop('#z2', %.2f, { scale: 1 }); pop('#z3', %.2f, { scale: 1 }); pop('#qk', %.2f, { x: -12 });" % (e, e + .08, e + .16, e + .24))
B.append("pop('#fb', %.2f, { scale: 1.08 }); pop('#q1', %.2f, { x: -20 });" % (w["face"], w["face"] + 0.04))
B.append("pop('#q2', %.2f, { x: -20 });" % w["insta"])
B.append("lgOut('#qc .lg', %.2f);" % T["qc"][1])
B.append("")
B.append("// what it could not check")
B.append("lgIn('#report .lg', %.2f, { stagger: 0 });" % T["report"][0])
B.append("pop('#r1', %.2f, { x: -20 });" % w["tells"])
B.append("pop('#r2', %.2f, { x: -20 });" % ws("what", ws("tells")))
B.append("lgOut('#report .lg', %.2f);" % T["report"][1])
B.append("")
B.append("// share + follow")
B.append("lgIn('#send .lg', %.2f); lgOut('#send .lg', %.2f);" % T["send"])
B.append("lgIn('#follow .lg', %.2f);" % T["follow"][0])
f = w["follow"]
B.append("tl.to('#fw-off', { opacity: 0, duration: 0.12 }, %.2f); tl.set('#fw-off', { opacity: 0 }, %.2f);" % (f + 0.28, T["cta"][0] + 0.03))
B.append("pop('#fw-on', %.2f, { y: 8, scale: 0.9 });" % (f + 0.30))
html = re.sub(r"/\* BEATS:START \*/.*?/\* BEATS:END \*/", lambda m: "/* BEATS:START */\n" + "\n".join(B) + "\n/* BEATS:END */", html, flags=re.S)
open(os.path.join(W, "public", "index.html"), "w", encoding="utf-8").write(html)

# joins.json for reel-check: only the hard joins are framing changes; dissolves are not jump cuts
jj = json.load(open(os.path.join(W, "joins.json")))
soft = [s for p in plan for s in p["soft"]]
json.dump({"video": "input-video.mp4", "fps": 60.0, "joins": J, "scores": [0] * len(J), "soft_dissolves": soft,
           "note": "hard joins only (take boundaries); soft_dissolves are 0.08 s cross-dissolves inside a take, no reframe",
           "find_joins_raw": jj.get("joins")}, open(os.path.join(W, "joins.json"), "w"), indent=1)
print("D=%.2f" % D)
for k, (a, b) in T.items(): print("%-7s %6.2f - %6.2f" % (k, a, b))
print("hard joins", J); print("soft", soft)
