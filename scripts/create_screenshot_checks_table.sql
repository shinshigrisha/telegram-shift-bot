-- Создание таблицы для отслеживания времени последнего скриншота в теме 'приход/уход'
CREATE TABLE IF NOT EXISTS screenshot_checks (
    id SERIAL PRIMARY KEY,
    group_id INTEGER NOT NULL UNIQUE REFERENCES groups(id) ON DELETE CASCADE,
    last_screenshot_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Создание индекса для быстрого поиска по group_id
CREATE INDEX IF NOT EXISTS idx_screenshot_checks_group_id ON screenshot_checks(group_id);

-- Комментарии к таблице и колонкам
COMMENT ON TABLE screenshot_checks IS 'Отслеживание времени последнего скриншота в теме приход/уход для каждой группы';
COMMENT ON COLUMN screenshot_checks.group_id IS 'ID группы из таблицы groups';
COMMENT ON COLUMN screenshot_checks.last_screenshot_time IS 'Время последнего скриншота, отправленного в тему приход/уход';

