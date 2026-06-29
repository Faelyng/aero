"""Generate a filled Mission Flight Plan Authorization PDF.

Overlays typed values onto the original blank template (page 1) using
a coordinate table calibrated from the template via tools/dump_coords.py.
Runtime deps: reportlab, pypdf (no pdfplumber needed at runtime).
"""

import io
import os
import textwrap
from reportlab.pdfbase.pdfmetrics import stringWidth

TEMPLATE_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "example",
        "Aircraft Mission Flight Plan Authorization Form 02032026.pdf",
    )
)

# Mission-type checkbox keys in top-to-bottom form order.
MISSION_TYPES = [
    ("routine_airborne_patrol",        "Routine Airborne Patrol"),
    ("ground_search_support",          "Ground Search Support"),
    ("sheriff_surveillance_support",   "Sheriff Surveillance Support"),
    ("aero_squadron_mission_training", "Aero Squadron Mission Training"),
    ("personnel_transportation",       "Personnel Transportation"),
    ("aircraft_systems_flight_check",  "Aircraft/Systems Flight Check"),
    ("maintenance_repositioning",      "Maintenance Repositioning"),
    ("pilot_checkout_qualification",   "Pilot Checkout/Qualification"),
    ("other",                          "Other (Explain)"),
]

# ---------------------------------------------------------------------------
# Coordinate tables — all in ReportLab space (origin bottom-left, y up).
# Derived from pdfplumber dump: y_rl = PAGE_HEIGHT - pdfplumber_bottom + 2
# ---------------------------------------------------------------------------
_H = 792.0

# Single-line text fields: key -> (x, y)
_TEXT = {
    "request_date":          (157, _H - 158.8 + 2),
    "flight_datetime":       (413, _H - 159.9 + 2),
    # Aircraft block
    "aircraft_id":           (458, _H - 193.5 + 2),   # value goes after the "N"
    "aircraft_model":        (406, _H - 222.6 + 2),
    "aircraft_color":        (358, _H - 253.5 + 2),
    "base_hangar":           (394, _H - 284.4 + 2),
    # Route block
    "departure_airport":     (423, _H - 308.9 + 2),
    "etd":                   (342, _H - 324.4 + 2),
    "interim_airports":      (420, _H - 339.9 + 2),
    "destination_airport":   (431, _H - 355.2 + 2),
    "eta":                   (342, _H - 370.8 + 2),
    "ata":                   (451, _H - 370.8 + 2),
    "route_of_flight":       (406, _H - 401.9 + 2),
    "altitudes":             (381, _H - 442.9 + 2),
    # Pilot
    "pilot_name_badge":      (182, _H - 541.5 + 2),
    "pilot_mobile":          (159, _H - 556.9 + 2),
    # Flight officer
    "fo_name_badge":         (229, _H - 612.0 + 2),
    "fo_mobile":             (160, _H - 627.5 + 2),
    # Observer
    "obs_name_badge":        (204, _H - 685.6 + 2),
    "obs_phone":             (120, _H - 700.9 + 2),
    # Authorizations (disambiguated by vertical position)
    "commander_auth":        (360, _H - 559.2 + 2),   # name/phone on signature line
    "commander_datetime":    (372, _H - 578.2 + 2),   # first DATE/TIME:
    "liaison_auth":          (315, _H - 615.4 + 2),   # text body of liaison box
    "liaison_datetime":      (372, _H - 634.4 + 2),   # second DATE/TIME:
    # Notifications — date goes on a sub-line below the email address
    "notify_email_datetime": (337, _H - 686.6 - 10),
    # Inflight frequency "other" text
    "freq_other_text":       (493, _H - 499.3 + 2),
    # Note: mission_type_other is not rendered inline — the column has no room.
    # Users should put the explanation in flight_objectives instead.
}

# Multi-line fields: key -> (x, y_start, wrap_cols, line_height_pts)
_PARA = {
    "flight_objectives": (80, _H - 401.9 - 13, 42, 11),
    "comments":          (80, _H - 477.7 - 13, 42, 11),
}

# Checkbox image bounds in pdfplumber coords (x0, top, x1, bottom).
# Source: pdfplumber image extraction from the template.
# Centers for the overlay are derived from these — keep this as the single
# source of truth so the test can validate against the same bounds.
CBX_BOUNDS = {
    # Mission types
    "routine_airborne_patrol":        ( 98.3, 193.6, 116.3, 210.0),
    "ground_search_support":          ( 98.3, 213.1, 116.3, 229.4),
    "sheriff_surveillance_support":   ( 98.3, 232.5, 116.3, 248.9),
    "aero_squadron_mission_training": ( 98.3, 252.0, 116.3, 268.3),
    "personnel_transportation":       ( 98.3, 271.4, 116.3, 287.8),
    "aircraft_systems_flight_check":  ( 98.3, 290.9, 116.3, 307.2),
    "maintenance_repositioning":      ( 98.3, 310.4, 116.3, 326.7),
    "pilot_checkout_qualification":   ( 98.3, 329.8, 116.3, 346.1),
    "other":                          ( 97.7, 349.3, 115.7, 365.6),
    # Inflight frequencies
    "freq_control20":                 (316.6, 479.9, 334.6, 496.2),
    "freq_other_box":                 (430.5, 479.9, 448.5, 496.2),
    "freq_1231":                      (316.6, 501.4, 334.6, 517.7),
    # Sheriff's office notifications
    "notify_email":                   (316.6, 667.5, 334.6, 683.8),
    "notify_dispatch":                (316.6, 702.7, 334.6, 719.0),
}

