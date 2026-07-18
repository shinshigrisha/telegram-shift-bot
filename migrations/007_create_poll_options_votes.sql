-- Миграция: создание таблиц poll_options и user_votes для детального учета голосов
-- Расширяет функциональность системы опросов

-- Таблица вариантов ответов опроса
-- poll_id имеет тип UUID для соответствия daily_polls.id
CREATE TABLE IF NOT EXISTS poll_options (
    id SERIAL PRIMARY KEY,
    poll_id UUID REFERENCES daily_polls(id) ON DELETE CASCADE,
    option_index INTEGER NOT NULL,  -- Индекс варианта (0, 1, 2, ...)
    option_text TEXT NOT NULL,      -- Текст варианта (например, "07:30-19:30 (лимит: 3)")
    slot_start TIME,                -- Время начала слота
    slot_end TIME,                  -- Время окончания слота
    max_users INTEGER DEFAULT 3,    -- Максимальное количество пользователей
    current_count INTEGER DEFAULT 0, -- Текущее количество голосов
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(poll_id, option_index)
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'poll_options' AND column_name = 'option_index'
    ) THEN
        ALTER TABLE poll_options ADD COLUMN option_index INTEGER;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'poll_options' AND column_name = 'option_text'
    ) THEN
        ALTER TABLE poll_options ADD COLUMN option_text TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'poll_options' AND column_name = 'slot_start'
    ) THEN
        ALTER TABLE poll_options ADD COLUMN slot_start TIME;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'poll_options' AND column_name = 'slot_end'
    ) THEN
        ALTER TABLE poll_options ADD COLUMN slot_end TIME;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'poll_options' AND column_name = 'max_users'
    ) THEN
        ALTER TABLE poll_options ADD COLUMN max_users INTEGER DEFAULT 3;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'poll_options' AND column_name = 'current_count'
    ) THEN
        ALTER TABLE poll_options ADD COLUMN current_count INTEGER DEFAULT 0;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'poll_options' AND column_name = 'created_at'
    ) THEN
        ALTER TABLE poll_options ADD COLUMN created_at TIMESTAMP DEFAULT NOW();
    END IF;
END $$;

-- Таблица голосов пользователей
CREATE TABLE IF NOT EXISTS user_votes (
    id SERIAL PRIMARY KEY,
    poll_id UUID REFERENCES daily_polls(id) ON DELETE CASCADE,
    option_id INTEGER REFERENCES poll_options(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,        -- Telegram User ID
    user_name VARCHAR(255),         -- Имя пользователя (@username или first_name)
    full_name VARCHAR(255),         -- Полное имя (first_name + last_name)
    voted_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(poll_id, user_id, option_id)
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_votes' AND column_name = 'option_id'
    ) THEN
        ALTER TABLE user_votes ADD COLUMN option_id INTEGER;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_votes' AND column_name = 'full_name'
    ) THEN
        ALTER TABLE user_votes ADD COLUMN full_name VARCHAR(255);
    END IF;
END $$;

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_poll_options_poll_id ON poll_options (poll_id);
CREATE INDEX IF NOT EXISTS idx_user_votes_poll_id ON user_votes (poll_id);
CREATE INDEX IF NOT EXISTS idx_user_votes_user_id ON user_votes (user_id);
CREATE INDEX IF NOT EXISTS idx_user_votes_option_id ON user_votes (option_id);

-- Добавляем новые поля в daily_polls, если их нет
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'daily_polls' AND column_name = 'screenshot_path'
    ) THEN
        ALTER TABLE daily_polls ADD COLUMN screenshot_path TEXT;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'daily_polls' AND column_name = 'closed_at'
    ) THEN
        ALTER TABLE daily_polls ADD COLUMN closed_at TIMESTAMP;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'daily_polls' AND column_name = 'reminder_sent'
    ) THEN
        ALTER TABLE daily_polls ADD COLUMN reminder_sent BOOLEAN DEFAULT FALSE;
    END IF;
END $$;
