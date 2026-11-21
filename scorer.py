import json
from pathlib import Path
from time import perf_counter as clock


timeCurve = ((0, 0), (15, 5), (30, 12), (60, 25), (90, 35), (120, 45))


def timeScore(seconds):
    minutes = seconds / 60
    for (start, low), (end, high) in zip(timeCurve, timeCurve[1:]):
        if minutes <= end:
            return low + scale(minutes, start, end, high - low)
    return 45


def scale(change, start, end, weight):
    return weight * min(1, max(0, (change - start) / (end - start)))


def keyValue(features, name, legacy):
    return features.get(name, features.get(legacy))


def scoreParts(workSeconds, keyboard, mouse, baseline):
    parts = dict(time=timeScore(workSeconds), backspace=None, keyInterval=None,
                 mouseSpeed=None, mouseRhythm=None)
    keys = baseline.get("keyboard", {})
    pointer = baseline.get("mouse", {})
    if keyValue(keyboard, "enough_data", "enough"):
        backspace = keyValue(keyboard, "backspace_ratio", "backspace")
        backspaceBase = keyValue(keys, "backspace_ratio", "backspace")
        interval = keyValue(keyboard, "iki_mean", "mean")
        intervalBase = keyValue(keys, "iki_mean", "mean")
        if backspace is not None and backspaceBase is not None:
            parts["backspace"] = scale(backspace - backspaceBase, .01, .05, 20)
        if interval is not None and (intervalBase or 0) > 0:
            parts["keyInterval"] = scale(interval / intervalBase - 1, .05, .20, 25)
    if mouse.get("enough_data"):
        if pointer.get("speed", 0) > 0 and mouse.get("speed") is not None:
            parts["mouseSpeed"] = scale(1 - mouse["speed"] / pointer["speed"], .05, .25, 10)
        if "acc_sign_changes" in pointer and mouse.get("acc_sign_changes") is not None:
            change = mouse["acc_sign_changes"] - pointer["acc_sign_changes"]
            parts["mouseRhythm"] = min(10 - (parts["mouseSpeed"] or 0), scale(change, .5, 2, 3))
    return parts


class fatigueScorer:
    def __init__(self, baseline=None):
        self.baseline = baseline or {}
        self.workSeconds = 0
        self.lastTime = None
        self.lastScreen = None
        self.screenOnSince = None

    def update(self, now, screen, lastActivity, keyboard, mouse, activity=None):
        lastTime = self.lastTime
        gap = now - lastTime if lastTime is not None else 0
        idle = activity is not None and activity["is_idle"]
        onBreak = activity is not None and activity["on_break"]
        if lastTime is None or gap > 15:
            self.screenOnSince = now if screen == "on" else None
        elif screen != self.lastScreen:
            self.screenOnSince = lastTime if screen == "on" else None
        elif screen == "off" or onBreak:
            self.workSeconds = max(0, self.workSeconds - 4 * gap)
        elif activity is not None and not idle:
            self.workSeconds += min(gap, activity["session_seconds"])
        elif screen == "on" and activity is None and lastActivity is not None and lastActivity >= self.screenOnSince:
            creditUntil = min(now, lastActivity + 60)
            self.workSeconds += max(0, creditUntil - lastTime)
        self.lastTime, self.lastScreen = now, screen

        if screen == "off" or idle or onBreak:
            keyboard, mouse = {}, {}
        parts = scoreParts(self.workSeconds, keyboard, mouse, self.baseline)
        return round(sum(points for points in parts.values() if points is not None), 2)


def liveReader():
    from collectors.keyboard import KeyboardCollector
    from collectors.mouse import MouseCollector
    from collectors.screen import screenCollector

    baseFile = Path(__file__).with_name("baseline.json")
    baseline = json.loads(baseFile.read_text(encoding="utf-8")) if baseFile.is_file() else {}
    scorer = fatigueScorer(baseline)
    keyboard, mouse, screen = KeyboardCollector(), MouseCollector(), screenCollector()
    screen.start()
    keyboard.start()
    mouse.start()

    def read(activity):
        screenState = screen.getFeatures()
        now = clock()
        keyboardAt, mouseAt = keyboard.last_activity, mouse.last_activity
        keys = keyboard.get_features() if now - keyboardAt <= 30 else {}
        pointer = mouse.get_features() if now - mouseAt <= 30 else {}
        return scorer.update(now, screenState, max(keyboardAt, mouseAt), keys, pointer, activity)

    return read


readLive = None


def getScore(activity=None):
    global readLive
    if readLive is None:
        readLive = liveReader()
    return readLive(activity)


get_score = getScore
