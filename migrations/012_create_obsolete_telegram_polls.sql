CREATE TABLE IF NOT EXISTS obsolete_telegram_polls (
    telegram_poll_id VARCHAR(255) PRIMARY KEY,
    group_id INTEGER,
    poll_date DATE,
    reason VARCHAR(100) NOT NULL DEFAULT 'recreated',
    retired_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_obsolete_telegram_polls_group_date
    ON obsolete_telegram_polls (group_id, poll_date);
