-- Миграция: добавление колонки telegram_topic_id в таблицу groups
-- Выполнить: docker exec -it shift-bot-postgres psql -U bot_user -d shift_bot -f /docker-entrypoint-initdb.d/add_topic_id_column.sql
-- Или через psql напрямую

ALTER TABLE groups 
ADD COLUMN IF NOT EXISTS telegram_topic_id INTEGER;

COMMENT ON COLUMN groups.telegram_topic_id IS 'ID темы (topic) для форум-групп Telegram, куда будут отправляться опросы';

