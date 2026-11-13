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

1. **T2 Modbus bus and timing.** One bus object per serial port: lock (one transaction at a
   time), minimum gap between transactions, retry policy that reports a final failure (today
   `attempt <= self.tries` is always true) and reads that return their value. Named constants
   for registers and command codes; device classes take a bus and an ID; node IDs in one place.
   The 250 ms barrier stagger stays in `main_ryan.py` for now (T16).

## Next

2. **T3 [P0] Sync the rig's newer `main_ryan` code** (`Fixed Cue On-Off Imaging`, `Rotate
   Train` at 10 pairs, other edits). The IP addresses are already done (T19); don't bring the
   rig's hard-coded addresses back in.
   The rig's copy still has the cue-light and LGTOM code removed in T1, so merge its changes into
   the repo's file rather than copying it over.
3. **T4 [P0] Session data folder into the local config** (rig: Seagate drive; repo: WD_BLACK).
4. **T6 [P0] Tag the as-run state** after T3, e.g. `as-run-2026-11-03`.
5. **T7 [P1] Lint and compile CI**: `py_compile` and pyflakes on the Python; `arduino-cli compile`
   with warnings for `arduino:avr:nano`; GitHub Actions on every push.

## Pool

- **T8 [P1] Schema startup check**: refuse to start if the database's `user_version` or columns
  don't match `schema.sql`; stamp the rig's copy (version 0, same layout) as version 1.
- **T9 [P3] Drop action-vector columns 27–30** (the retired cue lights). Nothing sets or acts on
  them since T1, but the readable action vector still shows them as its "UV Light" column (index 8),
  and removing the columns would shift every later index. Goes away with the action vectors in P3.
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
- **T18 `update_actuator_parameters` is broken and unused**: it indexes with `i` instead of
  `list_index` (pyflakes: undefined name), so it would raise if called; nothing calls it. Delete it
  or fix it with T2.

## Done

- **T5 [P0] Runtime files out of git.** `actuator_parameters.json`, `syringe_pump_parameters_list_30ml.json` and `state_variables_ryan.json` are ignored, each with a tracked `.example.json` (calibration examples taken from the rig on 2026-11-13); `actuator_parameters.json` is no longer tracked and the unused `syringe_pump_parameters_milk_30ml.json` is deleted. The rig's clone uses the files copied from the old folder.

- **T19 [P0] Pi addresses in an ignored local config.** `Ubuntu/local_config.py` reads
  `Ubuntu/local_config.json` (ignored; `local_config.example.json` is tracked) for the tracking
  Pi (`raspberrypi-d`) and the two display Pis (`raspberrypi-a`, `raspberrypi-b`); startup stops
  if the file is missing. The rig's file is written; `raspberrypi-c` (.29) is unused and didn't
  answer a ping. The session data folder (T4) can go in the same file.
- **T1 Dead cue-light code and the LGTOM session type removed.** `CueLight` and `BoardLights`
  classes; the four cue-light nodes created at startup; the UV buttons and their slots; the
  cue-light checks in the device worker and the action-vector runner; the cue-light entry in the
  shared state list (barrier and cue states moved up one place). LGTOM, the only session type that
  turned the lights on (57 sessions, 2022-04-22 to 2022-05-09), is retired: removed from the
  dialog, its action vectors and its session branch. Checked: both files compile, no references
  left, pyflakes shows no new undefined names. Not yet run on the rig.
- **Database**: rig database copied into `~/maze-control/Ubuntu` (ignored by git); one path for
  the Qt and sqlite3 connections; startup stops if the file is missing; `Ubuntu/schema.sql` and
  the README's Database section. `eced3b0`
- **Plan**: `Docs/refactor_plan.md`. `bdaa6db`
- **Unused `npsocket` import** removed from `main_ryan.py`. `56b6a98`
- **Rig setup** (not in git): DNS fixed; deploy key and clone at `~/maze-control`; snapshot of the
  old folder on the rig and this Mac.
