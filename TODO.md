# Aero Mission Planner — Planning Notes

## Deferred UI / Polish

- **System theme detection** (light/dark): detect at launch via registry (Windows) or
  `defaults` (macOS); call `sv_ttk.set_theme()` accordingly. ~30 min. Dynamic
  (follow live changes) not worth it.
- **Responsive layout — entry stretching**: make form fields expand horizontally as
  the window is resized. Low effort (~1 hr), `columnconfigure(weight=1)` + `fill="x"`.
- **Responsive layout — column reflow**: reflow left/right sections into a single
  column on narrow windows. Moderate effort (~3–5 hrs), requires restructuring layout
  and `<Configure>` listeners.

## Pre-Release / Release Quality

- **Open PDF after generating**: offer to open the saved PDF immediately (via
  `os.startfile` / `open` / `xdg-open`).
- **Mission deletion**: add a Delete button in the mission bar to remove the currently
  loaded mission file with a confirmation prompt.
- **Time field validation**: enforce HH:MM format in the time entries (or use a
  spinbox). Currently accepts any string.
- **App icon**: add a `.ico` / `.icns` for the window and packaged app.
- **About dialog**: version number, squadron name, basic credits.
- **Tab order**: audit keyboard navigation through the form fields.
- **Roster backup on update**: before overwriting `AeroRoster20260127.json` on import,
  save a timestamped backup.
- **PDF roster parsing**: currently marked "Experimental" in the UI — validate against
  a second real roster before removing that label.
- **Version number**: add a `__version__` somewhere (e.g., `main.py`) and surface it
  in the title bar and About dialog.

## Pre-Release / Data / Storage

- **Roster storage (production)**: currently the roster is read/written inside the
  PyInstaller `_internal/` bundle directory, which works but gets wiped on app updates.
  For production, copy the bundled roster to a per-user app-data directory on first
  launch (`%APPDATA%\AeroMissionPlanner` on Windows, `~/Library/Application Support/`
  on macOS) and read/write from there.
- **Mission storage location**: missions are saved next to the executable. Consider
  moving to user app-data directory (same reasoning as roster).

## Packaging (done for beta)

- `aero.spec` — PyInstaller spec (folder bundle / `--onedir`).
- `build.sh` — Linux / macOS build script.
- `build_windows.bat` — Windows build script (requires separate Windows venv;
  see comments in the file).
- Separate builds required per platform (PyInstaller cannot cross-compile).
- macOS: code-signing / notarization needed for Gatekeeper in production.
- Windows: code-signing avoids SmartScreen warning in production.
- Consider switching to `--onefile` for final release (adds ~5 sec cold-start delay
  but produces a single .exe / .app instead of a folder).
