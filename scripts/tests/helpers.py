"""What the tests share: calling a script the way the skill does, throwaway folders, and synthetic media.
Paths hang off this file's location, so the tests work wherever the skill folder lives."""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT_DIR = HERE.parent
needs_ffmpeg = unittest.skipIf(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                               "needs ffmpeg and ffprobe on PATH")


def run(script, *args):
    """Run one of the skill's Python scripts with the interpreter running the tests."""
    command = [sys.executable, str(SCRIPT_DIR / script), *map(str, args)]
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")


def scratch(case):
    """A temporary folder removed when the test finishes."""
    folder = tempfile.mkdtemp(prefix="sfve-")
    case.addCleanup(shutil.rmtree, folder, ignore_errors=True)
    return folder


def write(path, content):
    """Write text, or anything else as JSON, creating folders; returns the path."""
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return str(target)


def read(path):
    return pathlib.Path(path).read_text(encoding="utf-8")


def load(path):
    return json.loads(read(path))


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *map(str, args)], check=True)


def probe(path):
    """Returns ({"video": seconds, "audio": seconds}, container seconds)."""
    info = json.loads(subprocess.check_output(["ffprobe", "-loglevel", "error", "-of", "json",
                                               "-show_entries", "format=duration:stream=codec_type,duration", str(path)]))
    lengths = {s["codec_type"]: float(s["duration"]) for s in info.get("streams", []) if "duration" in s}
    return lengths, float(info["format"]["duration"])


def speech_wav(path, spans, total, rate=48000):
    """Faint room noise throughout, with a loud steady tone standing in for speech inside each (start, end) span."""
    gate = "+".join("between(t,%.3f,%.3f)" % s for s in spans) or "0"
    ffmpeg("-f", "lavfi", "-i", "sine=f=220:sample_rate=%d:duration=%.3f" % (rate, total),
           "-f", "lavfi", "-i", "anoisesrc=c=white:a=0.0005:r=%d:d=%.3f" % (rate, total),
           "-filter_complex", "[0]volume='if(%s,0.5,0)':eval=frame[v];[v][1]amix=inputs=2:normalize=0" % gate,
           "-c:a", "pcm_s16le", path)
    return path


def words_json(path, items):
    """[(text, start, end), ...] -> a {"words": [...]} transcript file."""
    return write(path, {"words": [dict(text=t, start=s, end=e) for t, s, e in items]})
