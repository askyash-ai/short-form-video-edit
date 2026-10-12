"""beat-check.py against a small fixture: "Comment" is spoken at 5.0 s, and cards are placed around it."""
import os
import time
import unittest

from .helpers import run, scratch, words_json, write

SPOKEN = [("So", 4.4, 4.6), ("comment", 5.0, 5.3), ("SKILL.", 5.4, 5.9), ("Mess-up", 8.0, 8.4), ("tags.", 8.5, 8.9)]


class BeatCheck(unittest.TestCase):
    def setUp(self):
        self.root = scratch(self)
        self.page = os.path.join(self.root, "public", "index.html")
        self.words = words_json(os.path.join(self.root, "transcript.json"), SPOKEN)
        self.video = os.path.join(self.root, "public", "input-video.mp4")

    def compose(self, *elements, video="older"):
        """Write the composition; video = "older" (transcript is current), "newer" (stale) or None (no video)."""
        write(self.page, '<div id="root" data-composition-id="t" data-start="0" data-duration="12.000">\n'
                         '<video id="bg-video" class="clip" src="input-video.mp4" data-start="0" data-duration="12"></video>\n'
                         '%s\n</div>\n' % "\n".join(elements))
        if video:
            write(self.video, "")
            now = time.time()
            os.utime(self.words, (now - 50, now - 50))
            stamp = now - 100 if video == "older" else now
            os.utime(self.video, (stamp, stamp))

    def check(self, *extra):
        return run("beat-check.py", "--index", self.page, "--transcript", self.words, *extra)

    @staticmethod
    def cta(start, extra='data-anchor="Comment SKILL"', name="cta"):
        return '<div class="card-host clip" id="%s" data-start="%s" data-duration="3" %s></div>' % (name, start, extra)

    def test_entry_window_around_the_word(self):
        cases = {4.75: "OK", 5.05: "OK", 4.2: "EARLY", 5.2: "LATE"}
        for start, verdict in cases.items():
            with self.subTest(start=start):
                self.compose(self.cta(start))
                result = self.check()
                self.assertEqual(result.returncode, 0 if verdict == "OK" else 1, result.stdout)
                self.assertRegex(result.stdout, r"\ncta\s.*\s%s\s" % verdict)

    def test_list_item_anchor_is_matched_loosely(self):
        self.compose('<div class="item" id="tag" data-at="7.80" data-anchor="mess up tags"></div>')
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertRegex(result.stdout, r"tag\s+7\.80@\s+8\.00\s+\+0\.20\s+OK")

    def test_unknown_words_are_reported(self):
        self.compose(self.cta(4.75, 'data-anchor="link in bio"'))
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn(" MISS ", result.stdout)

    def test_missing_anchor_on_a_card_or_a_cutaway(self):
        for element in (self.cta(4.75, ""), '<video id="broll-1" class="clip" src="b.mp4" data-start="6" data-duration="2"></video>'):
            with self.subTest(element=element[:30]):
                self.compose(element)
                result = self.check()
                self.assertEqual(result.returncode, 1)
                self.assertIn("NO-ANCHOR", result.stdout)

    def test_data_unanchored_opts_out(self):
        self.compose(self.cta(0.2, "data-unanchored"))
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue(result.stdout.rstrip().splitlines()[-1].startswith("0 checked"))

    def test_suggestions(self):
        self.compose(self.cta(5.2), self.cta(4.4, "", name="loose"))
        out = self.check("--suggest").stdout
        self.assertRegex(out, r'cta\s+data-start="4\.75"')
        self.assertIn('data-anchor="so comment skill"', out)

    def test_old_transcript_fails_unless_allowed(self):
        self.compose(self.cta(4.75), video="newer")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("predates input-video.mp4", result.stdout)
        self.assertEqual(self.check("--allow-stale").returncode, 0)

    def test_without_a_video_the_age_check_is_skipped(self):
        self.compose(self.cta(4.75), video=None)
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("staleness not checked", result.stdout)


if __name__ == "__main__":
    unittest.main()
