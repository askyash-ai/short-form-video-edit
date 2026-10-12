"""Tests for short-form-video-edit. All media is generated on the fly; nothing from a real shoot is needed.

From the scripts folder:   python -m unittest tests        (-v lists each test)
Anything needing ffmpeg is skipped when ffmpeg or ffprobe cannot be found.
"""
# `python -m unittest tests` only collects what this package exposes, so every module is pulled in here.
from .test_beat_check import *    # noqa: F401,F403
from .test_cutting import *       # noqa: F401,F403
from .test_media import *         # noqa: F401,F403
from .test_reel_tools import *    # noqa: F401,F403
