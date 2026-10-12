"""The cut chain on synthetic transcripts and audio: paper-cut, hand-cut, patch-cut, cutlist-to-edl, phrase-times,
tighten-cut, sliver, edge-audit and dead-air."""
import os
import unittest

from .helpers import load, needs_ffmpeg, read, run, scratch, speech_wav, words_json, write


def timed(text, start, step=0.3):
    """'a b c.' -> [(word, start, end)] one word every `step` s."""
    return [(w, round(start + i * step, 3), round(start + i * step + step * 0.8, 3)) for i, w in enumerate(text.split())]


class PaperCut(unittest.TestCase):
    def cut(self, items, duration=20.0):
        d = scratch(self)
        tr = words_json(os.path.join(d, "tx.json"), items)
        r = run("paper-cut.py", "--transcript", tr, "--duration", duration, "--out-dir", d)
        self.assertEqual(r.returncode, 0, r.stderr)
        return load(os.path.join(d, "cut-list.json")), read(os.path.join(d, "PAPER-CUT.md"))

    def reasons(self, cl):
        return [r["reason"] for r in cl["removed"]]

    def test_restart_inside_a_sentence(self):
        cl, md = self.cut(timed("So the tool, the tool reads every take.", 1.0))
        restart = [r for r in cl["removed"] if r["reason"] == "restart"]
        self.assertEqual(len(restart), 1)
        self.assertEqual(restart[0]["text"], "the tool,")
        self.assertTrue(any(abs(s["start"] - (1.9 - 0.15)) < 0.01 for s in cl["kept"]), cl["kept"])
        self.assertIn("~~the tool,~~  [restart]", md)

    def test_retake_keeps_the_last(self):
        cl, _ = self.cut(timed("This is my first line.", 1.0) + timed("This is my first line.", 4.0))
        self.assertTrue(any(r.startswith("retake (kept the later take at 4.0s)") for r in self.reasons(cl)))
        self.assertAlmostEqual(cl["kept"][0]["start"], 4.0 - 0.25, places=2)   # the first kept line gets the 0.25 s head

    def test_filler_only_retake_keeps_the_clean_one(self):
        cl, _ = self.cut(timed("Here is the trick.", 1.0) + timed("So here is the trick.", 4.0))
        self.assertTrue(any("with a filler in front" in r for r in self.reasons(cl)))
        self.assertAlmostEqual(cl["kept"][0]["start"], 1.0 - 0.25, places=2)

    def test_marker_removes_itself_and_the_flub(self):
        items = timed("I said the wrong number.", 1.0) + timed("Scratch that.", 4.0) + timed("The answer is forty two.", 6.0)
        cl, _ = self.cut(items)
        self.assertIn('marker: "Scratch that."', self.reasons(cl))
        self.assertIn('flub before "Scratch that."', self.reasons(cl))
        self.assertAlmostEqual(cl["kept"][0]["start"], 6.0 - 0.25, places=2)

    def test_false_start(self):
        cl, _ = self.cut(timed("So I", 1.0) + timed("So I wanted to show you this.", 3.0))
        self.assertIn("false start", self.reasons(cl))

    def test_long_pause_is_trimmed(self):
        cl, _ = self.cut(timed("We open the file", 1.0) + timed("then it reads every take.", 4.0))
        self.assertEqual(len(cl["kept"]), 2)
        self.assertTrue(any(r.startswith("silence") for r in self.reasons(cl)))

    def test_speech_chunks_set_the_ends(self):
        d = scratch(self)
        tr = words_json(os.path.join(d, "tx.json"), timed("A short clean line.", 1.0))
        sp = write(os.path.join(d, "speech.json"), {"timebase": "30/1", "chunks": [[0, 28, 99999], [28, 69, 1], [69, 600, 99999]]})
        r = run("paper-cut.py", "--transcript", tr, "--duration", 20, "--out-dir", d, "--speech", sp)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertAlmostEqual(load(os.path.join(d, "cut-list.json"))["kept"][-1]["end"], 69 / 30, places=2)


