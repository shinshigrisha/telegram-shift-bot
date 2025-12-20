-- Миграция: создание таблицы users
-- Выполнить: docker exec -it shift-bot-postgres psql -U bot_user -d shift_bot -f /docker-entrypoint-initdb.d/create_users_table.sql
-- Или напрямую через psql

CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,  -- telegram user_id
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    username VARCHAR(100),
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_verified ON users(is_verified);

COMMENT ON TABLE users IS 'Таблица для хранения информации о пользователях бота';
COMMENT ON COLUMN users.id IS 'Telegram user_id (используется как PRIMARY KEY)';
COMMENT ON COLUMN users.is_verified IS 'Статус верификации пользователя (имя и фамилия введены)';

