#!/usr/bin/env python3
"""cover-logo.py: put a tool's app tile (white rounded square + its logo) inside make-cover.mjs's glass card, right
aligned. aotw-01 (2026-10-11): the creator asked for the Claude logo on the cover; the Claude spark is in
$SK/assets/<tool>-logo.png (add your own). The card is make-cover's default (960x264 at (60,290)); pass --card if --top moved it.
Keep the title to the left two thirds (2 short lines) so the tile never covers a word.

  python cover-logo.py --cover W/renders/cover.png --logo $SK/assets/<tool>-logo.png [--out W/renders/cover.png]
"""
import argparse
from PIL import Image, ImageDraw, ImageFilter

ap = argparse.ArgumentParser()
ap.add_argument("--cover", required=True); ap.add_argument("--logo", required=True); ap.add_argument("--out")
ap.add_argument("--card", default="60,290,960,264", help="x,y,w,h of the glass card")
ap.add_argument("--size", type=int, default=156)
a = ap.parse_args()
cover = Image.open(a.cover).convert("RGBA"); logo = Image.open(a.logo).convert("RGBA")
cx, cy, cw, ch = map(int, a.card.split(",")); S = a.size; R = round(S * 0.244)
x, y = cx + cw - 40 - S, cy + (ch - S) // 2
sh = Image.new("RGBA", cover.size, (0, 0, 0, 0))
ImageDraw.Draw(sh).rounded_rectangle([x, y + 10, x + S, y + S + 10], R, fill=(4, 10, 20, 110))
cover = Image.alpha_composite(cover, sh.filter(ImageFilter.GaussianBlur(14)))
k = 4
tile = Image.new("RGBA", (S * k, S * k), (0, 0, 0, 0))
ImageDraw.Draw(tile).rounded_rectangle([0, 0, S * k - 1, S * k - 1], R * k, fill=(255, 255, 255, 255))
tile = tile.resize((S, S), Image.LANCZOS)
lw = int(S * 0.68); lh = int(logo.height * lw / logo.width)
tile.alpha_composite(logo.resize((lw, lh), Image.LANCZOS), ((S - lw) // 2, (S - lh) // 2))
cover.alpha_composite(tile, (x, y))
cover.convert("RGB").save(a.out or a.cover)
print("tile %dpx at (%d,%d) -> %s" % (S, x, y, a.out or a.cover))
