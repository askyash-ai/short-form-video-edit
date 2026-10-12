"""The 2026-10-11 reel tools on synthetic media: audio-polish (apply / check / master), find-joins, script-check."""
import json, os, subprocess, unittest
from .helpers import run, scratch, ffmpeg, write, load, needs_ffmpeg

# "speech": 220 Hz bursts (0.4 s on, 0.2 s off) after 1 s of room; the room is white noise ~-58 dBFS under it
SPEECH = "0.06*sin(2*PI*220*t)*gt(mod(t\\,0.6)\\,0.2)*gt(t\\,1)+0.0018*(2*random(0)-1)"


def take(path, secs=6, gain=1.0):
    ffmpeg("-f", "lavfi", "-i", "testsrc2=s=270x480:r=30", "-f", "lavfi",
           "-i", "aevalsrc=%s*(%s)|%s*(%s):s=48000" % (gain, SPEECH, gain, SPEECH), "-t", str(secs),
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-shortest", path)
    return path


def measure(path):
    r = run("audio-polish.py", "measure", path, "--json")
    return json.loads(r.stdout)[0]


@needs_ffmpeg
class AudioPolish(unittest.TestCase):
    def test_apply_levels_and_cleans_every_take(self):
        d = scratch(self)
        a, b = take(os.path.join(d, "a.mp4")), take(os.path.join(d, "b.mp4"), gain=0.4)   # b ~8 dB quieter
        before = measure(a)
        r = run("audio-polish.py", "apply", "--in-place", a, b)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        ma, mb = measure(a), measure(b)
        for m in (ma, mb):
            self.assertAlmostEqual(m["lufs"], -20, delta=0.6)
            self.assertTrue(m["polished"])
            self.assertEqual(m["clipped"], 0)
        # the room went down relative to the speech (denoise), not just with it
        self.assertLess(ma["floor"] - ma["lufs"], before["floor"] - before["lufs"] - 3)
        self.assertIn("video", subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", a],
                                              capture_output=True, text=True).stdout)
        again = run("audio-polish.py", "apply", "--in-place", a)
        self.assertIn("already polished", again.stdout)
        chk = run("audio-polish.py", "check", a, b)
        self.assertIn("level spread", chk.stdout)

    def test_master_hits_minus_14_with_bt709_tags(self):
        d = scratch(self)
        src, out = take(os.path.join(d, "raw.mp4"), secs=8), os.path.join(d, "final.mp4")
        run("audio-polish.py", "apply", "--in-place", src)
        r = run("audio-polish.py", "master", src, out)
        m = measure(out)
        self.assertAlmostEqual(m["lufs"], -14, delta=1.0, msg=r.stdout + r.stderr)
        self.assertLessEqual(m["true_peak"], -1.0)
        tags = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                               "stream=color_primaries,color_transfer,color_space", "-of", "csv=p=0", out],
                              capture_output=True, text=True).stdout.strip()
        self.assertEqual(tags, "bt709,bt709,bt709")

    def test_check_fails_a_clipped_take(self):
        d = scratch(self)
        hot = take(os.path.join(d, "hot.mp4"), gain=30.0)          # far past full scale: clipped
        r = run("audio-polish.py", "check", hot)
        self.assertEqual(r.returncode, 1)
        self.assertIn("clipped samples", r.stdout)


@needs_ffmpeg
class FindJoins(unittest.TestCase):
    def test_finds_the_one_hard_cut(self):
        d = scratch(self)
        os.makedirs(os.path.join(d, "public"))
        v = os.path.join(d, "public", "input-video.mp4")
        # a slow gradient that drifts (motion, no cut) for 2 s, then a different picture: one jump cut at 2.0 s
        ffmpeg("-f", "lavfi", "-i", "gradients=s=270x480:r=30:speed=0.01:seed=1", "-f", "lavfi",
               "-i", "gradients=s=270x480:r=30:speed=0.01:seed=7", "-filter_complex",
               "[0]trim=0:2,setpts=PTS-STARTPTS[a];[1]trim=0:2,setpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=1[v]",
               "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p", v)
        r = run("find-joins.py", "--video", v)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        joins = load(os.path.join(d, "joins.json"))["joins"]
        self.assertEqual(len(joins), 1, r.stdout)
        self.assertAlmostEqual(joins[0], 2.0, delta=0.05)


class ScriptCheck(unittest.TestCase):
    def table(self, d, last):
        return write(os.path.join(d, "script.md"), "# Reel\n\nTopic notes that are not spoken.\n\n| Clip | Line | Delivery note |\n|---|---|---|\n"
                     "| 01 | Fake login pages are stealing 2FA codes right now. | fast |\n"
                     "| 02 | " + " ".join(["word"] * 60) + " | |\n"
                     "| 03 | %s | |\n" % last)

    def test_reads_the_table_and_finds_the_keyword(self):
        d = scratch(self)
        r = run("script-check.py", "--script", self.table(d, "Comment SAFE and I'll send you the checklist."), "--keyword", "SAFE")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("3 lines", r.stdout)
        self.assertIn("line 2 is 60 words", r.stdout)
        self.assertIn('sounds like "save"', r.stdout)

    def test_fails_when_the_keyword_is_not_said_at_the_end(self):
        d = scratch(self)
        r = run("script-check.py", "--script", self.table(d, "Follow for more."), "--keyword", "SAFE")
        self.assertEqual(r.returncode, 1)
        self.assertIn("is NOT in", r.stdout)

    def test_warns_on_counted_steps(self):
        d = scratch(self)
        path = write(os.path.join(d, "s.md"), "| Clip | Line | Delivery note |\n|---|---|---|\n"
                     "| 1 | Step one, I drop in my raw takes. | |\n| 2 | First it picks the best take. | |\n"
                     "| 3 | Step 3, it builds the captions. | |\n| 4 | Comment SKILL for the file. | |\n")
        r = run("script-check.py", "--script", path, "--keyword", "SKILL")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("WARN tone", r.stdout)
        self.assertIn("lines 1, 3", r.stdout)


if __name__ == "__main__":
    unittest.main()
