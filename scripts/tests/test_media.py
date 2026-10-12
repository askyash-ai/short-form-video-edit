"""The ffmpeg-based tools on generated media: apply-cut, verify-render, broll-conform, teardown, screen-activity and
ingest."""
import os
import random
import subprocess
import unittest
from fractions import Fraction

from .helpers import ffmpeg, load, needs_ffmpeg, probe, read, run, scratch, words_json, write

# BT.709 written into the H.264 stream itself (VUI), which is what players and ffprobe read
TAG_709 = ["-bsf:v", "h264_metadata=colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1"]


def clip(path, seconds, size="320x180", rate=30, tags=True, audio=True, black_frames=None):
    """A test-pattern clip with a tone. black_frames=(first, count) splices pure black frames in at that frame."""
    graph = "[0:v]null[pic]"
    if black_frames:
        first, count = black_frames
        w, h = size.split("x")
        graph = ("[0:v]split[a][b];[a]trim=end_frame=%d[head];[b]trim=start_frame=%d,setpts=PTS-STARTPTS[tail];"
                 "color=black:s=%sx%s:r=%d,trim=end_frame=%d[gap];[head][gap][tail]concat=n=3:v=1:a=0[pic]"
                 % (first, first + count, w, h, rate, count))
    cmd = ["-f", "lavfi", "-i", "testsrc2=size=%s:rate=%d:duration=%s" % (size, rate, seconds)]
    if audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=330:sample_rate=48000:duration=%s" % seconds]
    cmd += ["-filter_complex", graph, "-map", "[pic]"] + (["-map", "1:a", "-c:a", "aac"] if audio else [])
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-b:v", "1M", "-pix_fmt", "yuv420p"] + (TAG_709 if tags else []) + [path]
    ffmpeg(*cmd)
    return path


