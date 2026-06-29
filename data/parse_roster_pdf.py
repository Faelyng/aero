"""Experimental parser for the Aero Squadron roster PDF.

Converts the roster PDF to the same JSON structure as AeroRoster20260127.json.
The roster format is fairly consistent, but may need tweaks when the layout
changes between revisions.
"""

import re
import pdfplumber

# ── patterns ─────────────────────────────────────────────────────────────────

_PHONE_RE    = re.compile(r'\(\d{3}\)\s*\d{3}[-.\s]?\d{4}(?:\s*\([CRBcrb]\))?')
_EMAIL_RE    = re.compile(r'E-?mail:\s*(\S+)', re.IGNORECASE)
_BADGE_RE    = re.compile(r'^(A-\d+)\s+(.+)$')
_REG_RE      = re.compile(r'\b(N\d+[A-Z]*)\b', re.IGNORECASE)
_RANK_RE     = re.compile(r'\((Lt\.|Capt\.|M\.D\.)\)', re.IGNORECASE)
_EMERGENCY_RE = re.compile(r'^Emergency(?:\s+Contact)?:\s*(.+)', re.IGNORECASE)

# Lines to skip entirely (headers, page numbers, table rows, etc.)
_SKIP_RE = re.compile(
    r'^(CONFIDENTIAL|SAN LUIS OBISPO|JANUARY|BADGE\s*$|AERO SQUADRON|'
    r'ACTIVE ASSET|Active Pilots|EMT/Para|Members on|Radio Tech|\d+\s*$|'
    r'GENERAL MEMBERSHIP|ELECTED|SPECIAL APPOINTED|SLOSAR|SUPPORT STAFF|'
    r'SHERIFF.S OFFICE|WATCH COMMANDER|DISPATCH|PERMITS|MEETING SUPPORT|'
    r'UNIT 1798|AIRCRAFT HANGAR|LOCKBOX|TRUCK VAULT|DOOR COMB|KEYLESS)',
    re.IGNORECASE,
)

_SECTION_EMERITUS = re.compile(r'^\s*EMERITUS MEMBERS\s*$', re.IGNORECASE | re.MULTILINE)
_SECTION_HONORARY = re.compile(r'^\s*HONORARY MEMBERS\s*$', re.IGNORECASE | re.MULTILINE)


# ── public entry point ───────────────────────────────────────────────────────

def parse_pdf(pdf_path) -> dict:
    """Parse a roster PDF and return a dict matching the roster JSON structure."""
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    general_text, emeritus_text, honorary_text = _split_sections(full_text)

    return {
        "san_luis_obispo_county_sheriff_aero_squadron": {
            "membership_roster": {
                "directory": {
                    "general_membership": _parse_badged_section(general_text),
                    "emeritus_members":   _parse_badged_section(emeritus_text),
                    "honorary_members":   _parse_honorary_section(honorary_text),
                }
            }
        }
    }


# ── section splitting ────────────────────────────────────────────────────────

def _split_sections(text: str) -> tuple[str, str, str]:
    em  = _SECTION_EMERITUS.search(text)
    hon = _SECTION_HONORARY.search(text)

    general  = text[: em.start()]  if em  else text
    emeritus = ""
    honorary = ""

    if em and hon and hon.start() > em.start():
        emeritus = text[em.end() : hon.start()]
        honorary = text[hon.end() :]
    elif em:
        emeritus = text[em.end() :]
    elif hon:
        honorary = text[hon.end() :]

    return general, emeritus, honorary


# ── member block parsing ─────────────────────────────────────────────────────

def _parse_badged_section(text: str) -> list[dict]:
    """Split text into member blocks on badge lines and parse each."""
    blocks: list[list[str]] = []
    current: list[str] = []

    for raw in text.splitlines():
        line = raw.strip()
        if _BADGE_RE.match(line):
            if current:
                blocks.append(current)
            current = [line]
        elif current:
            current.append(line)

    if current:
        blocks.append(current)

    return [m for m in (_parse_member_block(b) for b in blocks) if m]


