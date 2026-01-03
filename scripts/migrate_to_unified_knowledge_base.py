#!/usr/bin/env python3
"""
Скрипт для миграции данных в единую таблицу unified_knowledge_base.

Переносит данные из:
- faq_ai → unified_knowledge_base (type='faq')
- knowledge_base → unified_knowledge_base (type='chunk')

Использование:
    python scripts/migrate_to_unified_knowledge_base.py
"""
import asyncio
import sys
import os
from pathlib import Path

try:
    import asyncpg
except ImportError:
    print("❌ Ошибка: библиотека asyncpg не установлена")
    print("\nУстановите её командой:")
    print("    pip install asyncpg")
    sys.exit(1)

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

# Пытаемся получить DATABASE_URL
from dotenv import load_dotenv
load_dotenv()

database_url = os.getenv('DATABASE_URL')

# Если не найден, пробуем импортировать из settings
if not database_url:
    try:
        from config.settings import settings
        database_url = getattr(settings, 'DATABASE_URL', None)
    except ImportError:
        pass


async def migrate_data() -> None:
    """
    Мигрировать данные в unified_knowledge_base.
    
    Raises:
        SystemExit: При ошибках подключения или выполнения миграции
    """
    if not database_url:
        print("❌ DATABASE_URL не найден")
        print("\nУстановите DATABASE_URL одним из способов:")
        print("1. В файле .env: DATABASE_URL=postgresql://user:pass@host:5432/dbname")
        print("2. В переменных окружения: export DATABASE_URL=...")
        sys.exit(1)
    
    try:
        # Исправляем DATABASE_URL для локального подключения (если используется Docker)
        db_url = database_url
        if db_url and "postgresql://" in db_url:
            if "@postgres:" in db_url or "://postgres:" in db_url:
                db_url = db_url.replace("@postgres:", "@localhost:").replace("://postgres:", "://localhost:")
        
        # Подключаемся к БД
        conn = await asyncpg.connect(db_url)
        print("✅ Подключение к PostgreSQL установлено")
        
        print("\n" + "=" * 70)
        print("📚 МИГРАЦИЯ ДАННЫХ В ЕДИНУЮ БАЗУ ЗНАНИЙ")
        print("=" * 70)
        
        # Проверяем, существует ли таблица unified_knowledge_base
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'unified_knowledge_base'
            )
        """)
        
        if not table_exists:
            print("❌ Таблица unified_knowledge_base не существует!")
            print("   Сначала выполните миграцию: migrations/009_create_unified_knowledge_base.sql")
            await conn.close()
            sys.exit(1)
        
        # Проверяем, есть ли уже данные
        existing_count = await conn.fetchval("SELECT COUNT(*) FROM unified_knowledge_base")
        if existing_count > 0:
            print(f"⚠️  В таблице unified_knowledge_base уже есть {existing_count} записей")
            response = input("Продолжить миграцию? (y/n): ")
            if response.lower() != 'y':
                print("❌ Миграция отменена")
                await conn.close()
                sys.exit(0)
        
        # Мигрируем FAQ из faq_ai
        print("\n📝 Миграция FAQ из faq_ai...")
        faq_count = await conn.fetchval("SELECT COUNT(*) FROM faq_ai")
        print(f"   Найдено {faq_count} FAQ для миграции")
        
        if faq_count > 0:
            # Проверяем, сколько FAQ уже есть в unified_knowledge_base
            existing_faq = await conn.fetchval("SELECT COUNT(*) FROM unified_knowledge_base WHERE type = 'faq'")
            
            if existing_faq == 0:
                migrated_faq = await conn.execute("""
                    INSERT INTO unified_knowledge_base (
                        type, question, answer, keywords, category, tag, search_vector, created_at, updated_at
                    )
                    SELECT 
                        'faq' as type,
                        question,
                        answer,
                        keywords,
                        category,
                        tag,
                        search_vector,
                        created_at,
                        updated_at
                    FROM faq_ai
                """)
                print(f"   ✅ Мигрировано FAQ: {migrated_faq.split()[-1] if migrated_faq else '0'}")
            else:
                print(f"   ⚠️  FAQ уже мигрированы ({existing_faq} записей), пропускаем")
        
        # Мигрируем chunks из knowledge_base
        print("\n📄 Миграция chunks из knowledge_base...")
        chunk_count = await conn.fetchval("SELECT COUNT(*) FROM knowledge_base")
        print(f"   Найдено {chunk_count} chunks для миграции")
        
        if chunk_count > 0:
            # Проверяем, сколько chunks уже есть в unified_knowledge_base
            existing_chunks = await conn.fetchval("SELECT COUNT(*) FROM unified_knowledge_base WHERE type = 'chunk'")
            
            if existing_chunks == 0:
                migrated_chunks = await conn.execute("""
                    INSERT INTO unified_knowledge_base (
                        type, source, chunk_index, content, search_vector, created_at, updated_at
                    )
                    SELECT 
                        'chunk' as type,
                        source,
                        chunk_index,
                        content,
                        to_tsvector('russian', content) as search_vector,
                        created_at,
                        updated_at
                    FROM knowledge_base
                """)
                print(f"   ✅ Мигрировано chunks: {migrated_chunks.split()[-1] if migrated_chunks else '0'}")
            else:
                print(f"   ⚠️  Chunks уже мигрированы ({existing_chunks} записей), пропускаем")
        
        # Статистика
        total_count = await conn.fetchval("SELECT COUNT(*) FROM unified_knowledge_base")
        faq_count_new = await conn.fetchval("SELECT COUNT(*) FROM unified_knowledge_base WHERE type = 'faq'")
        chunk_count_new = await conn.fetchval("SELECT COUNT(*) FROM unified_knowledge_base WHERE type = 'chunk'")
        
        print("\n" + "=" * 70)
        print("✅ МИГРАЦИЯ ЗАВЕРШЕНА")
        print("=" * 70)
        print(f"  📊 Всего записей в unified_knowledge_base: {total_count}")
        print(f"  📝 FAQ: {faq_count_new}")
        print(f"  📄 Chunks: {chunk_count_new}")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка при миграции: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(migrate_data())