class HandCut(unittest.TestCase):
    def setUp(self):
        self.d = scratch(self)
        self.tr = words_json(os.path.join(self.d, "tx.json"), timed("one two three.", 1.0) + timed("four five six.", 4.0))
        self.sp = write(os.path.join(self.d, "speech.json"), {"timebase": "100/1", "chunks": [[0, 95, 99999], [95, 190, 1],
                                                                                              [190, 395, 99999], [395, 490, 1], [490, 2000, 99999]]})

    def test_keeps_only_the_listed_lines(self):
        r = run("hand-cut.py", "--transcript", self.tr, "--speech", self.sp, "--duration", 20, "--out-dir", self.d, "--keep", "4.0-4.6")
        self.assertEqual(r.returncode, 0, r.stderr)
        cl = load(os.path.join(self.d, "cut-list.json"))
        self.assertTrue(cl["hand_cut"])
        self.assertEqual(len(cl["kept"]), 1)
        self.assertAlmostEqual(cl["kept"][0]["start"], 3.85, places=2)
        self.assertAlmostEqual(cl["kept"][0]["end"], 4.9, places=2)
        self.assertIn("four five six.", read(os.path.join(self.d, "PAPER-CUT.md")))

    def test_a_time_that_is_not_a_word_start_fails(self):
        r = run("hand-cut.py", "--transcript", self.tr, "--speech", self.sp, "--duration", 20, "--out-dir", self.d, "--keep", "2.5-4.6")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("2.50 is not a word start", r.stderr)


# three kept pieces of a 14 s take: source 2-4, 6-9 and 11-12 s, i.e. flat 0-2, 2-5 and 5-6 s
PIECES = [(2.0, 4.0), (6.0, 9.0), (11.0, 12.0)]


class PatchCut(unittest.TestCase):
    def setUp(self):
        folder = scratch(self)
        self.cut_list = write(os.path.join(folder, "cut-list.json"),
                              {"source_duration": 14.0, "kept": [dict(start=a, end=b) for a, b in PIECES]})
        flat, rows = 0.0, []
        for a, b in PIECES:
            rows.append(dict(src_start=a, src_end=b, flat_start=flat, flat_end=flat + (b - a)))
            flat += b - a
        write(os.path.join(folder, "cut-map.json"), {"segments": rows, "flat_duration": flat, "cuts": [r["flat_start"] for r in rows[1:]]})

    def patch(self, *args):
        return run("patch-cut.py", "--cut-list", self.cut_list, *args)

    def pieces(self):
        return [(p["start"], p["end"]) for p in load(self.cut_list)["kept"]]

    def test_flat_ranges_map_back_to_the_source(self):
        table = {
            "1.6-2.3": [(2.0, 3.6), (6.3, 9.0), (11.0, 12.0)],               # across the first join: both sides shrink
            "3.0-3.5": [(2.0, 4.0), (6.0, 7.0), (7.5, 9.0), (11.0, 12.0)],   # inside the middle piece: it splits
        }
        original = read(self.cut_list)
        for flat, expected in table.items():
            with self.subTest(flat=flat):
                write(self.cut_list, original)
                result = self.patch("--drop-flat", flat)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.pieces(), expected)

    def test_a_leftover_shorter_than_min_keep_is_removed(self):
        result = self.patch("--drop-flat", "5.05-6.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.pieces(), PIECES[:2])
        self.assertIn("sliver at 11.000", result.stdout)

    def test_invalid_ranges_change_nothing(self):
        original = read(self.cut_list)
        problems = {"3-2": "give two numbers", "x-1": "give two numbers", "-1-2": "outside the flat duration", "5-7": "outside the flat duration"}
        for flat, message in problems.items():
            with self.subTest(flat=flat):
                result = self.patch("--drop-flat=" + flat)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
        self.assertEqual(read(self.cut_list), original)

    def test_a_cut_map_from_another_cut_list_is_refused(self):
        write(self.cut_list, {"kept": [dict(start=2.0, end=4.0), dict(start=6.5, end=9.0), dict(start=11.0, end=12.0)]})
        result = self.patch("--drop-flat", "0.5-0.7")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("made from a different cut list", result.stderr)

    def test_drop_by_source_time_and_add_requirements(self):
        self.assertEqual(self.patch("--drop", "11.1").returncode, 0)
        self.assertEqual(self.pieces(), PIECES[:2])
        result = self.patch("--add", "1-2")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--add needs --transcript and --speech", result.stderr)

class SmallTools(unittest.TestCase):
    def test_cutlist_to_edl(self):
        d = scratch(self)
        plan_file = os.path.join(d, "plan.json")
        cl = write(plan_file, {"source_duration": 10.0, "kept": [{"start": 1.0, "end": 4.0}, {"start": 6.0, "end": 8.0}],
                                                      "removed": [{"start": 4.0, "end": 6.0, "reason": "retake", "text": "say it again"}]})
        r = run("cutlist-to-edl.py", "--cut-list", cl, "--out", os.path.join(d, "edl.json"))
        self.assertEqual(r.returncode, 0, r.stderr)
        edl = load(os.path.join(d, "edl.json"))
        self.assertEqual([(x["start"], x["end"]) for x in edl["delete_ranges"]], [(0.0, 1.0), (4.0, 6.0), (8.0, 10.0)])
        self.assertEqual(edl["delete_ranges"][1]["reasons"], ["retake: say it again"])
        self.assertEqual(edl["edited_duration"], 5.0)

    def test_phrase_times(self):
        d = scratch(self)
        tr = words_json(os.path.join(d, "tx.json"), [("Every", 1.0, 1.2), ("Mess-up.", 1.3, 1.8), ("Comment", 5.0, 5.3), ("SKILL", 5.4, 5.8)])
        r = run("phrase-times.py", "--transcript", tr, "every mess up", "comment skill", "not said")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, r"every mess up\s+1\.00-1\.80")
        self.assertRegex(r.stdout, r"comment skill\s+5\.00-5\.80")
        self.assertRegex(r.stdout, r"not said\s+NOT FOUND")


