-- Миграция: создание таблицы users для хранения информации о пользователях
-- Используется для верификации пользователей и управления их данными

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_user_id BIGINT UNIQUE NOT NULL,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    username VARCHAR(255),
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Индекс для быстрого поиска по telegram_user_id
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'telegram_user_id'
    ) THEN
        CREATE INDEX IF NOT EXISTS idx_users_telegram_user_id ON users (telegram_user_id);
    END IF;
END $$;

-- Индекс для поиска по статусу верификации
CREATE INDEX IF NOT EXISTS idx_users_is_verified ON users (is_verified);

-- Триггер для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_users_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_users_updated_at();
