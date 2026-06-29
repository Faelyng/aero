"""Calibration helper: dump every word on the template form with its bbox.

Run once to calibrate pdf/form_filler coordinates:
    python3 tools/dump_coords.py

Output columns: x0  x1  top  bottom  "text"
Coordinates are in PDF points, origin top-left (pdfplumber convention).
Page height is printed first so values can be converted to reportlab's
bottom-left origin via: y_rl = page_height - bottom.
"""

import os
import pdfplumber

TEMPLATE = os.path.join(
    os.path.dirname(__file__),
    "..",
    "example",
    "Aircraft Mission Flight Plan Authorization Form 02032026.pdf",
)

with pdfplumber.open(TEMPLATE) as pdf:
    page = pdf.pages[0]
    print(f"PAGE_SIZE width={page.width} height={page.height}")
    for w in page.extract_words():
        print(
            f'{w["x0"]:7.1f} {w["x1"]:7.1f} {w["top"]:7.1f} {w["bottom"]:7.1f}  "{w["text"]}"'
        )
