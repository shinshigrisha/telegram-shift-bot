-- Миграция: создание единой таблицы unified_knowledge_base
-- Объединяет FAQ (faq_ai) и chunks из PDF (knowledge_base) в одну базу знаний
-- Используется ТОЛЬКО для AI-куратора (RAG - Retrieval-Augmented Generation)

-- SQL для создания единой таблицы базы знаний
-- Таблица безопасна для добавления в существующую БД:
-- - Использует IF NOT EXISTS (идемпотентность)
-- - Не имеет внешних ключей на другие таблицы
-- - Не изменяет существующие таблицы
-- - Изолирована от остальной схемы БД
CREATE TABLE IF NOT EXISTS unified_knowledge_base (
    id SERIAL PRIMARY KEY,
    -- Тип записи: 'faq' для FAQ или 'chunk' для chunks из PDF
    type VARCHAR(20) NOT NULL CHECK (type IN ('faq', 'chunk')),
    
    -- Поля для FAQ (используются только если type = 'faq')
    question TEXT,
    answer TEXT,
    keywords TEXT[] DEFAULT '{}',
    category VARCHAR(100),
    tag VARCHAR(100),
    
    -- Поля для chunks из PDF (используются только если type = 'chunk')
    source TEXT,
    chunk_index INTEGER,
    content TEXT,
    
    -- Вектор для полнотекстового поиска (общий для всех типов)
    search_vector tsvector,
    
    -- Временные метки
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Ограничения
    -- Для FAQ: question и answer обязательны
    CONSTRAINT check_faq_fields CHECK (
        (type = 'faq' AND question IS NOT NULL AND answer IS NOT NULL) OR
        (type != 'faq')
    ),
    -- Для chunks: source, chunk_index и content обязательны
    CONSTRAINT check_chunk_fields CHECK (
        (type = 'chunk' AND source IS NOT NULL AND chunk_index IS NOT NULL AND content IS NOT NULL) OR
        (type != 'chunk')
    ),
    -- Уникальность для chunks: source + chunk_index
    CONSTRAINT unique_unified_kb_source_chunk UNIQUE (source, chunk_index)
);

-- Индекс для быстрого поиска по типу
CREATE INDEX IF NOT EXISTS idx_unified_kb_type ON unified_knowledge_base (type);

-- Индекс для быстрого поиска по ключевым словам (для FAQ)
CREATE INDEX IF NOT EXISTS idx_unified_kb_keywords ON unified_knowledge_base USING GIN (keywords);

-- Индекс для полнотекстового поиска (GIN индекс для tsvector)
CREATE INDEX IF NOT EXISTS idx_unified_kb_search_vector ON unified_knowledge_base USING GIN (search_vector);

-- Индекс для поиска по категории и тегу (для FAQ)
CREATE INDEX IF NOT EXISTS idx_unified_kb_category ON unified_knowledge_base (category);
CREATE INDEX IF NOT EXISTS idx_unified_kb_tag ON unified_knowledge_base (tag);

-- Индекс для поиска по источнику (для chunks)
CREATE INDEX IF NOT EXISTS idx_unified_kb_source ON unified_knowledge_base (source);

-- Триггер для автоматического обновления search_vector
CREATE OR REPLACE FUNCTION update_unified_kb_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.type = 'faq' THEN
        -- Для FAQ: объединяем question и answer
        NEW.search_vector := to_tsvector('russian', COALESCE(NEW.question, '') || ' ' || COALESCE(NEW.answer, ''));
    ELSIF NEW.type = 'chunk' THEN
        -- Для chunks: используем content
        NEW.search_vector := to_tsvector('russian', COALESCE(NEW.content, ''));
    END IF;
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Удаляем триггер, если он уже существует (для идемпотентности)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_trigger 
        WHERE tgname = 'trigger_update_unified_kb_search_vector' 
        AND tgrelid = 'unified_knowledge_base'::regclass
    ) THEN
        DROP TRIGGER trigger_update_unified_kb_search_vector ON unified_knowledge_base;
    END IF;
END $$;

CREATE TRIGGER trigger_update_unified_kb_search_vector
    BEFORE INSERT OR UPDATE OF question, answer, content ON unified_knowledge_base
    FOR EACH ROW
    EXECUTE FUNCTION update_unified_kb_search_vector();

-- Триггер для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_unified_kb_updated_at()
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
        WHERE tgname = 'trigger_update_unified_kb_updated_at' 
        AND tgrelid = 'unified_knowledge_base'::regclass
    ) THEN
        DROP TRIGGER trigger_update_unified_kb_updated_at ON unified_knowledge_base;
    END IF;
END $$;

CREATE TRIGGER trigger_update_unified_kb_updated_at
    BEFORE UPDATE ON unified_knowledge_base
    FOR EACH ROW
    EXECUTE FUNCTION update_unified_kb_updated_at();

-- Комментарии к таблице и колонкам
COMMENT ON TABLE unified_knowledge_base IS 'Единая база знаний для AI-куратора: объединяет FAQ и chunks из PDF (RAG)';
COMMENT ON COLUMN unified_knowledge_base.type IS 'Тип записи: faq (FAQ) или chunk (chunk из PDF)';
COMMENT ON COLUMN unified_knowledge_base.question IS 'Вопрос (только для type=faq)';
COMMENT ON COLUMN unified_knowledge_base.answer IS 'Ответ (только для type=faq)';
COMMENT ON COLUMN unified_knowledge_base.keywords IS 'Ключевые слова для быстрого поиска (только для type=faq)';
COMMENT ON COLUMN unified_knowledge_base.category IS 'Категория FAQ (только для type=faq)';
COMMENT ON COLUMN unified_knowledge_base.tag IS 'Тег для классификации (только для type=faq)';
COMMENT ON COLUMN unified_knowledge_base.source IS 'Источник chunk (только для type=chunk, например: Data.pdf)';
COMMENT ON COLUMN unified_knowledge_base.chunk_index IS 'Порядковый номер chunk в источнике (только для type=chunk)';
COMMENT ON COLUMN unified_knowledge_base.content IS 'Содержимое chunk (только для type=chunk)';
COMMENT ON COLUMN unified_knowledge_base.search_vector IS 'Вектор для полнотекстового поиска PostgreSQL';
