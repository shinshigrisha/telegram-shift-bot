-- Миграция: исправление структуры таблицы users
-- Добавляет недостающие поля и индексы, если их нет

-- Добавляем поле telegram_user_id, если его нет
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'telegram_user_id'
    ) THEN
        ALTER TABLE users ADD COLUMN telegram_user_id BIGINT UNIQUE;
        
        -- Если в таблице уже есть данные, нужно будет заполнить telegram_user_id вручную
        -- Пока оставляем NULL, но добавляем NOT NULL constraint позже
    END IF;
END $$;

-- Изменяем тип id на SERIAL, если это еще не сделано
DO $$
BEGIN
    -- Проверяем, является ли id SERIAL
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' 
        AND column_name = 'id' 
        AND column_default LIKE 'nextval%'
    ) THEN
        -- Создаем последовательность, если её нет
        IF NOT EXISTS (SELECT 1 FROM pg_sequences WHERE sequencename = 'users_id_seq') THEN
            CREATE SEQUENCE users_id_seq;
        END IF;
        
        -- Устанавливаем значение последовательности на максимальный id + 1
        SELECT setval('users_id_seq', COALESCE((SELECT MAX(id) FROM users), 0) + 1);
        
        -- Устанавливаем default для id
        ALTER TABLE users ALTER COLUMN id SET DEFAULT nextval('users_id_seq');
    END IF;
END $$;

-- Изменяем размер полей first_name и last_name, если нужно
ALTER TABLE users 
    ALTER COLUMN first_name TYPE VARCHAR(255),
    ALTER COLUMN last_name TYPE VARCHAR(255),
    ALTER COLUMN username TYPE VARCHAR(255);

-- Создаем индекс для telegram_user_id, если его нет
CREATE INDEX IF NOT EXISTS idx_users_telegram_user_id ON users (telegram_user_id);

-- Переименовываем индекс, если он называется по-другому
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE tablename = 'users' AND indexname = 'idx_users_verified'
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE tablename = 'users' AND indexname = 'idx_users_is_verified'
    ) THEN
        ALTER INDEX idx_users_verified RENAME TO idx_users_is_verified;
    END IF;
END $$;

-- Создаем индекс для is_verified, если его нет
CREATE INDEX IF NOT EXISTS idx_users_is_verified ON users (is_verified);

-- Создаем или заменяем функцию для триггера updated_at
CREATE OR REPLACE FUNCTION update_users_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Создаем триггер, если его нет
DROP TRIGGER IF EXISTS trigger_update_users_updated_at ON users;
CREATE TRIGGER trigger_update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_users_updated_at();
