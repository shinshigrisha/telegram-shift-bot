CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    telegram_chat_id BIGINT UNIQUE NOT NULL,
    is_night BOOLEAN DEFAULT FALSE,
    poll_close_time TIME DEFAULT '19:00',
    settings JSONB NOT NULL DEFAULT '{"slots": [], "max_users_per_slot": 3}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_polls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
    poll_date DATE NOT NULL,
    telegram_poll_id VARCHAR(100),
    telegram_message_id BIGINT,
    telegram_topic_id INTEGER,
    status VARCHAR(20) DEFAULT 'active',
    screenshot_path TEXT,
    results JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(group_id, poll_date)
);

CREATE TABLE IF NOT EXISTS poll_slots (
    id SERIAL PRIMARY KEY,
    poll_id UUID REFERENCES daily_polls(id) ON DELETE CASCADE,
    slot_number INTEGER NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    max_users INTEGER DEFAULT 3,
    current_users INTEGER DEFAULT 0,
    user_ids JSONB DEFAULT '[]',
    CHECK (slot_number BETWEEN 1 AND 10),
    CHECK (max_users BETWEEN 1 AND 20)
);

CREATE TABLE IF NOT EXISTS user_votes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    poll_id UUID REFERENCES daily_polls(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    user_name VARCHAR(100),
    slot_id INTEGER REFERENCES poll_slots(id) ON DELETE SET NULL,
    voted_option VARCHAR(50),
    voted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(poll_id, user_id)
);

CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,  -- telegram user_id
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    username VARCHAR(100),
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS administrators (
    id SERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(100),
    full_name VARCHAR(200),
    is_super_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id VARCHAR(100),
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_daily_polls_group_date ON daily_polls(group_id, poll_date);
CREATE INDEX IF NOT EXISTS idx_daily_polls_status ON daily_polls(status);
CREATE INDEX IF NOT EXISTS idx_user_votes_poll_user ON user_votes(poll_id, user_id);
CREATE INDEX IF NOT EXISTS idx_user_votes_user_date ON user_votes(user_id, voted_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_users_verified ON users(is_verified);


