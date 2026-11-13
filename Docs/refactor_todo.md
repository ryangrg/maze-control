# maze-control refactor to-do

The working list for [refactor_plan.md](refactor_plan.md). The plan is the map (phases, ground
rules, what depends on what); this file is the queue of concrete work. Both change as we go.

How to use it

- Work one item at a time from **Now**. When it's done, move it to **Done** with its commit.
- Anything new we run into goes into **Pool** first, with a line on what and where.
- Reprioritise by moving items between sections or reordering them. IDs stay fixed, so they can
  be referred to after a reorder; new items take the next free number.
- Tags: `[P0]`…`[P7]` the plan phase it belongs to; **(goldens)** don't do before P2b, because it
  changes session flow and needs the golden tests to show nothing else changed; **(rig)** needs
  checking on the real maze; **(protocol)** changes what the rat experiences, so it is a
  decision for future cohorts, not a fix.

## Now

1. **T1 Remove dead cue-light code.** `CueLight` and `BoardLights` in `MazeControl_ZMQ.py`; the
   four `CueLight` objects at startup (IDs 2, 6, 10, 14, shared with actuators) and the cue-light
   buttons and slots in `main_ryan.py`. Leave the session-path check of action-vector columns
   27–30 for T9.
2. **T2 Modbus bus and timing.** One bus object per serial port: lock (one transaction at a
   time), minimum gap between transactions, retry policy that reports a final failure (today
   `attempt <= self.tries` is always true) and reads that return their value. Named constants
   for registers and command codes; device classes take a bus and an ID; node IDs in one place.
   The 250 ms barrier stagger stays in `main_ryan.py` for now (T16).

## Next

3. **T3 [P0] Sync the rig's newer `main_ryan` code** (`Fixed Cue On-Off Imaging`, `Rotate
   Train` at 10 pairs, other edits), with the real IP addresses moved into an ignored local config.
4. **T4 [P0] Session data folder into the local config** (rig: Seagate drive; repo: WD_BLACK).
5. **T5 [P0] Calibration files**: `actuator_parameters.json` and the syringe-pump JSON as tracked
   defaults plus untracked local values seeded from the rig. Must be done before anyone runs
   behaviour from `~/maze-control`, which otherwise uses stale barrier timings. (rig)
6. **T6 [P0] Tag the as-run state** after T3, e.g. `as-run-2026-11-03`.
7. **T7 [P1] Lint and compile CI**: `py_compile` and pyflakes on the Python; `arduino-cli compile`
   with warnings for `arduino:avr:nano`; GitHub Actions on every push.

## Pool

- **T8 [P1] Schema startup check**: refuse to start if the database's `user_version` or columns
  don't match `schema.sql`; stamp the rig's copy (version 0, same layout) as version 1.
- **T9 Remove the session-path cue-light handling** (action-vector columns 27–30, `main_ryan.py`
  around lines 100 and 7973). (goldens)
- **T10 Block a session when the noise DAC is missing** (today it only prints); fix the device
  search, which only checks devices numbered below the default output.
- **T11 [P5] Actuator firmware: non-blocking state machine** with a busy/status register;
  removes `clearBuffer`; also fixes `doNothing;` (no call) and the flush reading one byte too
  many. (rig)
- **T12 [P5] Light firmware: clamp PWM to 0–255** (values above 255 wrap on the 8-bit timer). (rig)
- **T13 Confirm the light board (ID 21) is a Nano** like the others. (rig)
- **T14 Pump `get_time`**: name the registers 5–7 and the `tc1*10000 + tc2*100 + tc3` decoding.
- **T15 Rig tidy-up at cutover**: PyCharm run config on `~/maze-control`; the live file is
  `main_ryan .py` (space in the name); archive the dated copies of `main_ryan` (leave other
  people's files alone); the rig's `~/.ssh/config` sets `User root` for every host.
- **T16 [P6] Retune or drop the 250 ms barrier stagger** after the firmware fix; keep it if the
  12 V rail needs it. (rig) (protocol)
- **T17 White noise level and band**: N(0,1) into float32 clips about 32% of samples, and the
  noise runs to 96 kHz while the Methods state 50 Hz–20 kHz at about 60 dB. (protocol)

## Done

- **Database**: rig database copied into `~/maze-control/Ubuntu` (ignored by git); one path for
  the Qt and sqlite3 connections; startup stops if the file is missing; `Ubuntu/schema.sql` and
  the README's Database section. `eced3b0`
- **Plan**: `Docs/refactor_plan.md`. `bdaa6db`
- **Unused `npsocket` import** removed from `main_ryan.py`. `56b6a98`
- **Rig setup** (not in git): DNS fixed; deploy key and clone at `~/maze-control`; snapshot of the
  old folder on the rig and this Mac.
