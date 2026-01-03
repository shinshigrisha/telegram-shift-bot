-- Миграция: создание таблицы faq_ai для RAG (Retrieval-Augmented Generation)
-- Используется для хранения базы знаний AI-куратора

CREATE TABLE IF NOT EXISTS faq_ai (
    id SERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    keywords TEXT[] DEFAULT '{}',
    category VARCHAR(100),
    tag VARCHAR(100),
    search_vector tsvector,
    qa_hash VARCHAR(32),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Индекс для быстрого поиска по ключевым словам (GIN индекс для массивов)
CREATE INDEX IF NOT EXISTS idx_faq_ai_keywords ON faq_ai USING GIN (keywords);

-- Индекс для полнотекстового поиска (GIN индекс для tsvector)
CREATE INDEX IF NOT EXISTS idx_faq_ai_search_vector ON faq_ai USING GIN (search_vector);

-- Индекс для поиска по категории и тегу
CREATE INDEX IF NOT EXISTS idx_faq_ai_category ON faq_ai (category);
CREATE INDEX IF NOT EXISTS idx_faq_ai_tag ON faq_ai (tag);

-- Добавляем колонку qa_hash для существующих таблиц (если её нет)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'faq_ai' AND column_name = 'qa_hash'
    ) THEN
        ALTER TABLE faq_ai ADD COLUMN qa_hash VARCHAR(32);
        -- Заполняем qa_hash для существующих записей
        UPDATE faq_ai SET qa_hash = md5(question || answer) WHERE qa_hash IS NULL;
    END IF;
END $$;

-- Обновляем qa_hash для существующих записей (если колонка уже была, но не заполнена)
UPDATE faq_ai SET qa_hash = md5(question || answer) WHERE qa_hash IS NULL;

-- Уникальный индекс для предотвращения дублирования записей (для ON CONFLICT DO NOTHING)
CREATE UNIQUE INDEX IF NOT EXISTS idx_faq_ai_unique_qa ON faq_ai (qa_hash);

-- Триггер для автоматического обновления search_vector и qa_hash при изменении question или answer
CREATE OR REPLACE FUNCTION update_faq_ai_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector('russian', COALESCE(NEW.question, '') || ' ' || COALESCE(NEW.answer, ''));
    NEW.qa_hash := md5(NEW.question || NEW.answer);
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Удаляем триггер, если он уже существует (для идемпотентности)
DROP TRIGGER IF EXISTS trigger_update_faq_ai_search_vector ON faq_ai;

CREATE TRIGGER trigger_update_faq_ai_search_vector
    BEFORE INSERT OR UPDATE OF question, answer ON faq_ai
    FOR EACH ROW
    EXECUTE FUNCTION update_faq_ai_search_vector();

-- Триггер для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_faq_ai_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Удаляем триггер, если он уже существует (для идемпотентности)
DROP TRIGGER IF EXISTS trigger_update_faq_ai_updated_at ON faq_ai;

CREATE TRIGGER trigger_update_faq_ai_updated_at
    BEFORE UPDATE ON faq_ai
    FOR EACH ROW
    EXECUTE FUNCTION update_faq_ai_updated_at();

-- Комментарии к таблице и колонкам
COMMENT ON TABLE faq_ai IS 'База знаний для AI-куратора (RAG)';
COMMENT ON COLUMN faq_ai.question IS 'Вопрос пользователя';
COMMENT ON COLUMN faq_ai.answer IS 'Ответ на вопрос';
COMMENT ON COLUMN faq_ai.keywords IS 'Ключевые слова для быстрого поиска (массив)';
COMMENT ON COLUMN faq_ai.category IS 'Категория FAQ (например: доставка, оплата, возвраты)';
COMMENT ON COLUMN faq_ai.tag IS 'Тег для классификации (например: Неаккуратная доставка)';
COMMENT ON COLUMN faq_ai.search_vector IS 'Вектор для полнотекстового поиска PostgreSQL';
