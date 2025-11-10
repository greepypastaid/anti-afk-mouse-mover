from __future__ import annotations
import argparse
import math
import os
import platform
import random
import sys
import time
import threading
import logging
from dataclasses import dataclass
from typing import Tuple, Optional

try:
    import pyautogui
    from pynput import keyboard
except ImportError:
    print("Missing dependencies. Install with: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

pyautogui.FAILSAFE = True
DEFAULT_MIN_MOVE = 8

@dataclass
class Config:
    min_sleep: float = 3.0
    max_sleep: float = 12.0
    move_duration_min: float = 0.4
    move_duration_max: float = 1.6
    margin: int = 40
    click_probability: float = 0.55
    right_click_probability: float = 0.08
    scroll_probability: float = 0.25
    scroll_amount_min: int = 40
    scroll_amount_max: int = 240
    dry_run: bool = False
    seed: Optional[int] = None
    verbose: bool = False
    min_move: int = DEFAULT_MIN_MOVE
    prompt_interval: bool = False
    local_move: bool = False
    move_radius: int = 150
    click_interval_min: float = 120.0
    click_interval_max: float = 480.0
    scroll_interval_min: float = 90.0
    scroll_interval_max: float = 360.0
    double_click_probability: float = 0.05
    pause_probability: float = 0.15
    pause_duration_min: float = 0.3
    pause_duration_max: float = 2.5
    micro_move_probability: float = 0.25
    micro_move_radius: int = 15
    long_pause_probability: float = 0.05
    long_pause_min: float = 5.0
    long_pause_max: float = 18.0
    # center-limited movement
    centered: bool = True
    center_fraction: float = 0.8  # fraction of half-screen radius to allow
    enable_hotkeys: bool = True

class State:
    def __init__(self):
        self.running = True
        self.paused = False
        self.lock = threading.Lock()
        now = time.time()
        self.next_click_at = now + 999999.0
        self.next_scroll_at = now + 999999.0

    def schedule_next_click(self, cfg: Config) -> None:
        self.next_click_at = time.time() + rand_uniform(cfg.click_interval_min, cfg.click_interval_max)

    def schedule_next_scroll(self, cfg: Config) -> None:
        self.next_scroll_at = time.time() + rand_uniform(cfg.scroll_interval_min, cfg.scroll_interval_max)

    def toggle_pause(self):
        with self.lock:
            self.paused = not self.paused
            logging.info("Paused=%s", self.paused)

    def stop(self):
        with self.lock:
            self.running = False
            logging.info("Stopping main loop...")


def rand_uniform(a: float, b: float) -> float:
    return random.uniform(a, b)


def dist(a: Tuple[int, int], b: Tuple[int, int]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return math.hypot(dx, dy)


def detect_platform() -> str:
    name = platform.system().lower()
    if "darwin" in name:
        return "mac"
    if "windows" in name:
        return "windows"
    if "linux" in name:
        return "linux"
    return "unknown"


def log_platform_notes(platform_name: str):
    if platform_name == "mac":
        logging.info("Platform detected: macOS")
        logging.info("Grant Accessibility permission to Terminal/Python in System Settings → Privacy & Security → Accessibility.")
    elif platform_name == "windows":
        logging.info("Platform detected: Windows")
        logging.info("If hotkeys do not respond, try running the terminal as Administrator.")
    elif platform_name == "linux":
        logging.info("Platform detected: Linux")
        if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            logging.warning("DISPLAY/WAYLAND variable not found. pyautogui needs a graphical session (X11/Wayland).")
        logging.info("Install dependencies such as python3-xlib, scrot, and xclip for best results: sudo apt install python3-xlib scrot xclip")
    else:
        logging.info("Platform detected: %s", platform_name)


def choose_point(config: Config) -> Tuple[int, int]:
    width, height = pyautogui.size()
    if config.centered:
        cx, cy = width // 2, height // 2
        max_r = int(min(width, height) / 2 * config.center_fraction)
        # respect margin
        max_r = max(0, max_r - config.margin)
        for _ in range(40):
            angle = rand_uniform(0, 2 * math.pi)
            r = rand_uniform(0, max_r)
            x = int(round(cx + math.cos(angle) * r))
            y = int(round(cy + math.sin(angle) * r))
            x = max(config.margin, min(width - config.margin, x))
            y = max(config.margin, min(height - config.margin, y))
            if (x, y) != (cx, cy):
                return x, y
        return cx, cy
    if config.local_move:
        cx, cy = pyautogui.position()
        for _ in range(20):
            angle = rand_uniform(0, 2 * math.pi)
            r = rand_uniform(0, config.move_radius)
            x = int(round(cx + math.cos(angle) * r))
            y = int(round(cy + math.sin(angle) * r))
            x = max(config.margin, min(width - config.margin, x))
            y = max(config.margin, min(height - config.margin, y))
            if (x, y) != (cx, cy):
                return x, y
        return max(config.margin, min(width - config.margin, cx + config.move_radius // 2)), max(config.margin, min(height - config.margin, cy))
    else:
        x = random.randint(config.margin, width - config.margin)
        y = random.randint(config.margin, height - config.margin)
        return x, y


def bezier_path(start: Tuple[int,int], end: Tuple[int,int], steps: int) -> list[Tuple[int,int]]:
    (x0, y0), (x2, y2) = start, end
    mx, my = (x0 + x2)/2, (y0 + y2)/2
    dx = (x2 - x0) * rand_uniform(-0.5, 0.5)
    dy = (y2 - y0) * rand_uniform(-0.5, 0.5)
    x1, y1 = mx + dx, my + dy
    pts = []
    for i in range(steps):
        t = i / (steps - 1)
        x = (1 - t)**2 * x0 + 2*(1 - t)*t*x1 + t**2 * x2
        y = (1 - t)**2 * y0 + 2*(1 - t)*t*y1 + t**2 * y2
        jitter_scale = 0.8 * (math.sin(t * math.pi) ** 2)
        if random.random() < 0.1:
            jitter_scale *= 1.5
        x += rand_uniform(-3, 3) * jitter_scale
        y += rand_uniform(-3, 3) * jitter_scale
        pts.append((int(round(x)), int(round(y))))
    return pts


def perform_move(target: Tuple[int,int], duration: float, config: Config):
    start_pos = pyautogui.position()
    if dist(start_pos, target) < config.min_move:
        if config.dry_run:
            logging.info("[MOVE] Skipped (too close) %s -> %s", start_pos, target)
        else:
            jitter_x = start_pos[0] + random.randint(-config.min_move, config.min_move)
            jitter_y = start_pos[1] + random.randint(-config.min_move, config.min_move)
            pyautogui.moveTo(jitter_x, jitter_y, duration=0.05)
        return

    steps = max(8, int(duration * rand_uniform(40, 80)))
    path = bezier_path(start_pos, target, steps)
    if config.dry_run:
        logging.info("[MOVE] %s -> %s duration=%.2fs steps=%d", start_pos, target, duration, len(path))
        return

    start_time = time.time()
    for i, (x, y) in enumerate(path):
        elapsed = time.time() - start_time
        remaining = max(0.0, duration - elapsed)
        steps_left = len(path) - i
        if steps_left <= 0:
            break
        sleep_chunk = remaining / steps_left
        speed_variation = rand_uniform(0.8, 1.2)
        chunk_dur = max(0.001, sleep_chunk * speed_variation)
        pyautogui.moveTo(x, y, duration=chunk_dur)


def perform_micro_move(config: Config):
    """Tiny restless movement around current position."""
    current = pyautogui.position()
    hops = random.randint(2, 4)
    if config.dry_run:
        logging.info("[MICRO-MOVE] starting at %s with %d hops", current, hops)
        return
    for idx in range(hops):
        angle = rand_uniform(0, 2 * math.pi)
        r = rand_uniform(2, config.micro_move_radius)
        nx = int(round(current[0] + math.cos(angle) * r))
        ny = int(round(current[1] + math.sin(angle) * r))
        pyautogui.moveTo(nx, ny, duration=rand_uniform(0.05, 0.18))
        if random.random() < 0.35 and idx < hops - 1:
            time.sleep(rand_uniform(0.05, 0.2))


def maybe_click(config: Config):
    # Human-like clicking with occasional double-clicks
    right = random.random() < config.right_click_probability
    btn = 'right' if right else 'left'
    
    # Check for double-click
    is_double = random.random() < config.double_click_probability
    clicks = 2 if is_double else 1
    
    if config.dry_run:
        logging.info("[CLICK] button=%s clicks=%d", btn, clicks)
    else:
        # small correction movement before click
        if random.random() < 0.3:
            pyautogui.moveRel(rand_uniform(-5, 5), rand_uniform(-5, 5), duration=rand_uniform(0.04, 0.12))
        if clicks == 1:
            pyautogui.click(button=btn)
        else:
            # Double-click with slight human delay
            pyautogui.click(button=btn)
            time.sleep(rand_uniform(0.08, 0.15))
            pyautogui.click(button=btn)
        # slight mouse drift after click
        if random.random() < 0.25:
            pyautogui.moveRel(rand_uniform(-6, 6), rand_uniform(-4, 4), duration=rand_uniform(0.05, 0.14))
    return True


def maybe_scroll(config: Config):
    # More natural scrolling - smaller amounts, varied speeds
    amt = random.randint(config.scroll_amount_min, config.scroll_amount_max)
    direction = -1 if random.random() < 0.5 else 1  # pyautogui: positive is up
    scroll_val = direction * amt
    
    if config.dry_run:
        logging.info("[SCROLL] amount=%d", scroll_val)
    else:
        # Sometimes do multiple small scrolls instead of one big one (more human)
        if abs(scroll_val) > 100 and random.random() < 0.4:
            # Break into 2-3 smaller scrolls
            num_scrolls = random.randint(2, 3)
            per_scroll = scroll_val // num_scrolls
            for i in range(num_scrolls):
                pyautogui.scroll(per_scroll)
                if i < num_scrolls - 1:
                    time.sleep(rand_uniform(0.05, 0.15))
        elif random.random() < 0.25:
            # short hover with tiny move before a single scroll
            pyautogui.moveRel(rand_uniform(-4, 4), rand_uniform(-4, 4), duration=rand_uniform(0.04, 0.1))
            pyautogui.scroll(scroll_val)
        else:
            pyautogui.scroll(scroll_val)
        # occasional scroll correction in opposite direction
        if random.random() < 0.2:
            correction = int(scroll_val * rand_uniform(-0.3, -0.1))
            if correction != 0:
                time.sleep(rand_uniform(0.05, 0.2))
                pyautogui.scroll(correction)
    return True


def action_loop(state: State, config: Config):
    iteration = 0
    # schedule first click/scroll
    state.schedule_next_click(config)
    state.schedule_next_scroll(config)
    while True:
        with state.lock:
            if not state.running:
                break
            paused = state.paused
        if paused:
            time.sleep(0.5)
            continue
        iteration += 1
        
        # Occasional "thinking" pause before action (human-like)
        if random.random() < config.pause_probability:
            think_pause = rand_uniform(config.pause_duration_min, config.pause_duration_max)
            if config.verbose or config.dry_run:
                logging.info("[PAUSE] Thinking pause: %.2fs", think_pause)
            time.sleep(think_pause)
        
        did_micro_move = False
        if random.random() < config.micro_move_probability:
            perform_micro_move(config)
            did_micro_move = True

        if not did_micro_move:
            target = choose_point(config)
            move_duration = rand_uniform(config.move_duration_min, config.move_duration_max)
            perform_move(target, move_duration, config)

        now = time.time()
        # perform scheduled click if due
        if now >= state.next_click_at:
            if random.random() < 0.25:
                # hesitate, reschedule slightly into future
                delay = rand_uniform(6.0, 22.0)
                state.next_click_at = now + delay
                if config.verbose or config.dry_run:
                    logging.info("[CLICK] Deferred by %.1fs", delay)
            else:
                maybe_click(config)
                state.schedule_next_click(config)
        # perform scheduled scroll if due
        if now >= state.next_scroll_at:
            if random.random() < 0.3:
                delay = rand_uniform(5.0, 18.0)
                state.next_scroll_at = now + delay
                if config.verbose or config.dry_run:
                    logging.info("[SCROLL] Deferred by %.1fs", delay)
            else:
                maybe_scroll(config)
                state.schedule_next_scroll(config)
        sleep_time = rand_uniform(config.min_sleep, config.max_sleep)
        if config.verbose or config.dry_run:
            logging.info("[SLEEP] %.2fs (iteration %d)", sleep_time, iteration)
        time.sleep(sleep_time)
        # occasional longer pause to simulate focus or getting distracted
        if random.random() < config.long_pause_probability:
            long_pause = rand_uniform(config.long_pause_min, config.long_pause_max)
            if config.verbose or config.dry_run:
                logging.info("[PAUSE] Long pause: %.2fs", long_pause)
            time.sleep(long_pause)
    logging.info("Loop terminated.")


def keyboard_listener(state: State):
    COMBO_PAUSE = {keyboard.Key.ctrl, keyboard.Key.alt, keyboard.KeyCode.from_char('p')}
    COMBO_QUIT = {keyboard.Key.ctrl, keyboard.Key.alt, keyboard.KeyCode.from_char('q')}
    current_keys = set()

    def on_press(key):
        current_keys.add(key)
        if COMBO_PAUSE.issubset(current_keys):
            state.toggle_pause()
        if COMBO_QUIT.issubset(current_keys):
            state.stop()
            return False  # stop listener

    def on_release(key):
        if key in current_keys:
            current_keys.remove(key)

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()


def parse_args() -> Config:
    p = argparse.ArgumentParser(description="Random mouse mover / anti-AFK utility")
    p.add_argument('--min-sleep', type=float, default=3.0, help='Minimum seconds between action cycles.')
    p.add_argument('--max-sleep', type=float, default=12.0, help='Maximum seconds between action cycles.')
    p.add_argument('--move-duration-min', type=float, default=0.4, help='Minimum movement duration.')
    p.add_argument('--move-duration-max', type=float, default=1.6, help='Maximum movement duration.')
    p.add_argument('--margin', type=int, default=40, help='Margin from screen edges.')
    p.add_argument('--click-prob', type=float, default=0.55, help='Probability of a click per cycle.')
    p.add_argument('--right-click-prob', type=float, default=0.08, help='Probability that a click is right-click.')
    p.add_argument('--scroll-prob', type=float, default=0.25, help='Probability of a scroll per cycle.')
    p.add_argument('--scroll-min', type=int, default=40, help='Minimum scroll amount (absolute).')
    p.add_argument('--scroll-max', type=int, default=240, help='Maximum scroll amount (absolute).')
    p.add_argument('--dry-run', action='store_true', help='Do not actuate, only print actions.')
    p.add_argument('--seed', type=int, default=None, help='Random seed for reproducibility.')
    p.add_argument('--verbose', action='store_true', help='Verbose cycle logging.')
    p.add_argument('--prompt-interval', action='store_true', help='Prompt for min/max sleep interval interactively before start.')
    p.add_argument('--local-move', action='store_true', help='Enable local-only small moves (keep actions near current cursor).')
    p.add_argument('--move-radius', type=int, default=150, help='Radius in pixels for local moves.')
    p.add_argument('--no-centered', action='store_true', help='Disable center-limited movement (allow full or local moves).')
    p.add_argument('--center-fraction', type=float, default=0.8, help='Fraction of half-screen radius to allow when centered')
    p.add_argument('--click-interval-min', type=float, default=120.0, help='Minimum seconds between random clicks.')
    p.add_argument('--click-interval-max', type=float, default=480.0, help='Maximum seconds between random clicks.')
    p.add_argument('--scroll-interval-min', type=float, default=90.0, help='Minimum seconds between random scrolls.')
    p.add_argument('--scroll-interval-max', type=float, default=360.0, help='Maximum seconds between random scrolls.')
    p.add_argument('--min-move', type=int, default=DEFAULT_MIN_MOVE, help='Minimum move distance (pixels) to perform a full move.')
    p.add_argument('--no-hotkeys', action='store_true', help='Disable global hotkeys (use CTRL+C or window close to exit).')
    args = p.parse_args()
    return Config(
        min_sleep=args.min_sleep,
        max_sleep=args.max_sleep,
        move_duration_min=args.move_duration_min,
        move_duration_max=args.move_duration_max,
        margin=args.margin,
        click_probability=args.click_prob,
        right_click_probability=args.right_click_prob,
        scroll_probability=args.scroll_prob,
        scroll_amount_min=args.scroll_min,
        scroll_amount_max=args.scroll_max,
        dry_run=args.dry_run,
        seed=args.seed,
        verbose=args.verbose,
        min_move=args.min_move,
        prompt_interval=args.prompt_interval,
        local_move=args.local_move,
        move_radius=args.move_radius,
        centered=not args.no_centered,
        center_fraction=args.center_fraction,
        click_interval_min=args.click_interval_min,
        click_interval_max=args.click_interval_max,
        scroll_interval_min=args.scroll_interval_min,
        scroll_interval_max=args.scroll_interval_max,
        enable_hotkeys=not args.no_hotkeys,
    )


def prompt_for_interval(config: Config) -> None:
    """Prompt the user to enter a single value or a min-max for sleep interval.

    Accepted formats:
      - "5"        -> min=5, max=5
      - "3-7"      -> min=3, max=7
      - "3 7" or "3,7"
    Empty input keeps existing values.
    """
    logging.info("Enter sleep interval as a single number (e.g. 5) or min-max (e.g. 3-7). Leave empty to keep defaults.")
    while True:
        try:
            raw = input("Interval (min or min-max): ").strip()
        except (EOFError, KeyboardInterrupt):
            logging.info("No input provided — keeping defaults.")
            return
        if raw == "":
            logging.info("Keeping default min/max sleep: %.2f - %.2f", config.min_sleep, config.max_sleep)
            return
        # normalize separators
        norm = raw.replace(',', ' ').replace('-', ' ')
        parts = norm.split()
        try:
            if len(parts) == 1:
                v = float(parts[0])
                if v <= 0:
                    logging.warning("Interval must be positive.")
                    continue
                config.min_sleep = config.max_sleep = v
                logging.info("Using fixed interval: %.2fs", v)
                return
            elif len(parts) == 2:
                a = float(parts[0]); b = float(parts[1])
                if a <= 0 or b <= 0:
                    logging.warning("Intervals must be positive numbers.")
                    continue
                lo, hi = (a, b) if a <= b else (b, a)
                config.min_sleep = lo
                config.max_sleep = hi
                logging.info("Using interval: %.2f - %.2f seconds", lo, hi)
                return
            else:
                logging.warning("Couldn't parse input. Try '5' or '3-7'.")
        except ValueError:
            logging.warning("Invalid number format. Try again.")


def main():
    config = parse_args()
    # configure logging
    level = logging.DEBUG if config.verbose else logging.INFO
    logging.basicConfig(format='[%(levelname)s] %(message)s', level=level)

    platform_name = detect_platform()
    log_platform_notes(platform_name)

    if config.seed is not None:
        random.seed(config.seed)
    # prompt for interval if requested
    if config.prompt_interval:
        prompt_for_interval(config)
    state = State()
    # if centered mode requested, move cursor to center at startup
    if config.centered:
        w, h = pyautogui.size()
        cx, cy = w // 2, h // 2
        if config.dry_run:
            logging.info("[INIT] Would move cursor to center %s", (cx, cy))
        else:
            try:
                pyautogui.moveTo(cx, cy, duration=rand_uniform(0.2, 0.7))
            except Exception:
                logging.debug("Failed to move to center on startup")
    logging.info("Anti-AFK mouse mover started.")
    if config.dry_run:
        logging.info("Dry-run mode: no real input events will be sent.")
    if config.enable_hotkeys:
        logging.info("Hotkeys: CTRL+ALT+P pause/resume | CTRL+ALT+Q quit.")
        t_listener = threading.Thread(target=keyboard_listener, args=(state,), daemon=True)
        t_listener.start()
    else:
        logging.info("Hotkeys disabled. Use CTRL+C or close the window to exit.")
    logging.info("Move mouse to top-left corner to trigger PyAutoGUI fail-safe if needed.")
    try:
        action_loop(state, config)
    except pyautogui.FailSafeException:
        logging.warning("FailSafe triggered (moved to top-left). Exiting.")
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received. Exiting.")
    finally:
        state.stop()

if __name__ == '__main__':
    main()
