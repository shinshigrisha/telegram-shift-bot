-- Хранение факта автоматических напоминаний по опросам

CREATE TABLE IF NOT EXISTS poll_reminder_dispatches (
    id SERIAL PRIMARY KEY,
    poll_id UUID NOT NULL REFERENCES daily_polls(id) ON DELETE CASCADE,
    reminder_hour INTEGER NOT NULL,
    is_night BOOLEAN NOT NULL DEFAULT FALSE,
    sent_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (poll_id, reminder_hour, is_night)
);

CREATE INDEX IF NOT EXISTS idx_poll_reminder_dispatches_poll_id
    ON poll_reminder_dispatches (poll_id);