@needs_ffmpeg
class ApplyCut(unittest.TestCase):
    def test_ninety_off_grid_pieces(self):
        folder = scratch(self)
        source = clip(os.path.join(folder, "take.mp4"), 50, size="160x90")
        rng, pieces, t = random.Random(11), [], 0.41
        for _ in range(90):           # enough pieces that the filter graph goes through a file
            n = rng.uniform(0.2, 0.4)
            pieces.append(dict(start=round(t, 3), end=round(t + n, 3)))
            t += n + rng.uniform(0.04, 0.15)
        cut_list = write(os.path.join(folder, "cut-list.json"), {"kept": pieces})
        flat = os.path.join(folder, "public", "input-video.mp4")
        result = run("apply-cut.py", "--cut-list", cut_list, "--input", source, "--out", flat, "--preset", "ultrafast")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("verified:", result.stdout)

        cut_map = load(os.path.join(folder, "cut-map.json"))
        lengths, _ = probe(flat)
        frames = sum(row["frames"] for row in cut_map["segments"])
        self.assertEqual(Fraction(frames, 30), Fraction(cut_map["flat_duration"]).limit_denominator(30))
        self.assertLess(abs(lengths["video"] - frames / 30), 1 / 30 + 1e-6)
        self.assertLess(abs(lengths["audio"] - lengths["video"]), 0.12)
        self.assertEqual(cut_map["cuts"], [row["flat_start"] for row in cut_map["segments"][1:]])
        on_grid = [abs(row["src_start"] * 30 - round(row["src_start"] * 30)) < 0.01 for row in cut_map["segments"]]
        self.assertTrue(all(on_grid))

    def test_pieces_under_a_frame_are_refused(self):
        folder = scratch(self)
        cut_list = write(os.path.join(folder, "cut-list.json"), {"kept": [dict(start=1.0, end=1.01)]})
        result = run("apply-cut.py", "--cut-list", cut_list, "--input", clip(os.path.join(folder, "take.mp4"), 2),
                     "--out", os.path.join(folder, "flat.mp4"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("at least one frame", result.stderr)


@needs_ffmpeg
class VerifyRender(unittest.TestCase):
    def setUp(self):
        self.folder = scratch(self)
        self.index = write(os.path.join(self.folder, "public", "index.html"),
                           '<div data-composition-id="verify" id="comp" data-duration="6" data-start="0">\n'
                           '  <div class="card-host clip" id="hook" data-start="1.000" data-duration="2" data-anchor="x"></div>\n</div>\n')
        self.report = os.path.join(self.folder, "check", "VERIFY.md")

    def verify(self, render, *extra):
        result = run("verify-render.py", "--render", render, "--res", "320x180", "--index", self.index, "--out", self.report, *extra)
        return result, read(self.report)

    def test_a_good_render_passes_with_all_sheets(self):
        result, report = self.verify(clip(os.path.join(self.folder, "good.mp4"), 6))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("**PASS**", report)
        self.assertIn("page 1 row 1: 1.00 s in hook", report)
        made = set(os.listdir(os.path.join(self.folder, "check")))
        self.assertTrue({"render-sheet.png", "render-dense-01.png", "render-transitions-01.png"} <= made, made)

    def test_failures_are_caught(self):
        cases = [
            ("flash", dict(black_frames=(90, 2)), ["| Black frames | FAIL |", "3.000 - 3.067 s (0.067 s, 2 frames): flash"]),
            ("untagged", dict(tags=False), ["| Colour tags | FAIL |"]),
        ]
        for name, options, expected in cases:
            with self.subTest(name=name):
                result, report = self.verify(clip(os.path.join(self.folder, name + ".mp4"), 6, **options))
                self.assertEqual(result.returncode, 1, result.stdout)
                for line in expected:
                    self.assertIn(line, report)

    def test_a_word_lost_at_a_join(self):
        said = "comment skill for the template".split()
        heard = "Comment skill for template.".split()
        flat = words_json(os.path.join(self.folder, "flat.json"), [(w, 0.4 * i, 0.4 * i + 0.3) for i, w in enumerate(said)])
        render_words = words_json(os.path.join(self.folder, "heard.json"), [(w, 0.4 * i, 0.4 * i + 0.3) for i, w in enumerate(heard)])
        result, report = self.verify(clip(os.path.join(self.folder, "good.mp4"), 6), "--kept", flat, "--words", render_words)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("**the**", report)

@needs_ffmpeg
class BrollConform(unittest.TestCase):
    def setUp(self):
        self.folder = scratch(self)

    def conform(self, source, *options):
        target = os.path.join(self.folder, "broll", os.path.splitext(os.path.basename(source))[0] + "-v.mp4")
        return run("broll-conform.py", "--in", source, "--out", target, *options), target

    def test_landscape_clip_with_sound_becomes_silent_vertical_hd30(self):
        result, target = self.conform(clip(os.path.join(self.folder, "wide.mp4"), 5, size="1280x720", rate=24),
                                      "--hd", "--fps", "30", "--start", "0.5", "--dur", "3")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        lengths, total = probe(target)
        self.assertEqual(set(lengths), {"video"})
        self.assertLess(abs(total - 3.0), 0.05)
        self.assertRegex(result.stdout, r"1080x1920, 30/1 fps")
        self.assertTrue(os.path.isfile(target + ".sheet.png"))

    def test_still_image_push_in_has_the_requested_length(self):
        still = os.path.join(self.folder, "board.png")
        ffmpeg("-f", "lavfi", "-i", "testsrc2=s=800x800", "-frames:v", "1", still)
        result, target = self.conform(still, "--dur", "2", "--hd")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertLess(abs(probe(target)[1] - 2.0), 0.05)
        self.assertNotEqual(self.conform(still, "--hd")[0].returncode, 0)          # a still without --dur is refused

    def test_duration_beyond_the_clip_is_refused(self):
        result, _ = self.conform(clip(os.path.join(self.folder, "two.mp4"), 2, audio=False), "--hd", "--dur", "5")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("is longer than the", result.stderr)


@needs_ffmpeg
class Teardown(unittest.TestCase):
    SKIPPED = [(75, 90), (200, 216), (290, 303)]        # frame numbers dropped from a 12 s stand-in -> three jump cuts

    @staticmethod
    def stand_in(path, frames):
        """A talking-head stand-in drawn with numpy: a smooth blotchy 'head' sliding 0.5 px a frame across a grey wall,
        plus fresh sensor noise every frame. Skipping frame numbers makes jump cuts that barely move the picture."""
        import numpy as np
        rng = np.random.default_rng(7)
        grid = rng.uniform(40, 220, (6, 5))
        wide = np.array([np.interp(np.linspace(0, 4, 70), np.arange(5), row) for row in grid])          # 6 x 70
        head = np.array([np.interp(np.linspace(0, 5, 90), np.arange(6), col) for col in wide.T]).T      # 90 x 70
        video, cols = bytearray(), np.arange(320, dtype=float)
        for n in frames:
            img = np.full((180, 320), 106.0)
            u = cols - (60 + 0.5 * n)                      # sub-pixel position: a smooth slide, like a slow drift on camera
            on = (u >= 0) & (u <= 69)
            for r in range(90):
                img[45 + r, on] = np.interp(u[on], np.arange(70), head[r])
            img += rng.normal(0, 2, img.shape)
            video += np.clip(img, 0, 255).astype(np.uint8).tobytes()
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "gray", "-s", "320x180", "-r", "30",
                        "-i", "-", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", path], input=bytes(video), check=True)

    def test_detects_subtle_jump_cuts_and_reports(self):
        folder = scratch(self)
        shown = [n for n in range(360) if not any(lo <= n <= hi for lo, hi in self.SKIPPED)]
        video = os.path.join(folder, "standin.mp4")
        self.stand_in(video, shown)
        joins_at = [k / 30 for k in range(1, len(shown)) if shown[k] - shown[k - 1] > 1]
        spoken = words_json(os.path.join(folder, "spoken.json"), [("word.", 0.6 + 0.5 * k, 0.9 + 0.5 * k) for k in range(16)])
        report_dir = os.path.join(folder, "teardown")
        result = run("teardown.py", "--video", video, "--transcript", spoken, "--out", report_dir)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        report = load(os.path.join(report_dir, "report.json"))
        found = report["cuts"]
        self.assertEqual(len(found), 3, found)
        self.assertTrue(all(abs(f - j) <= 1 / 30 + 1e-3 for f, j in zip(found, joins_at)), (found, joins_at))
        self.assertLess(max(c["diff"] for c in report["cut_detail"]), 40)   # a fixed 40/255 threshold would see none
        self.assertEqual(report["first_word"], 0.6)
        notes = read(os.path.join(report_dir, "TEARDOWN.md"))
        self.assertIn("## Count by eye from the sheets", notes)
        self.assertIn("sheet_01.png", notes)

        side_by_side = os.path.join(folder, "side.md")
        self.assertEqual(run("teardown.py", "--compare", os.path.join(report_dir, "report.json"), "--out", side_by_side).returncode, 0)
        self.assertIn("| Hard cuts / min |", read(side_by_side))

@needs_ffmpeg
class ScreenAndIngest(unittest.TestCase):
    def test_screen_activity_sees_motion_not_a_still_page(self):
        d = scratch(self)
        path = os.path.join(d, "screen.mp4")
        ffmpeg("-f", "lavfi", "-i", "color=c=white:s=640x360:r=30:d=4", "-f", "lavfi", "-i", "color=c=black:s=200x100:r=30:d=4",
               "-filter_complex", "[0][1]overlay=x='if(gte(t,2),40+100*t,40)':y=100", "-c:v", "libx264", "-preset", "ultrafast", path)
        out = os.path.join(d, "activity.json")
        r = run("screen-activity.py", "--video", path, "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        series = load(out)
        still = [v for t, v in series if t < 1.5]
        moving = [v for t, v in series if t >= 2.5]
        self.assertLess(max(still), 1.5)
        self.assertGreater(min(moving), 1.5)

    def test_ingest_orders_sets_aside_and_joins(self):
        d = scratch(self)
        raw = os.path.join(d, "raw")
        os.makedirs(raw)
        clip(os.path.join(raw, "IMG_0002.mp4"), 2)
        clip(os.path.join(raw, "IMG_0001.mp4"), 3)
        clip(os.path.join(raw, "screen.mp4"), 1, size="640x360")
        r = run("ingest.py", "--raw", raw, "--out", d, "--concat")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        info = load(os.path.join(d, "ingest.json"))
        self.assertEqual([c["file"] for c in info["clips"]], ["IMG_0001.mp4", "IMG_0002.mp4"])
        self.assertEqual([c["file"] for c in info["set_aside"]], ["screen.mp4"])
        self.assertEqual(info["clips"][1]["source_start"], info["clips"][0]["duration"].__round__(3))
        self.assertTrue(info["concat"]["stream_copy"])
        self.assertAlmostEqual(probe(os.path.join(d, "source.mp4"))[1], 5.0, delta=0.1)


if __name__ == "__main__":
    unittest.main()
