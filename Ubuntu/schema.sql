-- MazeControl.db schema, read by main_ryan.py (see README, Database).
-- Column order matches the rig's database; the later columns (e.g. session.total_switches,
-- session.delay, trial.cue_on) were added there with ALTER TABLE.
--
-- Build an empty database:  sqlite3 Ubuntu/MazeControl.db < Ubuntu/schema.sql
--
-- user_version identifies the schema. Version 1 is the layout of the rig's database on
-- 2026-11-03. Any change gets a new version and a numbered migration script; a database copied
-- from the rig before versioning has user_version 0 and the same layout as version 1.
PRAGMA user_version = 1;

CREATE TABLE subjects(
    subject_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    sex TEXT,
    behavior TEXT,
    last_session TEXT,
    cue_goal_orientation TEXT,
    session_type TEXT,
    active INTEGER DEFAULT 1,
    state TEXT,
    reward_volume INTEGER,
    delay INTEGER,
    date_of_birth TEXT
);

CREATE TABLE session(
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_number TEXT,
    date TEXT,
    time TEXT,
    behavior TEXT,
    session_type TEXT,
    cue_conf TEXT,
    session_duration REAL,
    total_trials INTEGER,
    total_perfect INTEGER,
    score TEXT,
    total_errors INTEGER,
    average_errors REAL,
    seed INTEGER,
    conf_file TEXT,
    coordinate_history_file TEXT,
    session_event_history_file NUMERIC,
    video_file TEXT,
    subject_id INTEGER NOT NULL,
    reward_volume INTEGER,
    average_latency INTEGER,
    score_string TEXT,
    total_switches INTEGER,
    delay INTEGER,
    FOREIGN KEY(subject_id) REFERENCES subjects(subject_id)
);

CREATE TABLE trial(
    trial_number INTEGER,
    start_arm TEXT,
    goal_location TEXT,
    cue_orientation TEXT,
    time_duration INTEGER,
    errors INTEGER,
    session_type TEXT,
    trial_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    turn_1 TEXT,
    turn_2 TEXT,
    perseveration_score INTEGER,
    first_error INTEGER,
    cue_on INTEGER,
    goal_zones_visited TEXT,
    FOREIGN KEY(session_id) REFERENCES session(session_id)
);

CREATE TABLE session_event(
    session_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_vector_idx INTEGER,
    action_vector_type TEXT,
    frame INTEGER,
    time_stamp INTEGER,
    zone INTEGER,
    x_coordinate INTEGER,
    y_coordinate INTEGER,
    time_duration INTEGER,
    start_arm TEXT,
    goal_location TEXT,
    cue_orientation TEXT,
    session_id INTEGER NOT NULL,
    FOREIGN KEY(session_id) REFERENCES session(session_id)
);
