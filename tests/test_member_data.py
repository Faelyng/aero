import json
import os
import tempfile
import unittest

from data.member_data import load_members, member_label, find_by_label

SAMPLE = {
    "san_luis_obispo_county_sheriff_aero_squadron": {
        "membership_roster": {
            "directory": {
                "general_membership": [
                    {
                        "badge": "A-10",
                        "name": "Chris Anderson",
                        "contact": {"phone": ["(805)704-4779 (C)", "(805)543-2626 (B)"]},
                        "aircraft": [
                            {"model": "Carbon Cub", "registration": "N716PM", "color": "Black and Red", "airport": "KSBP"}
                        ],
                    }
                ],
                "emeritus_members": [
                    {"badge": "A-23", "name": "James Cromwell", "contact": {"phone": ["(406)992-4035"]}}
                ],
                "honorary_members": [{"name": "Matthew Frank"}],
            }
        }
    }
}


class TestMemberData(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            json.dump(SAMPLE, f)

    def tearDown(self):
        os.remove(self.path)

    def test_flattens_all_categories(self):
        members = load_members(self.path)
        self.assertEqual(len(members), 3)
        names = {m["name"] for m in members}
        self.assertEqual(names, {"Chris Anderson", "James Cromwell", "Matthew Frank"})

    def test_normalizes_contact_and_aircraft(self):
        anderson = next(m for m in load_members(self.path) if m["name"] == "Chris Anderson")
        self.assertEqual(anderson["mobile_phone"], "(805)704-4779 (C)")
        self.assertEqual(anderson["aircraft"][0]["registration"], "N716PM")
        self.assertEqual(anderson["category"], "general_membership")

    def test_label_and_lookup(self):
        members = load_members(self.path)
        self.assertEqual(member_label(members[0]), "Chris Anderson (A-10)")
        self.assertEqual(member_label({"name": "Matthew Frank", "badge": None}), "Matthew Frank")
        found = find_by_label(members, "James Cromwell (A-23)")
        self.assertEqual(found["name"], "James Cromwell")

    def test_missing_file_returns_empty(self):
        self.assertEqual(load_members("/nonexistent/roster.json"), [])


if __name__ == "__main__":
    unittest.main()
