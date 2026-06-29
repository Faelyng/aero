import unittest

import tkinter as tk

from ui.desktop_ui import MissionFormApp


def _make_root():
    """Create a Tk root, or return None if no display is available."""
    try:
        return tk.Tk()
    except tk.TclError:
        return None


class TestUI(unittest.TestCase):
    def setUp(self):
        self.root = _make_root()
        if self.root is None:
            self.skipTest("no display available")
        self.app = MissionFormApp(self.root)

    def tearDown(self):
        if self.root is not None:
            self.root.destroy()

    def test_builds_all_fields(self):
        # Every entry field key the form filler expects should exist.
        self.assertIn("pilot_name_badge", self.app.vars)
        self.assertIn("aircraft_id", self.app.vars)
        self.assertEqual(len(self.app.mission_vars), 9)

    def test_member_autofill(self):
        member = {
            "name": "Chris Anderson",
            "badge": "A-10",
            "mobile_phone": "(805)704-4779 (C)",
            "aircraft": [
                {"registration": "N716PM", "model": "Carbon Cub", "color": "Black and Red", "airport": "KSBP"}
            ],
        }
        self.app.members = [member]
        self.app._member_labels = ["— None —", "Chris Anderson (A-10)"]
        self.app.pilot_var.set("Chris Anderson (A-10)")
        self.assertEqual(self.app.vars["pilot_name_badge"].get(), "Chris Anderson, A-10")
        self.assertEqual(self.app.vars["aircraft_id"].get(), "716PM")
        self.assertEqual(self.app.vars["aircraft_model"].get(), "Carbon Cub")

    def test_collect_includes_checkboxes(self):
        self.app.mission_vars["routine_airborne_patrol"].set(True)
        data = self.app.collect()
        self.assertIn("routine_airborne_patrol", data["mission_type"])
        self.assertIn("freq_control20", data)


if __name__ == "__main__":
    unittest.main()
