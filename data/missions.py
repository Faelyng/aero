"""Save and load mission form state as JSON files.

Missions are stored as JSON in a `missions/` directory next to the executable
(when frozen/packaged) or next to the project root (during development).
pathlib is used throughout for cross-platform compatibility.
"""

import json
import sys
import uuid
from datetime import datetime
from pathlib import Path


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def missions_dir() -> Path:
    d = _base_dir() / "missions"
    d.mkdir(exist_ok=True)
    return d


def save(form_data: dict, path: Path | None = None) -> Path:
    """Persist form_data to a JSON file. Returns the path written."""
    now = datetime.now()
    if path is None:
        stem = f"{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        path = missions_dir() / f"{stem}.json"
    payload = {
        "meta": {"saved_at": now.isoformat()},
        "form_data": form_data,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load(path: Path) -> dict:
    """Load and return form_data from a saved mission file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("form_data", data)


def list_missions() -> list[tuple[str, Path]]:
    """Return (display_label, path) tuples sorted newest-modified first."""
    files = sorted(
        missions_dir().glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    result = []
    for f in files:
        try:
            fd = json.loads(f.read_text(encoding="utf-8")).get("form_data", {})
            if fd.get("mission_name"):
                label = fd["mission_name"]
            else:
                flight = fd.get("flight_date") or fd.get("flight_datetime", "")
                parts = [flight, fd.get("pilot_name_badge", ""), fd.get("aircraft_id", "")]
                label = "  |  ".join(p for p in parts if p) or f.stem
        except Exception:
            label = f.stem
        result.append((label, f))
    return result
