-- Миграция: добавление колонок для тем в таблицу groups
-- Выполнить: docker exec -it shift-bot-postgres psql -U bot_user -d shift_bot -f /docker-entrypoint-initdb.d/add_topic_columns.sql

ALTER TABLE groups 
ADD COLUMN IF NOT EXISTS arrival_departure_topic_id INTEGER,
ADD COLUMN IF NOT EXISTS general_chat_topic_id INTEGER;

COMMENT ON COLUMN groups.arrival_departure_topic_id IS 'ID темы "приход/уход" для отправки результатов опросов';
COMMENT ON COLUMN groups.general_chat_topic_id IS 'ID темы "общий чат" для отправки напоминаний';

