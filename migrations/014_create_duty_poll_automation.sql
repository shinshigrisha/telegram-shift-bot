CREATE TABLE IF NOT EXISTS duty_poll_configs (
    id SERIAL PRIMARY KEY,
    telegram_chat_id BIGINT NOT NULL,
    message_thread_id BIGINT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (telegram_chat_id, message_thread_id)
);

CREATE TABLE IF NOT EXISTS duty_poll_dispatches (
    id SERIAL PRIMARY KEY,
    config_id INTEGER NOT NULL REFERENCES duty_poll_configs(id) ON DELETE CASCADE,
    poll_date DATE NOT NULL,
    telegram_poll_id VARCHAR(255),
    telegram_message_id BIGINT,
    status VARCHAR(50) NOT NULL DEFAULT 'sending',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMP,
    UNIQUE (config_id, poll_date)
);

CREATE INDEX IF NOT EXISTS idx_duty_poll_dispatches_open
    ON duty_poll_dispatches (poll_date, status);
