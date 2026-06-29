import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tkcalendar import DateEntry

from data.member_data import (
    load_members, member_label, find_by_label, import_roster,
    DEFAULT_ROSTER_PATH, SQUADRON_AIRCRAFT,
)
from data.missions import list_missions, load as load_mission, save as save_mission
from pdf.form_filler import MISSION_TYPES, fill

PAD = 6
_NO_MISSION  = "— New Mission —"
_PACIFIC = ZoneInfo("America/Los_Angeles")


def _today_pacific() -> date:
    return datetime.now(_PACIFIC).date()


def _to_pdf_date(s: str) -> str:
    """'MM/DD/YYYY' → 'MMDDYYYY'"""
    try:
        return datetime.strptime(s.strip(), "%m/%d/%Y").strftime("%m%d%Y")
    except ValueError:
        return s.replace("/", "")


def _to_pdf_datetime(date_s: str, time_s: str) -> str:
    d = _to_pdf_date(date_s)
    t = time_s.strip().replace(":", "")
    if d and t:
        return f"{d} {t}"
    return d or t
_NO_MEMBER   = "— None —"
_NO_AIRCRAFT = "— Select aircraft —"

_DEFAULT_COMMANDER       = "JENS E. HANSEN"
_DEFAULT_COMMANDER_PHONE = "805/478-1666"
_DEFAULT_LIAISON         = "CDR. JOHN MCDANIEL"


class MissionFormApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Aero Mission Planner")
        self.root.geometry("980x860")

        self.members = load_members()
        self._member_labels = [_NO_MEMBER] + [member_label(m) for m in self.members]

        self.vars = {}          # str field key -> StringVar
        self.text_widgets = {}  # multiline field key -> Text
        self.mission_vars = {}  # mission type key -> BooleanVar
        self._date_entries: dict[str, DateEntry] = {}  # date field key -> DateEntry

        # Per-role state — squadron aircraft always available
        self._pilot_aircraft: list[dict] = list(SQUADRON_AIRCRAFT)
        self.liaison_verbal = tk.BooleanVar(value=True)
        self._fo_member = None
        self._obs_member = None

        # Save path for the currently loaded mission (None = unsaved)
        self._current_path: Path | None = None
        self._loading = False  # suppresses autofill callbacks during load

        self._build_style()
        self._build_layout()
        self._apply_defaults()

    # ---- style -----------------------------------------------------------
    def _build_style(self):
        style = ttk.Style()
        style.configure("Header.TLabel", font=("Segoe UI", 13, "bold"))
        style.configure("Section.TLabelframe.Label", font=("Segoe UI", 9, "bold"))
        style.configure("Action.TButton", font=("Segoe UI", 10, "bold"), padding=6)

    # ---- layout ----------------------------------------------------------
    def _build_layout(self):
        # ── top bar ──────────────────────────────────────────────────────
        top = ttk.Frame(self.root, padding=(PAD, PAD, PAD, 0))
        top.pack(fill="x")
        ttk.Label(top, text="Mission Flight Plan Authorization",
                  style="Header.TLabel").pack(side="left")

        # ── mission load/save bar ─────────────────────────────────────────
        mbar = ttk.Frame(self.root, padding=(PAD, 4, PAD, 0))
        mbar.pack(fill="x")
        ttk.Label(mbar, text="Mission:").pack(side="left")
        self.mission_var = tk.StringVar(value=_NO_MISSION)
        self.mission_combo = ttk.Combobox(
            mbar, textvariable=self.mission_var, state="readonly", width=46
        )
        self.mission_combo.pack(side="left", padx=(4, 8))
        self.mission_combo.bind("<<ComboboxSelected>>", self._on_mission_selected)
        ttk.Button(mbar, text="New",  command=self._new_mission).pack(side="left", padx=2)
        ttk.Button(mbar, text="Save", command=self.save).pack(side="left", padx=2)

        ttk.Label(mbar, text="Name:").pack(side="left", padx=(12, 2))
        self.mission_name_var = tk.StringVar()
        ttk.Entry(mbar, textvariable=self.mission_name_var, width=24).pack(side="left")
        self._refresh_mission_list()

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=PAD, pady=4)

        # ── autofill pickers ──────────────────────────────────────────────
        af = ttk.Frame(self.root, padding=(PAD, 0))
        af.pack(fill="x")

        # Pilot row
        ttk.Label(af, text="Pilot:", width=10, anchor="e").grid(row=0, column=0, padx=4, pady=2)
        self.pilot_var = tk.StringVar()
        self._pilot_combo = ttk.Combobox(
            af, textvariable=self.pilot_var,
            values=self._member_labels, state="readonly", width=36,
        )
        self._pilot_combo.grid(row=0, column=1, padx=4)
        ttk.Label(af, text="Aircraft:").grid(row=0, column=2, padx=(12, 4))
        self.aircraft_var = tk.StringVar()
        self.aircraft_combo = ttk.Combobox(
            af, textvariable=self.aircraft_var, state="readonly", width=36
        )
        self.aircraft_combo.grid(row=0, column=3, padx=4)
        self.pilot_var.trace_add("write", self._on_pilot_changed)
        self.aircraft_var.trace_add("write", self._on_aircraft_changed)

        # Flight Officer row
        ttk.Label(af, text="Flight Officer:", width=10, anchor="e").grid(row=1, column=0, padx=4, pady=2)
        self.fo_var = tk.StringVar()
        self._fo_combo = ttk.Combobox(
            af, textvariable=self.fo_var,
            values=self._member_labels, state="readonly", width=36,
        )
        self._fo_combo.grid(row=1, column=1, padx=4)
        self.fo_var.trace_add("write", self._on_fo_changed)

        # Observer row
        ttk.Label(af, text="Observer:", width=10, anchor="e").grid(row=2, column=0, padx=4, pady=2)
        self.obs_var = tk.StringVar()
        self._obs_combo = ttk.Combobox(
            af, textvariable=self.obs_var,
            values=self._member_labels, state="normal", width=36,
        )
        self._obs_combo.grid(row=2, column=1, padx=4)
        self.obs_var.trace_add("write", self._on_obs_changed)

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=PAD, pady=4)

        # ── scrollable form body ──────────────────────────────────────────
        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=PAD)
        canvas = tk.Canvas(body, highlightthickness=0)
        scroll = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        left = ttk.Frame(inner)
        right = ttk.Frame(inner)
        left.grid(row=0, column=0, sticky="nw", padx=(0, PAD))
        right.grid(row=0, column=1, sticky="nw")

        self._build_left(left)
        self._build_right(right)

        # ── bottom buttons ────────────────────────────────────────────────
        btn_bar = ttk.Frame(self.root, padding=(PAD, 4))
        btn_bar.pack(fill="x")
        ttk.Button(btn_bar, text="Save", style="Action.TButton",
                   command=self.save).pack(side="left", padx=4)
        ttk.Button(btn_bar, text="Generate PDF", style="Action.TButton",
                   command=self.generate_pdf).pack(side="left", padx=4)
        ttk.Button(btn_bar, text="Update Roster (Experimental)",
                   command=self._update_roster).pack(side="right", padx=4)

    # ---- field helpers ---------------------------------------------------
    def _entry(self, parent, key, label, width=28):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=22, anchor="w").pack(side="left")
        var = tk.StringVar()
        ttk.Entry(row, textvariable=var, width=width).pack(side="left", fill="x", expand=True)
        self.vars[key] = var

    def _textarea(self, parent, key, height=3):
        txt = tk.Text(parent, height=height, width=42, wrap="word")
        txt.pack(fill="x", pady=2)
        self.text_widgets[key] = txt

    def _date_field(self, parent, key, label):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=22, anchor="w").pack(side="left")
        de = DateEntry(row, date_pattern="mm/dd/yyyy", width=14)
        de.pack(side="left")
        self._date_entries[key] = de

    def _datetime_field(self, parent, date_key, time_key, label):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=22, anchor="w").pack(side="left")
        de = DateEntry(row, date_pattern="mm/dd/yyyy", width=12)
        de.pack(side="left")
        ttk.Label(row, text=" Time:").pack(side="left")
        time_var = tk.StringVar()
        ttk.Entry(row, textvariable=time_var, width=6).pack(side="left", padx=(2, 0))
        ttk.Label(row, text="HH:MM").pack(side="left", padx=(2, 0))
        self._date_entries[date_key] = de
        self.vars[time_key] = time_var

    def _section(self, parent, title):
        frame = ttk.LabelFrame(parent, text=title,
                               style="Section.TLabelframe", padding=PAD)
        frame.pack(fill="x", pady=(0, PAD))
        return frame

    # ---- form sections ---------------------------------------------------
    def _build_left(self, parent):
        s = self._section(parent, "Request")
        self._date_field(s, "request_date", "Request Date")

        s = self._section(parent, "Mission Type")
        for key, lbl in MISSION_TYPES:
            var = tk.BooleanVar()
            ttk.Checkbutton(s, text=lbl, variable=var).pack(anchor="w")
            self.mission_vars[key] = var

        s = self._section(parent, "Flight Objective(s)")
        self._textarea(s, "flight_objectives", height=4)

        s = self._section(parent, "Comments")
        self._textarea(s, "comments", height=3)

        s = self._section(parent, "Pilot")
        self._entry(s, "pilot_name_badge",   "Name / Badge")
        self._entry(s, "pilot_mobile",       "Mobile Phone")
        self._entry(s, "pilot_ec_name",      "EC Name")
        self._entry(s, "pilot_ec_rel",       "EC Relationship")
        self._entry(s, "pilot_ec_phone",     "EC Phone")

        s = self._section(parent, "Flight Officer")
        self._entry(s, "fo_name_badge", "Name / Badge")
        self._entry(s, "fo_mobile",     "Mobile Phone")
        self._entry(s, "fo_ec_name",    "EC Name")
        self._entry(s, "fo_ec_rel",     "EC Relationship")
        self._entry(s, "fo_ec_phone",   "EC Phone")

        s = self._section(parent, "Observer")
        self._entry(s, "obs_name_badge", "Name / Badge")
        self._entry(s, "obs_phone",      "Phone")
        self._entry(s, "obs_ec_name",    "EC Name")
        self._entry(s, "obs_ec_rel",     "EC Relationship")
        self._entry(s, "obs_ec_phone",   "EC Phone")

    def _build_right(self, parent):
        s = self._section(parent, "Flight")
        self._datetime_field(s, "flight_date", "flight_time", "Flight Date/Time")

        s = self._section(parent, "Aircraft")
        self._entry(s, "aircraft_id",    "Identification (N…)")
        self._entry(s, "aircraft_model", "Model")
        self._entry(s, "aircraft_color", "Color")
        self._entry(s, "base_hangar",    "Base / Hangar")

        s = self._section(parent, "Route")
        self._entry(s, "departure_airport",  "Departure Airport")
        self._entry(s, "etd",                "ETD")
        self._entry(s, "interim_airports",   "Interim Airport(s)")
        self._entry(s, "destination_airport","Destination Airport")
        self._entry(s, "eta",                "ETA")
        self._entry(s, "ata",                "ATA")
        self._entry(s, "route_of_flight",    "Route of Flight")
        self._entry(s, "altitudes",          "Altitude(s)")

        s = self._section(parent, "Inflight Frequencies")
        self.freq_control20 = tk.BooleanVar()
        self.freq_1231      = tk.BooleanVar()
        self.freq_other     = tk.BooleanVar()
        ttk.Checkbutton(s, text="Control 20/Blue", variable=self.freq_control20).pack(anchor="w")
        ttk.Checkbutton(s, text="123.1 MHz",       variable=self.freq_1231).pack(anchor="w")
        ttk.Checkbutton(s, text="Other",            variable=self.freq_other).pack(anchor="w")
        self._entry(s, "freq_other_text", "Other freq")

        s = self._section(parent, "Authorizations")
        self._entry(s, "commander_auth",  "Commander Name")
        self._entry(s, "commander_phone", "Commander Phone")
        self._datetime_field(s, "commander_date", "commander_time", "Signature Date/Time")

        # Liaison row: name field + inline "Verbal" checkbox
        row = ttk.Frame(s)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Liaison Officer", width=22, anchor="w").pack(side="left")
        var = tk.StringVar()
        ttk.Entry(row, textvariable=var, width=20).pack(side="left", fill="x", expand=True)
        self.vars["liaison_name"] = var
        ttk.Checkbutton(row, text="Verbal", variable=self.liaison_verbal).pack(side="left", padx=(6, 0))

        self._datetime_field(s, "liaison_date", "liaison_time", "Signature Date/Time")

        s = self._section(parent, "Sheriff's Office Notifications")
        self.notify_email    = tk.BooleanVar()
        self.notify_dispatch = tk.BooleanVar()
        ttk.Checkbutton(s, text="SH_WC@CO.SLO.CA.US", variable=self.notify_email).pack(anchor="w")
        self._datetime_field(s, "notify_email_date", "notify_email_time", "Email Date/Time")
        ttk.Checkbutton(s, text="Dispatch via telephone", variable=self.notify_dispatch).pack(anchor="w")

    # ---- autofill callbacks ----------------------------------------------
    def _on_pilot_changed(self, *_):
        label = self.pilot_var.get()
        member = find_by_label(self.members, label)
        personal = (member.get("aircraft") or []) if member else []
        personal_regs = {ac.get("registration", "") for ac in personal}
        # Always append squadron aircraft not already in the pilot's personal list
        extra = [a for a in SQUADRON_AIRCRAFT if a["registration"] not in personal_regs]
        self._pilot_aircraft = personal + extra

        if member and not self._loading:
            self._fill_person("pilot", member)

        if self._pilot_aircraft:
            ac_labels = [self._aircraft_label(ac) for ac in self._pilot_aircraft]
            self.aircraft_combo.configure(values=ac_labels)
            self.aircraft_var.set(ac_labels[0])
        else:
            self.aircraft_combo.configure(values=[_NO_AIRCRAFT])
            self.aircraft_var.set(_NO_AIRCRAFT)

    def _on_aircraft_changed(self, *_):
        if self._loading:
            return
        label = self.aircraft_var.get()
        for ac in self._pilot_aircraft:
            if self._aircraft_label(ac) == label:
                self._fill_aircraft(ac)
                return

    def _on_fo_changed(self, *_):
        if self._loading:
            return
        member = find_by_label(self.members, self.fo_var.get())
        if member:
            self._fill_person("fo", member)

    def _on_obs_changed(self, *_):
        if self._loading:
            return
        member = find_by_label(self.members, self.obs_var.get())
        if member:
            self._fill_person("obs", member)

    def _fill_person(self, role: str, member: dict):
        badge = member.get("badge", "")
        name_badge = f"{member['name']}, {badge}".rstrip(", ")
        ec = member.get("emergency_contact") or {}
        if role == "pilot":
            self.vars["pilot_name_badge"].set(name_badge)
            self.vars["pilot_mobile"].set(member.get("mobile_phone", ""))
            self.vars["pilot_ec_name"].set(ec.get("name", ""))
            self.vars["pilot_ec_rel"].set(ec.get("relationship", ""))
            self.vars["pilot_ec_phone"].set(ec.get("phone", ""))
        elif role == "fo":
            self.vars["fo_name_badge"].set(name_badge)
            self.vars["fo_mobile"].set(member.get("mobile_phone", ""))
            self.vars["fo_ec_name"].set(ec.get("name", ""))
            self.vars["fo_ec_rel"].set(ec.get("relationship", ""))
            self.vars["fo_ec_phone"].set(ec.get("phone", ""))
        elif role == "obs":
            self.vars["obs_name_badge"].set(name_badge)
            self.vars["obs_phone"].set(member.get("mobile_phone", ""))
            self.vars["obs_ec_name"].set(ec.get("name", ""))
            self.vars["obs_ec_rel"].set(ec.get("relationship", ""))
            self.vars["obs_ec_phone"].set(ec.get("phone", ""))

    def _fill_aircraft(self, ac: dict):
        reg = ac.get("registration", "")
        self.vars["aircraft_id"].set(reg[1:] if reg.upper().startswith("N") else reg)
        self.vars["aircraft_model"].set(ac.get("model", ""))
        self.vars["aircraft_color"].set(ac.get("color", ""))
        self.vars["base_hangar"].set(ac.get("base_hangar") or ac.get("airport", ""))

    @staticmethod
    def _aircraft_label(ac: dict) -> str:
        reg = ac.get("registration", "")
        model = ac.get("model", "")
        return f"{reg} — {model}" if reg and model else (reg or model or _NO_AIRCRAFT)

    def _match_name_badge(self, name_badge: str) -> dict | None:
        """Find the member whose saved 'Name, Badge' string matches name_badge."""
        if not name_badge or name_badge == "NONE":
            return None
        for m in self.members:
            badge = m.get("badge", "")
            name = m.get("name", "")
            if badge and f"{name}, {badge}" == name_badge:
                return m
        return None

    # ---- mission save / load --------------------------------------------
    def _refresh_mission_list(self):
        missions = list_missions()
        self._mission_map = {label: path for label, path in missions}
        labels = [_NO_MISSION] + list(self._mission_map.keys())
        self.mission_combo.configure(values=labels)
        if self.mission_var.get() not in labels:
            self.mission_var.set(_NO_MISSION)

    def _on_mission_selected(self, _event=None):
        label = self.mission_var.get()
        if label == _NO_MISSION:
            return
        path = self._mission_map.get(label)
        if path:
            self._load_from(path)

    def _new_mission(self):
        for var in self.vars.values():
            var.set("")
        for txt in self.text_widgets.values():
            txt.delete("1.0", "end")
        for var in self.mission_vars.values():
            var.set(False)
        for var in (self.freq_control20, self.freq_1231, self.freq_other,
                    self.notify_email, self.notify_dispatch, self.liaison_verbal):
            var.set(False)
        self.pilot_var.set(_NO_MEMBER)
        self.fo_var.set(_NO_MEMBER)
        self.obs_var.set(_NO_MEMBER)
        self.aircraft_var.set(_NO_AIRCRAFT)
        self.mission_var.set(_NO_MISSION)
        self.mission_name_var.set("")
        self._current_path = None
        self._apply_defaults()

    def _apply_defaults(self):
        self.vars["commander_auth"].set(_DEFAULT_COMMANDER)
        self.vars["commander_phone"].set(_DEFAULT_COMMANDER_PHONE)
        self.vars["liaison_name"].set(_DEFAULT_LIAISON)
        self.liaison_verbal.set(True)
        self.notify_email.set(True)
        self.notify_dispatch.set(True)
        self.vars["departure_airport"].set("KSBP")
        self.vars["destination_airport"].set("KSBP")
        today = _today_pacific()
        for de in self._date_entries.values():
            de.set_date(today)

    def _load_from(self, path: Path):
        data = load_mission(path)
        self._current_path = path

        # Set picker combos while suppressing autofill callbacks.
        # _on_pilot_changed still runs (to populate the aircraft dropdown),
        # but form-field fills are skipped so saved data wins below.
        self._loading = True
        try:
            matched_pilot = self._match_name_badge(data.get("pilot_name_badge", ""))
            self.pilot_var.set(member_label(matched_pilot) if matched_pilot else _NO_MEMBER)
            # Try to select the saved aircraft in the now-populated dropdown
            saved_id = data.get("aircraft_id", "").upper()
            saved_reg = f"N{saved_id}" if saved_id and not saved_id.startswith("N") else saved_id
            for ac in self._pilot_aircraft:
                if ac.get("registration", "").upper() == saved_reg:
                    self.aircraft_var.set(self._aircraft_label(ac))
                    break
            matched_fo = self._match_name_badge(data.get("fo_name_badge", ""))
            self.fo_var.set(member_label(matched_fo) if matched_fo else _NO_MEMBER)
            matched_obs = self._match_name_badge(data.get("obs_name_badge", ""))
            self.obs_var.set(member_label(matched_obs) if matched_obs else _NO_MEMBER)
        finally:
            self._loading = False

        self.mission_name_var.set(data.get("mission_name", ""))
        for key, var in self.vars.items():
            var.set(data.get(key, ""))
        for key, txt in self.text_widgets.items():
            txt.delete("1.0", "end")
            txt.insert("1.0", data.get(key, ""))
        for key, var in self.mission_vars.items():
            var.set(key in (data.get("mission_type") or []))
        self.freq_control20.set(bool(data.get("freq_control20")))
        self.freq_1231.set(bool(data.get("freq_1231")))
        self.freq_other.set(bool(data.get("freq_other")))
        self.notify_email.set(bool(data.get("notify_email")))
        self.notify_dispatch.set(bool(data.get("notify_dispatch")))
        self.liaison_verbal.set(bool(data.get("liaison_verbal", True)))
        # Load date entries from saved data
        today = _today_pacific()
        for key, de in self._date_entries.items():
            saved = data.get(key, "")
            if saved:
                try:
                    de.set_date(datetime.strptime(saved, "%m/%d/%Y").date())
                except ValueError:
                    de.set_date(today)
            else:
                de.set_date(today)
        # Always reflect today for request date and commander sign-off
        self._date_entries["request_date"].set_date(today)
        self._date_entries["commander_date"].set_date(today)

    def save(self):
        data = self.collect()
        path = save_mission(data, self._current_path)
        self._current_path = path
        self._refresh_mission_list()
        self.mission_var.set(next(
            (lbl for lbl, p in self._mission_map.items() if p == path), _NO_MISSION
        ))

    # ---- roster update --------------------------------------------------
    def _update_roster(self):
        path = filedialog.askopenfilename(
            title="Select Roster File",
            filetypes=[
                ("Roster files", "*.json *.pdf"),
                ("JSON roster", "*.json"),
                ("PDF roster", "*.pdf"),
            ],
        )
        if not path:
            return

        if path.lower().endswith(".pdf"):
            if not messagebox.askyesno(
                "Experimental Feature",
                "PDF roster parsing is experimental and may not extract all members "
                "correctly.\n\nA JSON backup of the current roster is recommended "
                "before proceeding.\n\nContinue?",
            ):
                return

        try:
            ok, msg, count = import_roster(path, DEFAULT_ROSTER_PATH)
        except Exception as e:
            messagebox.showerror("Roster Update Failed", str(e))
            return

        if not ok:
            messagebox.showerror("Roster Update Failed", msg)
            return

        self.members = load_members()
        self._member_labels = [_NO_MEMBER] + [member_label(m) for m in self.members]
        for combo in (self._pilot_combo, self._fo_combo, self._obs_combo):
            combo.configure(values=self._member_labels)

        messagebox.showinfo("Roster Updated", f"Loaded {count} members.")

    # ---- collect + generate ---------------------------------------------
    def collect(self) -> dict:
        data = {k: v.get().strip() for k, v in self.vars.items()}
        for key, de in self._date_entries.items():
            data[key] = de.get_date().strftime("%m/%d/%Y")
        for key, txt in self.text_widgets.items():
            data[key] = txt.get("1.0", "end").strip()
        data["mission_name"]   = self.mission_name_var.get().strip()
        data["mission_type"]   = [k for k, v in self.mission_vars.items() if v.get()]
        data["freq_control20"] = self.freq_control20.get()
        data["freq_1231"]      = self.freq_1231.get()
        data["freq_other"]     = self.freq_other.get()
        data["notify_email"]   = self.notify_email.get()
        data["notify_dispatch"] = self.notify_dispatch.get()
        data["liaison_verbal"] = self.liaison_verbal.get()
        return data

    @staticmethod
    def _emergency_str(data: dict, prefix: str) -> str:
        name  = data.get(f"{prefix}_ec_name", "").strip()
        rel   = data.get(f"{prefix}_ec_rel", "").strip()
        phone = data.get(f"{prefix}_ec_phone", "").strip()
        parts = [name]
        if rel:
            parts.append(f"({rel})")
        if phone:
            parts.append(phone)
        return " ".join(p for p in parts if p)

    def generate_pdf(self):
        data = self.collect()

        # Convert display-format dates to PDF format before rendering
        data["request_date"]          = _to_pdf_date(data.get("request_date", ""))
        data["flight_datetime"]       = _to_pdf_datetime(data.get("flight_date", ""), data.get("flight_time", ""))
        data["commander_datetime"]    = _to_pdf_datetime(data.get("commander_date", ""), data.get("commander_time", ""))
        data["liaison_datetime"]      = _to_pdf_datetime(data.get("liaison_date", ""), data.get("liaison_time", ""))
        data["notify_email_datetime"] = _to_pdf_datetime(data.get("notify_email_date", ""), data.get("notify_email_time", ""))

        missing = [
            label for key, label in (
                ("aircraft_id",      "Aircraft Identification"),
                ("pilot_name_badge", "Pilot Name/Badge"),
            ) if not data.get(key)
        ]
        if missing:
            messagebox.showerror("Missing fields", "Please fill: " + ", ".join(missing))
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile="mission_form.pdf",
        )
        if not path:
            return
        # Assemble compound fields for PDF rendering
        for prefix in ("pilot", "fo", "obs"):
            data[f"{prefix}_emergency"] = self._emergency_str(data, prefix)

        auth  = data.get("commander_auth", "").strip()
        phone = data.get("commander_phone", "").strip()
        data["commander_auth"] = f"{auth}  {phone}".strip() if phone else auth

        liaison_name = data.get("liaison_name", "").strip()
        data["liaison_auth"] = (
            f"VERBAL PER {liaison_name}" if data.get("liaison_verbal") and liaison_name
            else liaison_name
        )

        # Write "NONE" for explicitly-absent crew slots (matches form convention)
        for key in ("fo_name_badge", "obs_name_badge"):
            if not data.get(key):
                data[key] = "NONE"

        try:
            fill(data, path)
        except Exception as e:
            messagebox.showerror("PDF generation failed", str(e))
            return
        self.save()
        messagebox.showinfo("Success", f"Saved {path}")
