import json
import os
import sys
import shutil
from pathlib import Path


def _default_roster_path() -> str:
    if getattr(sys, "frozen", False):
        # Keep the roster next to the executable so it survives app updates and
        # onefile re-extractions.  On first launch the bundled copy is seeded there.
        exe_dir = Path(sys.executable).parent
        target = exe_dir / "AeroRoster20260127.json"
        if not target.exists():
            bundled = Path(getattr(sys, "_MEIPASS", exe_dir)) / "AeroRoster20260127.json"
            if bundled.exists():
                shutil.copy2(bundled, target)
        return str(target)
    return str(Path(__file__).resolve().parent.parent / "AeroRoster20260127.json")


DEFAULT_ROSTER_PATH = _default_roster_path()

# Aircraft owned by the squadron and available to any qualified pilot.
SQUADRON_AIRCRAFT = [
    {
        "registration": "N805SL",
        "model": "Cessna 182R",
        "seats": "4 Place",
        "weight_class": "HW",
        "color": "",
        "base_hangar": "KSBP, HANGAR N1-9",
    },
]

# The roster JSON nests members under a fixed path. Categories preserve which
# group a member belongs to so the UI can label/group them if desired.
_ROOT_KEY = "san_luis_obispo_county_sheriff_aero_squadron"
CATEGORIES = ("general_membership", "emeritus_members", "honorary_members")


_EMPTY_EC = {"name": "", "relationship": "", "phone": ""}


def _parse_emergency_contact(raw) -> dict:
    """Normalise emergency contact to {name, relationship, phone}.
    Accepts the structured dict form or a legacy flat string.
    """
    if not raw:
        return dict(_EMPTY_EC)
    if isinstance(raw, dict):
        return {
            "name":         raw.get("name", ""),
            "relationship": raw.get("relationship", ""),
            "phone":        raw.get("phone", ""),
        }
    # Legacy flat string: "BAMBI (SPOUSE) 408/348-2278"
    import re
    m = re.match(r'^(.*?)\s*\(([^)]+)\)\s*([\d/\-\(\) ]+)$', str(raw).strip())
    if m:
        return {"name": m.group(1).strip(), "relationship": m.group(2).strip(), "phone": m.group(3).strip()}
    m2 = re.search(r'([\d/\-]{7,})$', str(raw).strip())
    if m2:
        return {"name": str(raw)[:m2.start()].strip(), "relationship": "", "phone": m2.group(1).strip()}
    return {"name": str(raw).strip(), "relationship": "", "phone": ""}


def _directory(roster):
    return (
        roster.get(_ROOT_KEY, {})
        .get("membership_roster", {})
        .get("directory", {})
    )


def load_roster(file_path=DEFAULT_ROSTER_PATH):
    """Return the raw roster JSON, or an empty dict if the file is missing."""
    if not os.path.exists(file_path):
        return {}
    with open(file_path, "r") as f:
        return json.load(f)


def _normalize(entry, category):
    """Flatten a roster entry into the shape the UI/form consume."""
    contact = entry.get("contact", {})
    phones = contact.get("phone", []) or []
    return {
        "badge": entry.get("badge", ""),
        "name": entry.get("name", ""),
        "rank": entry.get("rank", ""),
        "role": entry.get("role", ""),
        "phones": phones,
        "mobile_phone": next((p for p in phones if "(C)" in p), phones[0] if phones else ""),
        "email": contact.get("email", ""),
        "emergency_contact": _parse_emergency_contact(contact.get("emergency_contact")),
        "address": entry.get("address", ""),
        "aircraft": entry.get("aircraft", []) or [],
        "category": category,
    }


def load_members(file_path=DEFAULT_ROSTER_PATH):
    """Load and flatten all roster members across every category."""
    directory = _directory(load_roster(file_path))
    members = []
    for category in CATEGORIES:
        for entry in directory.get(category, []):
            members.append(_normalize(entry, category))
    return members


def member_label(member):
    """Human-readable label for a dropdown, e.g. 'Chris Anderson (A-10)'."""
    badge = member.get("badge")
    return f"{member['name']} ({badge})" if badge else member["name"]


def find_by_label(members, label):
    return next((m for m in members if member_label(m) == label), None)


def validate_roster(file_path) -> tuple[bool, str, int]:
    """Check that a file is a parseable roster JSON with the expected structure.

    Returns (ok, message, member_count).
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return False, f"Could not read file: {e}", 0

    directory = _directory(data)
    if not directory:
        return False, "File does not match the expected roster structure.", 0

    count = sum(len(directory.get(c, [])) for c in CATEGORIES)
    if count == 0:
        return False, "No members found in the roster.", 0

    return True, f"Found {count} members.", count


def import_roster(source_path, dest_path=DEFAULT_ROSTER_PATH):
    """Validate and install source_path as the active roster.

    Accepts both .json and .pdf files. Returns (ok, message, member_count).
    """
    source_path = str(source_path)

    if source_path.lower().endswith(".pdf"):
        return _import_pdf_roster(source_path, dest_path)

    ok, msg, count = validate_roster(source_path)
    if not ok:
        return False, msg, 0
    shutil.copy2(source_path, dest_path)
    return True, msg, count


def _import_pdf_roster(source_path, dest_path):
    """Parse a roster PDF, write it as JSON, and return (ok, message, count)."""
    try:
        from data.parse_roster_pdf import parse_pdf
        data = parse_pdf(source_path)
    except Exception as e:
        return False, f"PDF parse failed: {e}", 0

    # Validate the parsed structure before writing
    directory = _directory(data)
    if not directory:
        return False, "Parsed PDF did not produce a valid roster structure.", 0

    count = sum(len(directory.get(c, [])) for c in CATEGORIES)
    if count == 0:
        return False, "No members found in the parsed PDF.", 0

    with open(dest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return True, f"Found {count} members.", count
