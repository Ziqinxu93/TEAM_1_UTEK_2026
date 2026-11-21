import ctypes
import math
import statistics
import sys
import threading
import time
from collections import deque
from pynput import mouse
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass  # already set (e.g. by main.py) or unsupported

# ---- tunable parameters (can be moved to config.py) ----
SAMPLE_INTERVAL = 0.02      # s, resampling interval (50 Hz)
SEGMENT_GAP = 0.2           # s, a pause longer than this ends a segment
MIN_SEGMENT_SAMPLES = 5     # shorter segments are discarded as unreliable
SMOOTHING_ALPHA = 0.4       # EMA factor applied to speed before differencing
ACC_THRESHOLD = 2000.0      # px/s^2, acceleration sign flips below this are ignored
MIN_REVERSAL_PX = 2.0       # px, ignore direction changes on tiny jitter moves
WINDOW = 60.0               # s, feature window
MIN_SEGMENTS = 3            # fewer segments in the window -> not enough data

SEGMENT_KEYS = (
    "speed",             # px/s, path length / duration
    "efficiency",        # 0-1, straight-line distance / path length
    "reversals",         # direction reversals per segment
    "peak_acc",          # px/s^2, max acceleration in segment
    "mean_abs_acc",      # px/s^2, mean |acceleration|
    "acc_sign_changes",  # accel/decel flips per segment (sub-movements)
    "time_to_peak",      # 0-1, time of peak speed / segment duration
)


class _Segment:
    """Running statistics for one continuous mouse movement."""

    def __init__(self, t, x, y):
        self.start_t = t
        self.start_pos = (x, y)
        self.last_t = t
        self.last_pos = (x, y)
        self.path = 0.0
        self.n = 1
        self.last_dx = 0.0
        self.last_dy = 0.0
        self.reversals = 0
        self.v_smooth = None
        self.peak_v = 0.0
        self.t_peak_v = t
        self.peak_acc = 0.0
        self.sum_abs_acc = 0.0
        self.n_acc = 0
        self.last_acc_sign = 0
        self.acc_sign_changes = 0

    def add(self, t, x, y):
        dt = t - self.last_t
        if dt <= 0:
            return
        dx = x - self.last_pos[0]
        dy = y - self.last_pos[1]
        d = math.hypot(dx, dy)
        self.path += d
        self.n += 1

        # Direction reversal: this step points against the previous one.
        if d >= MIN_REVERSAL_PX:
            if dx * self.last_dx + dy * self.last_dy < 0:
                self.reversals += 1
            self.last_dx, self.last_dy = dx, dy

        # Speed, smoothed with an EMA; acceleration from the smoothed speed.
        v = d / dt
        if self.v_smooth is None:
            self.v_smooth = v
        else:
            prev_v = self.v_smooth
            self.v_smooth = SMOOTHING_ALPHA * v + (1 - SMOOTHING_ALPHA) * prev_v
            acc = (self.v_smooth - prev_v) / dt
            self.peak_acc = max(self.peak_acc, acc)
            self.sum_abs_acc += abs(acc)
            self.n_acc += 1
            if abs(acc) > ACC_THRESHOLD:
                sign = 1 if acc > 0 else -1
                if self.last_acc_sign and sign != self.last_acc_sign:
                    self.acc_sign_changes += 1
                self.last_acc_sign = sign

        if self.v_smooth > self.peak_v:
            self.peak_v = self.v_smooth
            self.t_peak_v = t

        self.last_t = t
        self.last_pos = (x, y)

    def summary(self):
        """Return a dict of segment statistics, or None if too short."""
        duration = self.last_t - self.start_t
        if self.n < MIN_SEGMENT_SAMPLES or duration <= 0 or self.path <= 0:
            return None
        straight = math.hypot(self.last_pos[0] - self.start_pos[0],
                              self.last_pos[1] - self.start_pos[1])
        return {
            "end_t": self.last_t,
            "speed": self.path / duration,
            "efficiency": straight / self.path,
            "reversals": self.reversals,
            "peak_acc": self.peak_acc,
            "mean_abs_acc": self.sum_abs_acc / self.n_acc if self.n_acc else 0.0,
            "acc_sign_changes": self.acc_sign_changes,
            "time_to_peak": (self.t_peak_v - self.start_t) / duration,
        }