@needs_ffmpeg
class AudioEdges(unittest.TestCase):
    """Synthetic 'speech' = a loud tone at 1.0-2.0 s and 3.5-4.5 s over quiet room tone."""

    def setUp(self):
        self.d = scratch(self)
        self.wav = speech_wav(os.path.join(self.d, "take.wav"), [(1.0, 2.0), (3.5, 4.5)], 6.0)
        self.tr = words_json(os.path.join(self.d, "tx.json"), [("Hello", 1.0, 1.5), ("there.", 1.5, 2.0), ("Second", 3.5, 4.0), ("line.", 4.0, 4.5)])

    def test_tighten_trims_air_and_splits_long_silence(self):
        cl = write(os.path.join(self.d, "cut-list.json"), {"source_duration": 6.0, "kept": [{"start": 0.2, "end": 5.6}]})
        out = os.path.join(self.d, "tight.json")
        r = run("tighten-cut.py", "--audio", self.wav, "--cut-list", cl, "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        kept = load(out)["kept"]
        self.assertEqual(len(kept), 2, kept)
        self.assertAlmostEqual(kept[0]["start"], 0.93, delta=0.04)
        self.assertAlmostEqual(kept[1]["end"], 4.61, delta=0.04)

    def test_sliver_drops_a_segment_with_no_speech(self):
        cl = write(os.path.join(self.d, "cut-list.json"), {"kept": [{"start": 0.9, "end": 2.1}, {"start": 2.5, "end": 3.0}, {"start": 3.4, "end": 4.6}]})
        r = run("sliver.py", "--cut-list", cl, "--audio", self.wav, "--fix")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("never reaches speech level", r.stdout)
        self.assertEqual(len(load(cl)["kept"]), 2)

    def test_edge_audit_finds_and_fixes_a_mid_sound_start(self):
        # the segment starts inside the tail of the first (dropped) line; its first kept word is "Second" at 3.5
        cl = write(os.path.join(self.d, "cut-list.json"), {"kept": [{"start": 1.9, "end": 4.6}]})
        r = run("edge-audit.py", "--audio", self.wav, "--cut-list", cl, "--transcript", self.tr)
        self.assertIn("seg 0 starts mid-sound at 1.90", r.stdout)
        r = run("edge-audit.py", "--audio", self.wav, "--cut-list", cl, "--transcript", self.tr, "--fix")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertAlmostEqual(load(cl)["kept"][0]["start"], 3.5 - 0.08, delta=0.03)   # in the room tone just ahead of "Second"
        r = run("edge-audit.py", "--audio", self.wav, "--cut-list", cl, "--transcript", self.tr)
        self.assertIn("1 segments, 0 issues", r.stdout)

    def test_dead_air_plans_the_long_pause_down_to_target(self):
        write(os.path.join(self.d, "transcript.json"), read(self.tr))
        os.replace(self.wav, os.path.join(self.d, "audio.wav"))
        r = run("dead-air.py", self.d, "--plan", "--max", "0.30", "--max-sentence", "0.25", "--target", "0.12")
        self.assertEqual(r.returncode, 0, r.stderr)
        plan = [line for line in r.stdout.splitlines() if line.startswith("PLAN")][0]
        drops = [tuple(float(x) for x in p.split("-")) for p in plan.split("--drop-flat ")[1:]]
        inner = [p for p in drops if 2.0 < p[0] < 3.5]
        self.assertEqual(len(inner), 1, plan)
        self.assertAlmostEqual(inner[0][1] - inner[0][0], 1.5 - 0.12, delta=0.03)
        self.assertTrue(any(p[0] == 0.0 for p in drops), "the 1 s head should be trimmed")


if __name__ == "__main__":
    unittest.main()
