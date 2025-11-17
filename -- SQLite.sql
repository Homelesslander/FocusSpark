-- SQLite
CREATE TABLE IF NOT EXISTS custom_rewards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    title TEXT NOT NULL,
    cost INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS redemptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    reward_type TEXT NOT NULL,
    reward_id INTEGER,
    title TEXT,
    cost INTEGER,
    redeemed_at TEXT DEFAULT CURRENT_TIMESTAMP
);
