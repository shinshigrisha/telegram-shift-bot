-- Create groups table for admin panel
CREATE TABLE IF NOT EXISTS groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    chat_id BIGINT NOT NULL UNIQUE,
    topic_id BIGINT,
    topic_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_groups_chat_id ON groups(chat_id);
