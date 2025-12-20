-- Миграция: добавление колонки important_info_topic_id в таблицу groups
-- Выполнить: docker exec shift-bot-postgres psql -U bot_user -d shift_bot -f /docker-entrypoint-initdb.d/add_important_info_topic_id.sql
-- Или напрямую через psql

ALTER TABLE groups 
ADD COLUMN IF NOT EXISTS important_info_topic_id INTEGER;

COMMENT ON COLUMN groups.important_info_topic_id IS 'ID темы (topic) для форум-групп Telegram, куда будут отправляться важные информационные сообщения';

