# Systemic Fatigue Monitor (UTEK 2026 Programming, Team 1)

This is a lightweight background program that estimates how tired a user is from ordinary computer use. It needs no wearables or extra sensors. Every 5 seconds it writes a **Systemic Fatigue Score (0–100)** to a local JSON file. When the score shows that the user really needs a break, it shows a reminder.

## Team

- Penghao Li
- Ziqin Xu

## Requirements

- Windows (the reminder pop-up and the screen on/off detection use Windows APIs)
- Python 3
- [pynput](https://github.com/moses-palmer/pynput) is the only third-party dependency. Everything else is from the Python standard library.

## Installation

```bash
git clone https://github.com/Ziqinxu93/TEAM_1_UTEK_2026.git
cd TEAM_1_UTEK_2026
python -m pip install -r requirements.txt
```

## Running

```bash
python main.py
```

The program starts listening in the background. Every 5 seconds it overwrites `output.json` in the current folder. The file has three fields: `timestamp`, `score` (0–100) and `status`.

- The next write is scheduled from the previous scheduled time (on a monotonic clock), so the 5-second interval does not drift.
- The file is first written to `output.json.tmp` and then swapped in with `os.replace`, so a reader never sees a half-written file.

## Deployment (running in the background)

- **No console window:** run `pythonw main.py` instead of `python main.py`. To stop it, end the `pythonw.exe` process in Task Manager.
- **Start automatically at login:** press `Win + R`, type `shell:startup`, and put a shortcut to `pythonw main.py` in that folder. Set the shortcut's **Start in** field to the project folder so `output.json` is written there.

## How it works

```
collectors/keyboard.py ─┐
collectors/mouse.py ────┼──>  scorer.py  ──>  broadcaster.py  ──>  output.json (every 5 s)
collectors/activity.py ─┤          │
collectors/screen.py ───┘          └──────>  intervention.py  ──>  break reminder

main.py starts all modules and runs the 5-second loop.
```

Collection, scoring, broadcasting and intervention are separate modules.

| Module | What it does |
|---|---|
| `collectors/keyboard.py` | Typing rhythm over the last 60 seconds: keystrokes, keys per minute, inter-key interval (mean, standard deviation, coefficient of variation), backspace ratio and key hold time. Pauses longer than 2 s are not counted as intervals. Needs at least 20 keystrokes. |
| `collectors/mouse.py` | Samples the cursor every 20 ms. A pause longer than 0.2 s ends a movement segment. For each segment it computes speed, path efficiency, direction reversals and acceleration (peak, mean absolute value, sign changes, time to peak speed). It also records clicks per minute, click hold time and scrolls per minute. Uses the last 60 seconds and needs at least 3 segments. |
| `collectors/activity.py` | Uses the last keyboard and mouse activity to track idle time (60 s or more), breaks (120 s or more), continuous session length, length of the last break and breaks in the last hour. |
| `collectors/screen.py` | Subscribes to Windows display power notifications to know whether the screen is on or off. |
| `scorer.py` | Combines the features into one 0–100 fatigue score (see below). |
| `broadcaster.py` | Writes the score to `output.json` safely. |
| `intervention.py` | Decides when to show a break reminder. |
| `baseline.json` | The user's personal baseline values. Keyboard and mouse features are compared with these values, not with a fixed standard. |

### How the score is calculated

| Part | Points | What raises it |
|---|---|---|
| Continuous work time | 0–45 | Time actually spent working: 5 points at 15 min, 12 at 30 min, 25 at 60 min, 35 at 90 min, 45 at 120 min or more |
| Backspace ratio | 0–20 | Backspace ratio higher than the baseline: starts at +1 percentage point, full at +5 |
| Inter-key interval | 0–25 | Typing slower than the baseline: starts at 5% slower, full at 20% slower |
| Mouse speed | 0–10 | Mouse slower than the baseline: starts at 5% slower, full at 25% slower |
| Mouse rhythm | 0–3 | More acceleration sign changes than the baseline (less smooth movement). Mouse speed and rhythm together are capped at 10 |

- Work time only grows while the user is active. While the screen is off or the user is on a break, it goes down 4 times as fast as it built up, so the score recovers after rest.
- Keyboard and mouse parts are skipped when there is not enough data, when that device has had no input for 30 s, when the user is idle or on a break, or when the screen is off.
- If `baseline.json` has no value for a part, that part is skipped.

### When a reminder appears

1. When the fatigue score goes above 60, one reminder appears. It is triggered by the user's state, not by a timer.
2. After that, no more reminders appear, however high the score gets.
3. When the user takes a break (2 minutes or more away from the computer), the reminder resets. If the score goes above 60 again after the user comes back, one more reminder appears.

The reminder is a Windows message box shown on a separate thread, so it never blocks scoring or the 5-second output.

## Customization

All parameters are constants at the top of each file or in `baseline.json`, so they can be tuned for different users without changing the logic.

| File | What you can tune |
|---|---|
| `baseline.json` | The user's personal baseline: keyboard `mean` (inter-key interval) and `backspace` (backspace ratio). Mouse `speed` and `acc_sign_changes` can be added under `"mouse"` to turn on the mouse parts of the score. |
| `scorer.py` | `timeCurve` (minutes of work → points), and the start point, full point and maximum points of each part in `scoreParts`. |
| `intervention.py` | The score that triggers a reminder (60) and the reminder text. |
| `collectors/keyboard.py` | `window`, `pause`, `minkeys`, `maxhold`, `stale` |
| `collectors/mouse.py` | `SAMPLE_INTERVAL`, `SEGMENT_GAP`, `MIN_SEGMENT_SAMPLES`, `SMOOTHING_ALPHA`, `ACC_THRESHOLD`, `MIN_REVERSAL_PX`, `WINDOW`, `MIN_SEGMENTS` |
| `collectors/activity.py` | `idlemin` (idle threshold), `breakmin` (break threshold), `history` (break history length) |

## Privacy and efficiency

- No typed text is recorded. The keyboard collector keeps timestamps and whether a key was Backspace. Key codes are held only until the key is released, to measure hold time.
- Mouse positions stay in memory only long enough to compute movement statistics. Click positions are not stored.
- No screenshots, camera or microphone are used. The screen collector only knows whether the display is on or off.
- All feature data stays in memory in 60-second rolling windows. The only file written is `output.json`.
- The collectors use pynput event listeners, so the program does almost no work when the user is not typing or moving the mouse.

## References

1. **pynput**, by Moses Palmér. https://github.com/moses-palmer/pynput (LGPL-3.0). Used for the keyboard and mouse listeners.
2. Dhakal, V., Feit, A. M., Kristensson, P. O., & Oulasvirta, A. (2018). *Observations on Typing from 136 Million Keystrokes.* Proceedings of the 2018 CHI Conference on Human Factors in Computing Systems. https://doi.org/10.1145/3173574.3174220. Background for the typing features: inter-key interval, key hold time and error correction.
3. **AI assistance: Claude (Anthropic) and ChatGPT (OpenAI).**
   - We consulted AI to learn how to use Git, how to use various Python functions, how to implement the code and how to write a README.
   - AI-generated code: `collectors/mouse.py` and part of `scorer.py`.
