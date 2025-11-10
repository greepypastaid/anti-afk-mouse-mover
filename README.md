# Anti AFK Mouse Mover

Keep your session alive with small, random mouse moves and occasional clicks/scrolls.

This tool is lightweight and meant for simple use cases (e.g., keeping a remote session or notebook active).

Quick start
1. Create and activate a virtualenv:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

3. Run:

```bash
python anti_afk.py
```

Useful examples
- Verbose, shorter sleeps:

```bash
python anti_afk.py --min-sleep 2 --max-sleep 6 --verbose
```

- Skip tiny moves (avoid fighting your mouse):

```bash
python anti_afk.py --min-move 12
```

- Prompt for interval interactively (enter a single value or a min-max like `3-7`):

```bash
python anti_afk.py --prompt-interval
```

Movement tweaks
- Default "centered" mode keeps moves inside the middle ~80% of the screen. Disable with `--no-centered`.
- Keep activity right where the cursor already is with `--local-move --move-radius 120`.
- Slow or speed up background clicks/scrolls via `--click-interval-*` and `--scroll-interval-*`.

Controls & safety
- CTRL+ALT+P — pause / resume (`--no-hotkeys` disables this)
- CTRL+ALT+Q — quit (`--no-hotkeys` disables this)
- Move cursor to top-left corner to trigger PyAutoGUI's failsafe and exit immediately
- Prefer `--no-hotkeys` when global shortcuts collide; use CTRL+C or close the window to exit

Main options (high level)
- `--min-sleep`, `--max-sleep`: seconds between action cycles (default 3–12)
- `--move-duration-min`, `--move-duration-max`: movement duration in seconds
- `--margin`: avoid screen edges (pixels)
- `--click-prob`, `--right-click-prob`, `--scroll-prob`: tune click/scroll behavior
- `--min-move`: minimum pixels to perform a full move; otherwise the script jitters in place
- `--local-move`, `--move-radius`: prefer small circles around the current cursor position
- `--center-fraction`, `--no-centered`: widen or disable the centered movement window
- `--dry-run`: don't send real input, only log actions
- `--seed`: set RNG seed for reproducible dry-runs
- `--prompt-interval`: prompt interactively for min/max sleep interval before starting
- `--no-hotkeys`: skip registering global shortcuts if they conflict on your OS

Platform notes
- macOS: grant Accessibility permission to your Terminal/Python (System Settings → Privacy & Security → Accessibility).
- Windows: if hotkeys fail, run the shell as Administrator.
- Linux: run inside a graphical session (X11/Wayland) and install helpers such as `python3-xlib`, `scrot`, and `xclip`.

Use responsibly — don't bypass rules or automate interactions where it's not allowed.

Want a sample dry-run output or a macOS launchd example? I can add one.
