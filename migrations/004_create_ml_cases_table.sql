-- Миграция: создание таблицы для ML-кейсов (обучение и explainability)
-- Используется для классификации и объяснения решений AI-куратора

CREATE TABLE IF NOT EXISTS ml_cases (
    id SERIAL PRIMARY KEY,
    input TEXT NOT NULL,
    label VARCHAR(100) NOT NULL,
    decision VARCHAR(200),
    explanation TEXT NOT NULL,
    input_vector tsvector,
    explanation_vector tsvector,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_ml_cases_label ON ml_cases (label);
CREATE INDEX IF NOT EXISTS idx_ml_cases_input_vector ON ml_cases USING GIN (input_vector);
CREATE INDEX IF NOT EXISTS idx_ml_cases_explanation_vector ON ml_cases USING GIN (explanation_vector);

-- Триггер для автоматического обновления векторов
CREATE OR REPLACE FUNCTION update_ml_cases_vectors()
RETURNS TRIGGER AS $$
BEGIN
    NEW.input_vector := to_tsvector('russian', COALESCE(NEW.input, ''));
    NEW.explanation_vector := to_tsvector('russian', COALESCE(NEW.explanation, ''));
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Удаляем триггер, если он уже существует (для идемпотентности)
DROP TRIGGER IF EXISTS trigger_update_ml_cases_vectors ON ml_cases;

CREATE TRIGGER trigger_update_ml_cases_vectors
    BEFORE INSERT OR UPDATE OF input, explanation ON ml_cases
    FOR EACH ROW
    EXECUTE FUNCTION update_ml_cases_vectors();

-- Комментарии
COMMENT ON TABLE ml_cases IS 'ML-кейсы для обучения и explainability AI-куратора';
COMMENT ON COLUMN ml_cases.input IS 'Входной текст (ситуация от курьера/покупателя)';
COMMENT ON COLUMN ml_cases.label IS 'Целевая переменная (тег/категория)';
COMMENT ON COLUMN ml_cases.decision IS 'Решение (ответственность)';
COMMENT ON COLUMN ml_cases.explanation IS 'Объяснение решения (explainability)';
COMMENT ON COLUMN ml_cases.input_vector IS 'Вектор для полнотекстового поиска по input';
COMMENT ON COLUMN ml_cases.explanation_vector IS 'Вектор для полнотекстового поиска по explanation';