def _parse_member_block(lines: list[str]) -> dict | None:
    first = lines[0].strip()
    badge_m = _BADGE_RE.match(first)
    if not badge_m:
        return None

    badge    = badge_m.group(1)
    rest     = badge_m.group(2)
    all_text = "\n".join(lines)

    phones = [_normalize_phone(p) for p in _PHONE_RE.findall(all_text)]
    email_m = _EMAIL_RE.search(all_text)
    email   = email_m.group(1) if email_m else ""
    ec_m = _EMERGENCY_RE.search(all_text)
    emergency_contact = _parse_emergency_str(ec_m.group(1).strip()) if ec_m else None

    name_line = _PHONE_RE.sub("", rest).strip()
    name, rank, role = _parse_name_line(name_line)

    aircraft = _parse_aircraft_lines(lines[1:])

    entry: dict = {"badge": badge, "name": name}
    if rank:
        entry["rank"] = rank
    if role:
        entry["role"] = role
    contact: dict = {"phone": phones}
    if email:
        contact["email"] = email
    if emergency_contact:
        contact["emergency_contact"] = emergency_contact
    entry["contact"] = contact
    if aircraft:
        entry["aircraft"] = aircraft

    return entry


# ── name parsing ─────────────────────────────────────────────────────────────

def _parse_name_line(text: str) -> tuple[str, str, str]:
    """Return (full_name, rank, role) from the name portion of a first line."""
    text = text.strip()

    # Pull out rank
    rank = ""
    rm = _RANK_RE.search(text)
    if rm:
        rank = rm.group(1)
        text = (text[: rm.start()] + text[rm.end() :]).strip()

    # Pull out any other parenthetical (EMT, Past Commander, nickname, etc.)
    extras = re.findall(r'\(([^)]+)\)', text)
    text   = re.sub(r'\([^)]+\)', '', text).strip()

    if "," in text:
        lastname, rest = text.split(",", 1)
        lastname = lastname.strip().title()
        rest     = rest.strip()

        words = [w.strip('",;. ') for w in rest.split() if w.strip('",;. ')]
        firstname_words: list[str] = []
        role_words:      list[str] = []
        in_role = False

        for w in words:
            if not in_role and w.isupper() and len(w) > 2:
                in_role = True
            (role_words if in_role else firstname_words).append(w)

        firstname = " ".join(firstname_words)
        role_parts = role_words[:]
        # Append non-rank parenthetical extras as role context
        for e in extras:
            if e not in (rank, "Past Commander") and not re.match(r'Lt\.|Capt\.', e):
                role_parts.append(f"({e})")
        role = " ".join(role_parts)
        name = f"{firstname} {lastname}".strip()
    else:
        name = text.title()
        role = " ".join(f"({e})" for e in extras)

    return name, rank, role


# ── aircraft parsing ──────────────────────────────────────────────────────────

def _parse_aircraft_lines(lines: list[str]) -> list[dict]:
    """State-machine parser for aircraft entries within a member block."""
    aircraft: list[dict] = []
    current:  dict | None = None
    in_ac_section = False

    for raw in lines:
        line = raw.strip()
        if not line or _SKIP_RE.match(line) or _EMAIL_RE.match(line):
            continue

        # "Aircraft: ..." — first aircraft entry
        ac_m = re.match(r'Aircraft:\s*(.+)', line, re.IGNORECASE)
        if ac_m:
            if current is not None:
                aircraft.append(current)
            current = _parse_ac_csv(ac_m.group(1))
            in_ac_section = True
            continue

        # "Color: ..." — assign to current aircraft
        col_m = re.match(r'Color:\s*(.+)', line, re.IGNORECASE)
        if col_m and current is not None:
            current["color"] = col_m.group(1).strip()
            aircraft.append(current)
            current = None
            continue

        if not in_ac_section:
            continue

        # Airport-only continuation, possibly with inline color
        # e.g. "(SBP/SZP) Color: Blue, Orange and White"
        ap_m = re.match(r'\(([A-Z0-9/]+)\)(.*)', line)
        if ap_m and current is not None and not current.get("airport"):
            current["airport"] = ap_m.group(1)
            rest_inline = ap_m.group(2).strip()
            col_inline = re.match(r'Color:\s*(.+)', rest_inline, re.IGNORECASE)
            if col_inline:
                current["color"] = col_inline.group(1).strip()
                aircraft.append(current)
                current = None
            continue

        # Subsequent aircraft (no "Aircraft:" prefix, but has a registration)
        if _REG_RE.search(line) and "," in line:
            if current is not None:
                aircraft.append(current)
            current = _parse_ac_csv(line)
            continue

    if current is not None:
        aircraft.append(current)

    return aircraft


