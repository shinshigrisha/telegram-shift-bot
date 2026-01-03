#!/usr/bin/env python3
"""
Скрипт для импорта chunks из PDF в таблицу knowledge_base.

Использование:
    python scripts/import_pdf_chunks_to_db.py

PDF файл должен находиться по пути: docs/Data.pdf

Скрипт:
1. Читает PDF файл и разбивает на chunks
2. Импортирует chunks в таблицу knowledge_base
3. Использует ON CONFLICT DO NOTHING для предотвращения дубликатов
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

# Импортируем функции из pdf_to_chunks.py
try:
    from scripts.pdf_to_chunks import create_chunks_from_pdf, PDFChunk
except ImportError:
    print("❌ Ошибка: не удалось импортировать функции из pdf_to_chunks.py")
    print("Убедитесь, что файл scripts/pdf_to_chunks.py существует")
    sys.exit(1)

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


async def import_chunks_to_db(chunks: list[PDFChunk]) -> None:
    """
    Импортировать chunks в таблицу knowledge_base.
    
    Args:
        chunks: Список PDFChunk объектов для импорта
        
    Raises:
        SystemExit: При ошибках подключения или выполнения импорта
    """
    if not database_url:
        print("❌ DATABASE_URL не найден")
        print("\nУстановите DATABASE_URL одним из способов:")
        print("1. В файле .env: DATABASE_URL=postgresql://user:pass@host:5432/dbname")
        print("2. В переменных окружения: export DATABASE_URL=...")
        sys.exit(1)
    
    if not chunks:
        print("❌ Нет chunks для импорта")
        sys.exit(1)
    
    try:
        # Исправляем DATABASE_URL для локального подключения (если используется Docker)
        # Заменяем "postgres:" на "localhost:" в URL, если это необходимо
        db_url = database_url
        if db_url and "postgresql://" in db_url:
            # Если хост - "postgres" (имя Docker контейнера), заменяем на localhost
            if "@postgres:" in db_url or "://postgres:" in db_url:
                db_url = db_url.replace("@postgres:", "@localhost:").replace("://postgres:", "://localhost:")
        
        # Подключаемся к БД
        conn = await asyncpg.connect(db_url)
        print("✅ Подключение к PostgreSQL установлено")
        
        print(f"\n📥 Импорт {len(chunks)} chunks в таблицу knowledge_base...")
        
        # Получаем количество записей до импорта
        count_before = await conn.fetchval("SELECT COUNT(*) FROM knowledge_base")
        
        # Импортируем chunks
        errors = 0
        
        for chunk_num, chunk in enumerate(chunks, 1):
            try:
                # Используем ON CONFLICT DO NOTHING для предотвращения дубликатов
                await conn.execute(
                    """
                    INSERT INTO knowledge_base (source, chunk_index, content)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (source, chunk_index) DO NOTHING
                    """,
                    chunk.source,
                    chunk.chunk_index,
                    chunk.content
                )
                
                # Показываем прогресс каждые 50 chunks
                if chunk_num % 50 == 0:
                    print(f"  ✅ Обработано {chunk_num}/{len(chunks)} chunks...")
            
            except Exception as e:
                print(f"❌ Ошибка при импорте chunk #{chunk.chunk_index}: {e}")
                errors += 1
        
        # Статистика
        count_after = await conn.fetchval("SELECT COUNT(*) FROM knowledge_base")
        inserted = count_after - count_before
        skipped = len(chunks) - inserted - errors
        
        print("\n" + "=" * 70)
        print("✅ ИМПОРТ ЗАВЕРШЁН")
        print("=" * 70)
        print(f"  ✅ Успешно импортировано: {inserted} chunks")
        print(f"  ⚠️  Пропущено (дубликаты): {skipped} chunks")
        print(f"  ❌ Ошибок: {errors} chunks")
        print(f"  📊 Всего в базе: {count_after} chunks")
        
        # Статистика по источникам
        stats = await conn.fetch(
            """
            SELECT source, COUNT(*) as cnt
            FROM knowledge_base
            GROUP BY source
            ORDER BY cnt DESC
            """
        )
        
        if stats:
            print("\n📊 Статистика по источникам:")
            for row in stats:
                print(f"  • {row['source']}: {row['cnt']} chunks")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка при импорте: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


async def main() -> None:
    """Главная функция скрипта."""
    # Определяем путь к PDF
    script_dir = Path(__file__).parent.parent
    pdf_path = script_dir / "docs" / "Data.pdf"
    
    print("=" * 70)
    print("📚 ИМПОРТ CHUNKS ИЗ PDF В БАЗУ ЗНАНИЙ")
    print("=" * 70)
    print(f"PDF файл: {pdf_path}")
    
    if not pdf_path.exists():
        print(f"❌ PDF файл не найден: {pdf_path}")
        sys.exit(1)
    
    try:
        # Создаём chunks из PDF
        print("\n📄 Чтение и разбиение PDF на chunks...")
        chunks = create_chunks_from_pdf(
            pdf_path=pdf_path,
            source_name="Data.pdf",
            min_chunk_size=500,
            max_chunk_size=800,
        )
        
        print(f"✅ Создано {len(chunks)} chunks")
        
        # Импортируем в БД
        await import_chunks_to_db(chunks)
        
        print("\n" + "=" * 70)
        print("✅ ГОТОВО")
        print("=" * 70)
        print("\n💡 Chunks успешно импортированы в таблицу knowledge_base.")
        print("   Теперь их можно использовать для RAG в AI-кураторе.")
        
    except FileNotFoundError as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
