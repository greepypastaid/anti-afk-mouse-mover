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

Controls & safety
- CTRL+ALT+P — pause / resume
- CTRL+ALT+Q — quit
- Move cursor to top-left corner to trigger PyAutoGUI's failsafe and exit immediately

Main options (high level)
- `--min-sleep`, `--max-sleep`: seconds between action cycles (default 3–12)
- `--move-duration-min`, `--move-duration-max`: movement duration in seconds
- `--margin`: avoid screen edges (pixels)
- `--click-prob`, `--right-click-prob`, `--scroll-prob`: tune click/scroll behavior
- `--min-move`: minimum pixels to perform a full move; otherwise script does a small jitter
- `--dry-run`: don't send real input, just log actions
- `--seed`: set RNG seed for reproducible dry-runs
 - `--prompt-interval`: prompt interactively for min/max sleep interval before starting

Notes
- On macOS you may need to grant Accessibility permission to your Terminal or Python interpreter (System Settings → Privacy & Security → Accessibility).
- Use responsibly — don't bypass rules or automate interactions where it's not allowed.

Want a sample dry-run output or a macOS launchd example? I can add one.
