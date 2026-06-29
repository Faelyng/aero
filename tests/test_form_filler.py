import os
import tempfile
import unittest

from pdf import form_filler
from pdf.form_filler import MISSION_TYPES, CBX_BOUNDS

try:
    import pdfplumber
    import pypdf  # noqa: F401
    import reportlab  # noqa: F401
    HAVE_PDF_LIBS = True
except ImportError:
    HAVE_PDF_LIBS = False

TEMPLATE = form_filler.TEMPLATE_PATH

ALL_CHECKBOXES = {
    "mission_type": [key for key, _ in MISSION_TYPES],
    "freq_control20": True,
    "freq_other": True,
    "freq_1231": True,
    "notify_email": True,
    "notify_dispatch": True,
}

# Map data flag keys to their CBX_BOUNDS key (needed for non-mission-type boxes).
_FLAG_TO_BOUNDS_KEY = {
    "freq_control20": "freq_control20",
    "freq_other":     "freq_other_box",
    "freq_1231":      "freq_1231",
    "notify_email":   "notify_email",
    "notify_dispatch":"notify_dispatch",
}


@unittest.skipUnless(HAVE_PDF_LIBS, "PDF libraries not installed")
@unittest.skipUnless(os.path.exists(TEMPLATE), "Template PDF missing")
class TestFormFiller(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._out = os.path.join(self._tmpdir, "out.pdf")

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _words(self, path):
        with pdfplumber.open(path) as pdf:
            return pdf.pages[0].extract_words()

    def test_generates_valid_pdf(self):
        form_filler.fill({"mission_type": ["routine_airborne_patrol"]}, self._out)
        self.assertTrue(os.path.exists(self._out))
        with open(self._out, "rb") as f:
            self.assertEqual(f.read(5), b"%PDF-")
        self.assertGreater(os.path.getsize(self._out), 1000)

    def test_text_fields_appear_in_output(self):
        form_filler.fill({
            "request_date": "06292026",
            "flight_datetime": "06302026 0900",
            "pilot_name_badge": "BANYS, A-34",
        }, self._out)
        text = " ".join(w["text"] for w in self._words(self._out))
        self.assertIn("06292026", text)
        self.assertIn("06302026", text)
        self.assertIn("BANYS,", text)

    def test_checkboxes_centered_in_boxes(self):
        """Each selected checkbox's X must land inside the corresponding box bounds."""
        form_filler.fill(ALL_CHECKBOXES, self._out)
        words = self._words(self._out)
        x_marks = [w for w in words if w["text"] == "X"]

        def inside(bounds_key):
            x0, top, x1, bottom = CBX_BOUNDS[bounds_key]
            return any(
                x0 <= w["x0"] and w["x1"] <= x1 + 1 and
                top <= w["top"] and w["bottom"] <= bottom + 1
                for w in x_marks
            )

        for key, _ in MISSION_TYPES:
            with self.subTest(checkbox=key):
                self.assertTrue(inside(key), f"X not inside box for {key}")

        for flag, bounds_key in _FLAG_TO_BOUNDS_KEY.items():
            with self.subTest(checkbox=flag):
                self.assertTrue(inside(bounds_key), f"X not inside box for {flag}")

    def test_unchecked_boxes_have_no_x(self):
        """When no checkboxes are selected, no X marks appear in the checkbox areas."""
        form_filler.fill({}, self._out)
        words = self._words(self._out)
        x_marks = [w for w in words if w["text"] == "X"]
        for key, (x0, top, x1, bottom) in CBX_BOUNDS.items():
            with self.subTest(checkbox=key):
                inside = any(
                    x0 <= w["x0"] and w["x1"] <= x1 + 1 and
                    top <= w["top"] and w["bottom"] <= bottom + 1
                    for w in x_marks
                )
                self.assertFalse(inside, f"Unexpected X in box for {key}")


if __name__ == "__main__":
    unittest.main()
