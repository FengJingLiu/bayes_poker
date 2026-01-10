"""SQLite 表结构定义（精简版 - 仅玩家查询）。"""

from __future__ import annotations

SCHEMA_VERSION = 2

CREATE_PLAYERS_TABLE = """
CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);
"""

CREATE_HANDS_TABLE = """
CREATE TABLE IF NOT EXISTS hands (
    hand_hash TEXT PRIMARY KEY,
    hash_version INTEGER NOT NULL DEFAULT 2,

    yyyymmdd INTEGER NOT NULL,
    hand_id INTEGER,
    table_name TEXT,
    seat_count INTEGER NOT NULL,
    button_seat INTEGER,

    phhs_blob BLOB NOT NULL,

    source TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"""

CREATE_HAND_PLAYERS_TABLE = """
CREATE TABLE IF NOT EXISTS hand_players (
    hand_hash TEXT NOT NULL REFERENCES hands(hand_hash) ON DELETE CASCADE,
    player_id INTEGER NOT NULL REFERENCES players(player_id),

    yyyymmdd INTEGER NOT NULL,
    seat_no INTEGER NOT NULL,
    rel_pos TEXT,
    starting_stack INTEGER,

    PRIMARY KEY (hand_hash, player_id),
    CHECK (seat_no > 0)
);
"""

CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_hand_players_player_date
    ON hand_players(player_id, yyyymmdd);

CREATE INDEX IF NOT EXISTS idx_hand_players_hand
    ON hand_players(hand_hash);

CREATE INDEX IF NOT EXISTS idx_hands_date
    ON hands(yyyymmdd);

CREATE INDEX IF NOT EXISTS idx_hands_hand_id
    ON hands(hand_id);
"""


def init_database(conn) -> None:
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    cursor.executescript(CREATE_PLAYERS_TABLE)
    cursor.executescript(CREATE_HANDS_TABLE)
    cursor.executescript(CREATE_HAND_PLAYERS_TABLE)
    cursor.executescript(CREATE_INDEXES)

    conn.commit()