class MouseCollector:
    """Listens to the mouse in a background thread and exposes features."""

    def __init__(self, window=WINDOW):
        self.window = window
        self._lock = threading.Lock()
        self._segments = deque()   # finished segment summaries
        self._clicks = deque()     # (release_time, hold_duration)
        self._scrolls = deque()    # timestamps
        self._press_t = {}         # button -> press time
        self._current = None       # _Segment in progress
        self._last_sample_t = 0.0
        self._last_move_t = 0.0
        # Shared clock for activity.py: time.perf_counter()
        self.last_activity = time.perf_counter()
        self._listener = None

    # ---- lifecycle ----
    def start(self):
        self._listener = mouse.Listener(on_move=self._on_move,
                                        on_click=self._on_click,
                                        on_scroll=self._on_scroll)
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        if self._listener is not None:
            self._listener.stop()

    # ---- callbacks: keep these cheap (they run on the OS input thread) ----
    def _on_move(self, x, y):
        now = time.perf_counter()
        with self._lock:
            self.last_activity = now
            if self._current is not None and now - self._last_move_t > SEGMENT_GAP:
                self._close_segment()
            self._last_move_t = now
            if self._current is None:
                self._current = _Segment(now, x, y)
                self._last_sample_t = now
            elif now - self._last_sample_t >= SAMPLE_INTERVAL:
                self._current.add(now, x, y)
                self._last_sample_t = now

    def _on_click(self, x, y, button, pressed):
        now = time.perf_counter()
        with self._lock:
            self.last_activity = now
            if pressed:
                self._press_t[button] = now
            else:
                t0 = self._press_t.pop(button, None)
                if t0 is not None:
                    self._clicks.append((now, now - t0))

    def _on_scroll(self, x, y, dx, dy):
        now = time.perf_counter()
        with self._lock:
            self.last_activity = now
            self._scrolls.append(now)

    # ---- internals (call with lock held) ----
    def _close_segment(self):
        summary = self._current.summary()
        if summary is not None:
            self._segments.append(summary)
        self._current = None

    def _prune(self, now):
        cutoff = now - self.window
        while self._segments and self._segments[0]["end_t"] < cutoff:
            self._segments.popleft()
        while self._clicks and self._clicks[0][0] < cutoff:
            self._clicks.popleft()
        while self._scrolls and self._scrolls[0] < cutoff:
            self._scrolls.popleft()

    # ---- public API ----
    def get_features(self):
        """Features over the last `window` seconds, for scorer.py."""
        now = time.perf_counter()
        with self._lock:
            if self._current is not None and now - self._last_move_t > SEGMENT_GAP:
                self._close_segment()
            self._prune(now)
            segments = list(self._segments)
            clicks = list(self._clicks)
            n_scrolls = len(self._scrolls)

        minutes = self.window / 60.0
        features = {
            "segments": len(segments),
            "clicks_per_min": len(clicks) / minutes,
            "scrolls_per_min": n_scrolls / minutes,
            "click_hold_mean": (statistics.fmean(h for _, h in clicks)
                                if clicks else None),
            "enough_data": len(segments) >= MIN_SEGMENTS,
        }
        for key in SEGMENT_KEYS:
            features[key] = (statistics.fmean(s[key] for s in segments)
                             if features["enough_data"] else None)
        return features


if __name__ == "__main__":
    # Quick manual test, run from the repo root:  python -m collectors.mouse
    collector = MouseCollector()
    collector.start()
    print("Move the mouse around. Features print every 5 s. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(5)
            feats = collector.get_features()
            print({k: (round(v, 3) if isinstance(v, float) else v)
                   for k, v in feats.items()})
    except KeyboardInterrupt:
        collector.stop()