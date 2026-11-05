# maze-control refactor and CI plan

Drafted 2026-11-03. Goal: a tested, CI-checked control program built
around an explicit session engine, deployed to the rig from `~/maze-control` (a clone of this
repository) instead of the untracked `~/PycharmProjects/MazeControl`.

Ground rules

- `Ubuntu/main_2c2s.py` is not edited: the context package (`../docs/context/`) cites its line
  numbers. All changes go into `main_ryan.py` and the shared modules.
- The repository is public: real IP addresses, data paths and the databases stay out of git
  (local config file, ignored).
- Every session type in `main_ryan.py` keeps working (about 60: 55 with a start-goal branch in
  `generate_start_goal_pairs`, plus Exposure, the LGT dialog types and `Fixed Cue On-Off Imaging`).
- The refactor reproduces current behaviour exactly, including the white noise as it is now.
  Protocol changes (see Findings) are separate, deliberate and recorded.
- New or changed protocols are previewed and approved (P2c) before their goldens enter CI:
  CI checks the code still does what was approved; the preview checks it does what was intended.
- CD stops at a tagged release. The rig pulls a tag by hand, between sessions, with someone present.

## Phases

| Phase | Work | Depends on | Parallel? |
|---|---|---|---|
| P0 | Sync rig → repo: the rig's newer `main_ryan .py` (On-Off session type, Rotate Train 10 pairs), the missing `npsocket.py`; real IPs, data folder and DB path moved to an ignored local config; one DB path for both the Qt and sqlite3 connections | — | no |
| P1 | CI layer 0: dependencies exported from the rig's `mazeControlpy11` conda env; headless import (`QT_QPA_PLATFORM=offscreen`, stubbed serial and PortAudio); `arduino-cli compile` for the three sketches (board to confirm, probably classic Nano); schema checks: build a fresh database from `Ubuntu/schema.sql`, prepare every SQL string in the code against it; startup check on the rig that the live database's `user_version` (or columns) matches what the code expects, refusing to start a session otherwise (a database copied before versioning has `user_version` 0 with the version-1 layout); GitHub Actions | P0 | no |
| P2a | Harness fakes at four boundaries: recording devices (barriers, pumps, cue lights, lights), scripted rat (sets `WorkerSessionVideoThread.zone`), virtual clock (`time.time`/`time.sleep`, advancing on each call so busy loops finish), fake `SoundControl` (noise on/off) | P1 | no |
| P2b | Golden recordings from the current code at the device-command level: every session type × seeds × scenarios (all correct, errors, reaching criterion, timeouts); also replay real sessions from the `session_event` table (zone entries with timestamps); harness sessions write into a database built from `schema.sql` and read the rows back | P2a | no |
| P2c | Protocol preview (validation before CI): a local web page draws a cartoon maze from the zone and door registry (`zones.json`, `doors.json`, vendored with a hash manifest since this repository is public) and animates a virtual rat with barriers, cues, cue lights, rewards, noise, trial count and criterion, plus an event timeline. Replay mode after P2a (scripted runs and real sessions from `session_event`, driven by the harness on a watchable clock); interactive mode after P3a (drive the rat by clicking zones or with the keyboard, each input an engine event). An approved run is saved as that session type's golden, so what the experimenter signed off is what CI enforces | P2a (replay), P3a (interactive) | replay overlaps P2b |
| P3a | Session engine core: explicit trial state machine driven by events (zone entered, timeout, criterion met); protocols as data (base protocol + modifiers: Imaging, Twist, Cue On in ITI, Switch/Detour/Reverse/Cue-off at criterion); configuration rules computed per trial; device interface (barriers, cues, pumps, lights, audio). First family migrated: Fixed Cue | P2b | no |
| P3b | Family migrations, each passing its goldens with the old path kept until it does: Diff LGT, Cue Delay, Rotate, Dark, Twist, Switch/Detour/Reverse, Exposure/LGT | P3a | yes, one session per family |
| P4 | Wire-level virtual rig: simulated Modbus nodes (pymodbus) on virtual serial ports with the real IDs and register maps, including nodes that stop listening during a move; full session run in CI | P3a | overlaps P3b |
| P5 | Firmware: non-blocking actuator state machine with a busy/status register (removes `clearBuffer`, fixes `doNothing;`); light PWM clamp to 0–255; host-side unit tests of the motion logic | — | yes, any time |
| P6 | Bus behaviour: Modbus wrapper fixes; Python polls the actuator status register; retune or drop the 250 ms stagger (keep it if the 12 V rail needs it) | P4, P5 | no |
| P7 | Cutover at the rig: PyCharm run config on `~/maze-control`, same database, dry run with barriers powered, then a real session | all | no, at the rig |

## Findings to fix (from the 2026-11-03 review)

Bugs (safe to fix):

- `MazeControl_ZMQ.py` retry loops: `attempt <= self.tries` is always true, so a write that
  fails three times returns silently while the GUI has already flipped its state.
- `mc_read_register` never returns the value; `get_cycle_count()` is always `None`.
- `ActuatorControl_Modbus_Maze.ino`: `lowerBarrier` ends with `doNothing;` (no call); the
  blocking `delay()` move starves `poll()`, which is why `clearBuffer()` exists; commands sent to
  a node during its move are dropped; `clearBuffer` reads one byte too many.
- `Modbus_12V_PWM_Light_Control_Maze.ino`: no clamp; values above 255 wrap on the 8-bit timer.
- White noise: if the `DH80S` DAC is not found the session runs silently without masking noise
  (should block the session); the device search only checks indices below the default output.

Protocol questions (do not change in the refactor):

- White noise: N(0,1) into float32 full scale clips about 32% of samples; generated up to
  96 kHz (192 kHz rate) with no filtering, while the Methods state 50 Hz–20 kHz at about 60 dB.
  Any change is a new condition for future cohorts, re-measured with a sound meter.
- Barrier stagger of 250 ms between commands sets the order and timing of barrier moves.

## Rig notes

- Old folder `~/PycharmProjects/MazeControl` is left untouched; snapshot
  `~/MazeControl_snapshots/MazeControl_asrun_2026-11-03.tar.gz` (copy on the Mac, same SHA-256).
- New clone `~/maze-control`: fetch over HTTPS, push over SSH with the repository deploy key
  `~/.ssh/maze_control_deploy`.
- Runtime state files rewritten by the GUI (`actuator_parameters.json`,
  `syringe_pump_parameters_list_30ml.json`, `state_variables_ryan.json`) should become
  tracked defaults plus untracked local values.