def _parse_ac_csv(csv_str: str) -> dict:
    """Parse 'Model, Registration, Seats, WeightClass, (Airport)' CSV."""
    parts = [p.strip().strip("()") for p in csv_str.split(",")]

    ac: dict = {
        "model": "", "registration": "", "seats": "",
        "weight_class": "", "airport": "", "color": "",
    }

    # Model = everything before the N-number
    reg_idx = next(
        (i for i, p in enumerate(parts) if re.match(r'^N\d+[A-Z]*$', p.strip().upper())),
        None,
    )
    if reg_idx is not None:
        ac["model"]        = ", ".join(p.strip() for p in parts[:reg_idx])
        ac["registration"] = parts[reg_idx].strip().upper()
        for p in parts[reg_idx + 1 :]:
            p_s = p.strip("() ")
            p_u = p_s.upper()
            if p_u in ("HW", "LW"):
                ac["weight_class"] = p_u
            elif re.search(r"place", p_s, re.IGNORECASE):
                ac["seats"] = p_s
            elif re.match(r"^K[A-Z]{3,4}$", p_u):
                ac["airport"] = p_u
            elif "/" in p_s and len(p_s) <= 12:
                ac["airport"] = p_u
    else:
        ac["model"] = csv_str.strip()

    return ac


# ── honorary members ──────────────────────────────────────────────────────────

def _parse_honorary_section(text: str) -> list[dict]:
    members = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or _SKIP_RE.match(line):
            continue

        badge = ""
        bm = _BADGE_RE.match(line)
        if bm:
            badge = bm.group(1)
            line  = bm.group(2).strip()

        role_m   = re.search(r'\(([^)]+)\)', line)
        role     = role_m.group(1) if role_m else ""
        name_raw = re.sub(r'\([^)]+\)', '', line).strip().strip('",')

        if "," in name_raw:
            last, rest = name_raw.split(",", 1)
            name = f"{rest.strip()} {last.strip().title()}".strip()
        else:
            name = name_raw.title()

        if name:
            entry: dict = {"name": name}
            if badge:
                entry["badge"] = badge
            if role:
                entry["role"] = role
            members.append(entry)

    return members


# ── phone normalisation ───────────────────────────────────────────────────────

def _parse_emergency_str(text: str) -> dict:
    """Parse 'NAME (RELATIONSHIP) PHONE' into a structured dict."""
    m = re.match(r'^(.*?)\s*\(([^)]+)\)\s*([\d/\-\(\) ]+)$', text)
    if m:
        return {"name": m.group(1).strip(), "relationship": m.group(2).strip(), "phone": m.group(3).strip()}
    m2 = re.search(r'([\d/\-]{7,})$', text)
    if m2:
        return {"name": text[:m2.start()].strip(), "relationship": "", "phone": m2.group(1).strip()}
    return {"name": text, "relationship": "", "phone": ""}


def _normalize_phone(phone: str) -> str:
    """Ensure a space before the (C)/(B)/(R) suffix."""
    return re.sub(r'(?<!\s)(\([CRBcrb]\))$', r' \1', phone.strip())
