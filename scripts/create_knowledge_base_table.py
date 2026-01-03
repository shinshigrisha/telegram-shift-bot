#!/usr/bin/env python3
"""
Скрипт для создания таблицы knowledge_base для хранения chunks из PDF.

Использование:
    python scripts/create_knowledge_base_table.py

Таблица используется ТОЛЬКО для AI-куратора (RAG - Retrieval-Augmented Generation).
Хранит разбитый на chunks контент из PDF файлов для базы знаний.

Таблица безопасна для добавления в существующую БД:
- Использует IF NOT EXISTS (идемпотентность)
- Не имеет внешних ключей на другие таблицы
- Не изменяет существующие таблицы
- Изолирована от остальной схемы БД
"""
import asyncio
import sys
from pathlib import Path

try:
    import asyncpg
except ImportError:
    print("❌ Ошибка: библиотека asyncpg не установлена")
    print("\nУстановите её командой:")
    print("    pip install asyncpg")
    sys.exit(1)

# Добавляем корневую директорию проекта в путь для импорта settings
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from config.settings import settings
except ImportError:
    print("❌ Ошибка: не удалось импортировать settings")
    print("Убедитесь, что файл config/settings.py существует")
    sys.exit(1)


def get_migration_sql() -> str:
    """
    Получить SQL для создания таблицы knowledge_base.
    
    SQL вынесен в отдельную функцию для удобства и читаемости.
    Таблица содержит:
    - id (SERIAL PRIMARY KEY)
    - source (TEXT) - источник chunk (например: Data.pdf)
    - chunk_index (INTEGER) - порядковый номер chunk
    - content (TEXT) - содержимое chunk
    - created_at, updated_at (TIMESTAMP) - временные метки
    
    Returns:
        SQL строка для создания таблицы и связанных объектов
    """
    return """
-- Миграция: создание таблицы knowledge_base для хранения chunks из PDF
-- Используется ТОЛЬКО для AI-куратора (RAG - Retrieval-Augmented Generation)
-- Хранит разбитый на chunks контент из PDF файлов для базы знаний

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
"""


async def run_migration() -> None:
    """
    Выполнить миграцию для создания таблицы knowledge_base.
    
    Raises:
        SystemExit: При ошибках подключения или выполнения миграции
    """
    try:
        # Проверяем наличие DATABASE_URL
        if not hasattr(settings, 'DATABASE_URL') or not settings.DATABASE_URL:
            print("❌ DATABASE_URL не найден в settings")
            print("\nУстановите DATABASE_URL в файле .env или config/settings.py")
            sys.exit(1)
        
        print("=" * 70)
        print("📚 СОЗДАНИЕ ТАБЛИЦЫ KNOWLEDGE_BASE")
        print("=" * 70)
        print(f"Подключение к БД: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else '***'}")
        
        # Подключаемся к БД
        conn = await asyncpg.connect(settings.DATABASE_URL)
        print("✅ Подключение к PostgreSQL установлено")
        
        # Получаем SQL миграции
        sql = get_migration_sql()
        
        # Выполняем миграцию
        print("\n📝 Выполнение миграции...")
        await conn.execute(sql)
        await conn.close()
        
        print("✅ Миграция выполнена успешно")
        print("✅ Таблица knowledge_base создана")
        print("✅ Индексы созданы")
        print("✅ Триггеры созданы")
        print("✅ Комментарии добавлены")
        
        print("\n" + "=" * 70)
        print("✅ ГОТОВО")
        print("=" * 70)
        print("\n💡 Таблица knowledge_base готова к использованию.")
        print("   Теперь можно импортировать chunks из PDF используя:")
        print("   python scripts/pdf_to_chunks.py")
        
    except asyncpg.exceptions.DuplicateTableError:
        print("ℹ️  Таблица knowledge_base уже существует")
        print("✅ Миграция идемпотентна - можно запускать повторно")
    except asyncpg.exceptions.DuplicateObjectError as e:
        if "already exists" in str(e) or "уже существует" in str(e):
            print(f"ℹ️  Объект уже существует: {e}")
            print("✅ Миграция идемпотентна - можно запускать повторно")
        else:
            raise
    except asyncpg.exceptions.PostgresError as e:
        print(f"❌ Ошибка PostgreSQL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка при выполнении миграции: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_migration())
