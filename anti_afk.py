from __future__ import annotations
import argparse
import math
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
DEFAULT_MIN_MOVE = 8  # pixels: ignore tiny automatic moves that conflict with user

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

class State:
    def __init__(self):
        self.running = True
        self.paused = False
        self.lock = threading.Lock()

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


def choose_point(config: Config) -> Tuple[int, int]:
    width, height = pyautogui.size()
    x = random.randint(config.margin, width - config.margin)
    y = random.randint(config.margin, height - config.margin)
    return x, y


def bezier_path(start: Tuple[int,int], end: Tuple[int,int], steps: int) -> list[Tuple[int,int]]:
    # Quadratic Bezier with random control point near midpoint + jitter
    (x0, y0), (x2, y2) = start, end
    mx, my = (x0 + x2)/2, (y0 + y2)/2
    # Control point offset
    dx = (x2 - x0) * rand_uniform(-0.3, 0.3)
    dy = (y2 - y0) * rand_uniform(-0.3, 0.3)
    x1, y1 = mx + dx, my + dy
    pts = []
    for i in range(steps):
        t = i / (steps - 1)
        # Quadratic Bezier formula
        x = (1 - t)**2 * x0 + 2*(1 - t)*t*x1 + t**2 * x2
        y = (1 - t)**2 * y0 + 2*(1 - t)*t*y1 + t**2 * y2
        # jitter
        jitter_scale = 0.6 * (math.sin(t * math.pi) ** 2)
        x += rand_uniform(-2, 2) * jitter_scale
        y += rand_uniform(-2, 2) * jitter_scale
        pts.append((int(round(x)), int(round(y))))
    return pts


def perform_move(target: Tuple[int,int], duration: float, config: Config):
    start_pos = pyautogui.position()
    # If user moved the mouse recently (or target is too close), skip to avoid fighting them
    if dist(start_pos, target) < config.min_move:
        # do a small jitter instead of a full move to appear alive but not override user
        if config.dry_run:
            logging.info("[MOVE] Skipped (too close) %s -> %s", start_pos, target)
        else:
            jitter_x = start_pos[0] + random.randint(-config.min_move, config.min_move)
            jitter_y = start_pos[1] + random.randint(-config.min_move, config.min_move)
            pyautogui.moveTo(jitter_x, jitter_y, duration=0.05)
        return

    steps = max(6, int(duration * rand_uniform(30, 60)))
    path = bezier_path(start_pos, target, steps)
    if config.dry_run:
        logging.info("[MOVE] %s -> %s duration=%.2fs steps=%d", start_pos, target, duration, len(path))
        return

    # Use moveTo with small durations for smoother movement and fewer explicit sleeps
    start_time = time.time()
    for i, (x, y) in enumerate(path):
        elapsed = time.time() - start_time
        remaining = max(0.0, duration - elapsed)
        steps_left = len(path) - i
        if steps_left <= 0:
            break
        # allocate time for this chunk
        sleep_chunk = remaining / steps_left
        # clamp a minimal duration to avoid zero-duration rapid calls
        chunk_dur = max(0.001, sleep_chunk)
        pyautogui.moveTo(x, y, duration=chunk_dur)


def maybe_click(config: Config):
    if random.random() < config.click_probability:
        right = random.random() < config.right_click_probability
        btn = 'right' if right else 'left'
        if config.dry_run:
            logging.info("[CLICK] button=%s", btn)
        else:
            pyautogui.click(button=btn)
        return True
    return False


def maybe_scroll(config: Config):
    if random.random() < config.scroll_probability:
        amt = random.randint(config.scroll_amount_min, config.scroll_amount_max)
        direction = -1 if random.random() < 0.5 else 1  # pyautogui: positive is up
        scroll_val = direction * amt
        if config.dry_run:
            logging.info("[SCROLL] amount=%d", scroll_val)
        else:
            pyautogui.scroll(scroll_val)
        return True
    return False


def action_loop(state: State, config: Config):
    iteration = 0
    while True:
        with state.lock:
            if not state.running:
                break
            paused = state.paused
        if paused:
            time.sleep(0.5)
            continue
        iteration += 1
        target = choose_point(config)
        move_duration = rand_uniform(config.move_duration_min, config.move_duration_max)
        perform_move(target, move_duration, config)
        # random order of click/scroll attempt
        ops = [maybe_click, maybe_scroll]
        random.shuffle(ops)
        for op in ops:
            op(config)
        sleep_time = rand_uniform(config.min_sleep, config.max_sleep)
        if config.verbose or config.dry_run:
            logging.info("[SLEEP] %.2fs (iteration %d)", sleep_time, iteration)
        time.sleep(sleep_time)
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
    p.add_argument('--min-move', type=int, default=DEFAULT_MIN_MOVE, help='Minimum move distance (pixels) to perform a full move.')
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

    if config.seed is not None:
        random.seed(config.seed)
    state = State()
    logging.info("Anti-AFK mouse mover started.")
    logging.info("Hotkeys: CTRL+ALT+P pause/resume | CTRL+ALT+Q quit | Move mouse to top-left corner to FAILSAFE abort.")
    if config.dry_run:
        logging.info("Dry-run mode: no real input events will be sent.")
    # Start keyboard listener thread
    t_listener = threading.Thread(target=keyboard_listener, args=(state,), daemon=True)
    t_listener.start()
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
