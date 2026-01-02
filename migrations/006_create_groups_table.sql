-- Создание таблицы groups для админ-панели
CREATE TABLE IF NOT EXISTS "groups" (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    chat_id BIGINT NOT NULL UNIQUE,
    topic_id BIGINT,
    topic_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_groups_chat_id ON "groups" (chat_id);
CREATE INDEX IF NOT EXISTS idx_groups_name ON "groups" (name);