# Centers in ReportLab coords (origin bottom-left), derived from CBX_BOUNDS.
_CBX = {
    key: ((x0 + x1) / 2, _H - (top + bottom) / 2)
    for key, (x0, top, x1, bottom) in CBX_BOUNDS.items()
}


# Fields whose values start inline after a long label, then wrap to the left
# margin when they exceed the column boundary (~x=305).
# Format: key -> (x_inline, y, x_wrap, col_right, line_height)
_LEFT_COL_RIGHT = 305
_WRAP_INLINE = {
    "pilot_emergency": (229, _H - 572.4 + 2, 80, _LEFT_COL_RIGHT, 10),
    "fo_emergency":    (230, _H - 642.9 + 2, 80, _LEFT_COL_RIGHT, 10),
    "obs_emergency":   (229, _H - 716.4 + 2, 80, _LEFT_COL_RIGHT, 10),
}


def _draw_wrap_inline(c, font, size, x_start, y, x_wrap, col_right, lh, text):
    """Draw text starting inline at (x_start, y), wrapping to x_wrap when the
    current line would exceed col_right."""
    words = text.split()
    line = ""
    x = x_start
    for word in words:
        candidate = (line + " " + word).strip() if line else word
        if line and x + stringWidth(candidate, font, size) > col_right:
            c.drawString(x, y, line)
            line = word
            x = x_wrap
            y -= lh
        else:
            line = candidate
    if line:
        c.drawString(x, y, line)


def fill(data, output_path, template_path=TEMPLATE_PATH):
    """Write a filled form PDF to output_path from a flat field-key dict.

    Raises FileNotFoundError if the template is missing.
    Returns output_path.
    """
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found: {template_path}")

    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas as rl_canvas

    packet = io.BytesIO()
    c = rl_canvas.Canvas(packet, pagesize=(612, _H))

    # Single-line text fields
    c.setFont("Helvetica", 9)
    for key, (x, y) in _TEXT.items():
        val = str(data.get(key) or "").strip()
        if val:
            c.drawString(x, y, val)

    # Inline-wrap fields (start inline, wrap to left margin on overflow)
    c.setFont("Helvetica", 9)
    for key, (x_s, y, x_w, col_r, lh) in _WRAP_INLINE.items():
        val = str(data.get(key) or "").strip()
        if val:
            _draw_wrap_inline(c, "Helvetica", 9, x_s, y, x_w, col_r, lh, val)

    # Multi-line paragraph fields
    c.setFont("Helvetica", 8)
    for key, (x, y, cols, lh) in _PARA.items():
        val = str(data.get(key) or "").strip()
        if not val:
            continue
        lines = []
        for raw in val.splitlines():
            lines.extend(textwrap.wrap(raw, cols) or [""])
        for i, line in enumerate(lines):
            c.drawString(x, y - i * lh, line)

    # Checkbox "X" marks — centered in each box using the box's center coords.
    # drawCentredString handles horizontal centering; the 0.35 factor vertically
    # positions the baseline so the cap-height is centered in the box.
    CBX_FONT, CBX_SIZE = "Helvetica-Bold", 10
    c.setFont(CBX_FONT, CBX_SIZE)

    def draw_x(key):
        cx, cy = _CBX[key]
        c.drawCentredString(cx, cy - CBX_SIZE * 0.35, "X")

    mission_types = set(data.get("mission_type") or [])
    for key, _ in MISSION_TYPES:
        if key in mission_types:
            draw_x(key)

    for flag_key, cbx_key in (
        ("freq_control20",  "freq_control20"),
        ("freq_other",      "freq_other_box"),
        ("freq_1231",       "freq_1231"),
        ("notify_email",    "notify_email"),
        ("notify_dispatch", "notify_dispatch"),
    ):
        if data.get(flag_key):
            draw_x(cbx_key)

    c.save()
    packet.seek(0)

    overlay = PdfReader(packet)
    template = PdfReader(template_path)
    writer = PdfWriter()

    # Page 1: form with overlay
    form_page = template.pages[0]
    form_page.merge_page(overlay.pages[0])
    writer.add_page(form_page)

    # Page 2: authorization process page (keep as-is)
    if len(template.pages) > 1:
        writer.add_page(template.pages[1])

    with open(output_path, "wb") as f:
        writer.write(f)
    return output_path
