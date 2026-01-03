-- Миграция: создание таблицы knowledge_base для хранения chunks из PDF
-- Используется ТОЛЬКО для AI-куратора (RAG - Retrieval-Augmented Generation)
-- Хранит разбитый на chunks контент из PDF файлов для базы знаний

-- SQL для создания таблицы knowledge_base
-- Таблица безопасна для добавления в существующую БД:
-- - Использует IF NOT EXISTS (идемпотентность)
-- - Не имеет внешних ключей на другие таблицы
-- - Не изменяет существующие таблицы
-- - Изолирована от остальной схемы БД
CREATE TABLE IF NOT EXISTS knowledge_base (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    -- Уникальная комбинация source + chunk_index для предотвращения дубликатов
    CONSTRAINT unique_source_chunk UNIQUE (source, chunk_index)
);

-- Индекс для быстрого поиска по источнику
CREATE INDEX IF NOT EXISTS idx_knowledge_base_source ON knowledge_base (source);

-- Индекс для быстрого поиска по chunk_index
CREATE INDEX IF NOT EXISTS idx_knowledge_base_chunk_index ON knowledge_base (chunk_index);

-- Индекс для полнотекстового поиска по content (для RAG)
CREATE INDEX IF NOT EXISTS idx_knowledge_base_content_vector ON knowledge_base 
    USING GIN (to_tsvector('russian', content));

-- Триггер для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_knowledge_base_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Удаляем триггер, если он уже существует (для идемпотентности)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_trigger 
        WHERE tgname = 'trigger_update_knowledge_base_updated_at' 
        AND tgrelid = 'knowledge_base'::regclass
    ) THEN
        DROP TRIGGER trigger_update_knowledge_base_updated_at ON knowledge_base;
    END IF;
END $$;

CREATE TRIGGER trigger_update_knowledge_base_updated_at
    BEFORE UPDATE ON knowledge_base
    FOR EACH ROW
    EXECUTE FUNCTION update_knowledge_base_updated_at();

-- Комментарии к таблице и колонкам
COMMENT ON TABLE knowledge_base IS 'База знаний для AI-куратора: chunks из PDF файлов (RAG)';
COMMENT ON COLUMN knowledge_base.id IS 'Уникальный идентификатор chunk';
COMMENT ON COLUMN knowledge_base.source IS 'Источник chunk (например: Data.pdf)';
COMMENT ON COLUMN knowledge_base.chunk_index IS 'Порядковый номер chunk в источнике (начиная с 0)';
COMMENT ON COLUMN knowledge_base.content IS 'Содержимое chunk (текст длиной 500-800 символов)';
COMMENT ON COLUMN knowledge_base.created_at IS 'Дата и время создания записи';
COMMENT ON COLUMN knowledge_base.updated_at IS 'Дата и время последнего обновления записи';
