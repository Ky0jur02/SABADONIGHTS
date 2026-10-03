# Adventure-world redesign + Teacher Dashboard

Run as before: `python main.py` (Python 3.11, pygame, pyserial).

## Teacher access
* HOME now has **LOGIN** (students) and **TEACHER DASHBOARD**.
* First-run teacher account: `teacher` / `teacher123`.
  **Change it** with `python change_teacher_password.py`.
* Dashboard: student list -> per-activity summary (attempts, best score,
  average time, accuracy, latest status) with topic filter (LEFT/RIGHT)
  -> ENTER for previous attempts. ESC/BACKSPACE goes back one level.
  Everything is also clickable with the mouse.

## Data notes
* `attempts` got a nullable `session_id` column (safe `ALTER TABLE`);
  a new `teachers` table was added. No existing data is touched.
* Each game object gets a `session_id` so the ten questions of one play
  are grouped into one "attempt" on the dashboard.
* Rows saved BEFORE this update have no session_id, so each old row
  shows as its own one-question attempt. New plays group correctly.
* Status rule unchanged (score > 7 MASTERED, > 3 DEVELOPING, else
  NEEDS SUPPORT), now in `database.get_performance_status()`.

## Child screens
Result screens show only WELL DONE / SCORE / encouragement. Status and
average time are still calculated and saved, and shown to teachers only.

## Worlds (`WORLD_THEMES` in main.py)
HOME/Overworld, NUMBER BLOCK forest, MONEY underwater, CLOCK ice,
PIZZA FRACTION lava, MIXED QUICKSTART space, plus a clean TEACHER theme.
CLOCK / PIZZA FRACTION / MIXED QUICKSTART were placeholder screens in the
original code and remain placeholders (now themed).

## Inputs
All keyboard, serial/ESP32/NFC and money-button (MONEY_TOTAL) handling
is unchanged. Fonts: playful stack with automatic system fallback for
titles/buttons; original Arial fonts still render questions and the peso sign.
