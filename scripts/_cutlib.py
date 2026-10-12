"""_cutlib.py: shared helpers for the cut and check scripts (transcripts, speech chunks, audio levels, ffprobe).

Levels are RMS of 16-bit samples (0-32767) with the channels averaged, measured in 10 ms frames, so a threshold such as
300 means the same thing for every script and every sample rate: a quiet room sits around 5-80, speech around 1000+.
"""
import json
import os
import re
import subprocess
import sys

FRAME = 0.01  # seconds per level frame


def fail(msg, code=1):
    """Print to stderr and exit non-zero (argparse style)."""
    print(msg, file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------- transcripts
def load_words(path):
    """Word list [{text, start, end}] sorted by start, from any of: a plain list, {"words": [...]} (ElevenLabs, the
    normalized shape), or whisper-style {"segments": [{"words": [...]}]}. Spacing / non-word entries are dropped."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        items = data.get("words")
        if items is None:
            items = [w for seg in data.get("segments", []) for w in seg.get("words", [])]
    else:
        items = data
    out = []
    for w in items:
        if w.get("type", "word") != "word":
            continue
        text = str(w.get("text", w.get("word", ""))).strip()
        if not text or "start" not in w:
            continue
        start = float(w["start"])
        out.append({"text": text, "start": start, "end": float(w.get("end", start))})
    out.sort(key=lambda w: w["start"])
    return out


_TOKEN = re.compile(r"[a-z0-9']+")


def tokens(text):
    """Lowercase word tokens; punctuation and hyphens split or vanish ("mess-up." -> ["mess", "up"])."""
    return _TOKEN.findall(str(text).lower().replace("’", "'"))


def key(text):
    """One comparison key per transcript word ("Mess-up." -> "messup")."""
    return "".join(tokens(text))


def ends_sentence(text):
    return str(text).rstrip().endswith((".", "?", "!"))


# ---------------------------------------------------------------- auto-editor speech chunks
def load_speech(path):
    """auto-editor v1 JSON ({"timebase": "30/1", "chunks": [[from, to, speed], ...]}) -> [(start_s, end_s)] of speech.
    A chunk with speed 99999 (or 0) is silence."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    num, _, den = str(data.get("timebase", "30/1")).partition("/")
    rate = float(num) / float(den or 1)
    return [(a / rate, b / rate) for a, b, speed in data["chunks"] if speed not in (0, 99999)]


# ---------------------------------------------------------------- ffprobe
def probe(path, entries="stream=codec_type,width,height,r_frame_rate,duration:format=duration"):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", entries, "-of", "json", path],
                       capture_output=True, text=True)
    if r.returncode:
        fail("ffprobe could not read %s: %s" % (path, r.stderr.strip()[-300:]))
    return json.loads(r.stdout)


def stream(info, kind):
    return next((s for s in info.get("streams", []) if s.get("codec_type") == kind), None)


def rate_of(s, default=30.0):
    """r_frame_rate "60000/1001" -> 59.94."""
    num, _, den = str((s or {}).get("r_frame_rate", "")).partition("/")
    try:
        r = float(num) / float(den or 1)
        return r if r > 0 else default
    except ValueError:
        return default


# ---------------------------------------------------------------- audio levels
class Audio:
    """Decoded audio (channels averaged) with level helpers. Reads any file ffmpeg can (wav, mp4, mov)."""

    def __init__(self, path, sr=16000):
        import numpy as np
        self.np = np
        info = probe(path, "stream=codec_type,channels")
        a = stream(info, "audio")
        if a is None:
            fail("no audio stream in %s" % path)
        ch = int(a.get("channels") or 1)
        raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", path, "-map", "0:a:0", "-ar", str(sr),
                              "-f", "s16le", "-acodec", "pcm_s16le", "-"], capture_output=True).stdout
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
        x = x[: len(x) // ch * ch].reshape(-1, ch).mean(axis=1)
        self.sr, self.x = sr, x
        hop = int(sr * FRAME)
        n = len(x) // hop
        self.frames = np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(axis=1)) if n else np.zeros(0)
        self.duration = len(x) / sr

    def level(self, t0, t1):
        """RMS between two times (at least one sample)."""
        a = max(0, int(t0 * self.sr))
        b = max(a + 1, int(t1 * self.sr))
        seg = self.x[a:b]
        return float(self.np.sqrt((seg ** 2).mean())) if len(seg) else 0.0

    def idx(self, t):
        return int(round(t / FRAME))

    def runs(self, mask, i0=0, i1=None):
        """[(first, last)] frame-index runs where mask is true, inside [i0, i1)."""
        i1 = len(mask) if i1 is None else min(i1, len(mask))
        out, start = [], None
        for i in range(max(0, i0), i1):
            if mask[i] and start is None:
                start = i
            elif not mask[i] and start is not None:
                out.append((start, i - 1))
                start = None
        if start is not None:
            out.append((start, i1 - 1))
        return out


# ---------------------------------------------------------------- cut lists
def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path, data):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)


def total(segments):
    return round(sum(s["end"] - s["start"] for s in segments), 3)


def merge(segments, join_gap=0.12, min_len=0.2, duration=None):
    """Sort, clamp, drop pieces under min_len, and join pieces that nearly touch."""
    out = []
    for s in sorted(segments, key=lambda s: s["start"]):
        a = max(0.0, s["start"])
        b = s["end"] if duration is None else min(duration, s["end"])
        if b - a < min_len:
            continue
        if out and a - out[-1]["end"] < join_gap:
            out[-1]["end"] = max(out[-1]["end"], b)
        else:
            out.append({"start": a, "end": b})
    return [{"start": round(s["start"], 3), "end": round(s["end"], 3)} for s in out]


def gaps(kept, duration):
    """The stretches of [0, duration] not covered by kept segments."""
    out, cursor = [], 0.0
    for s in sorted(kept, key=lambda s: s["start"]):
        if s["start"] > cursor + 0.001:
            out.append((round(cursor, 3), round(s["start"], 3)))
        cursor = max(cursor, s["end"])
    if duration - cursor > 0.001:
        out.append((round(cursor, 3), round(duration, 3)))
    return out
