#!/usr/bin/env python3
"""
Скрипт для создания единой таблицы unified_knowledge_base.

Использование:
    python scripts/create_unified_knowledge_base.py

Таблица объединяет FAQ и chunks из PDF в одну базу знаний.
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

try:
    from config.settings import settings
except ImportError:
    print("❌ Ошибка: не удалось импортировать settings")
    print("Убедитесь, что файл config/settings.py существует")
    sys.exit(1)


def get_migration_sql() -> str:
    """
    Получить SQL для создания таблицы unified_knowledge_base.
    
    Returns:
        SQL строка для создания таблицы и связанных объектов
    """
    migration_file = Path(__file__).parent.parent / "migrations" / "009_create_unified_knowledge_base.sql"
    
    if not migration_file.exists():
        raise FileNotFoundError(f"Файл миграции не найден: {migration_file}")
    
    with open(migration_file, 'r', encoding='utf-8') as f:
        return f.read()


async def run_migration() -> None:
    """Выполнить миграцию для создания таблицы unified_knowledge_base."""
    try:
        if not hasattr(settings, 'DATABASE_URL') or not settings.DATABASE_URL:
            print("❌ DATABASE_URL не найден в settings")
            print("\nУстановите DATABASE_URL в файле .env или config/settings.py")
            sys.exit(1)
        
        print("=" * 70)
        print("📚 СОЗДАНИЕ ЕДИНОЙ БАЗЫ ЗНАНИЙ")
        print("=" * 70)
        
        # Исправляем DATABASE_URL для локального подключения
        db_url = settings.DATABASE_URL
        if db_url and "postgresql://" in db_url:
            if "@postgres:" in db_url or "://postgres:" in db_url:
                db_url = db_url.replace("@postgres:", "@localhost:").replace("://postgres:", "://localhost:")
        
        print(f"Подключение к БД: {db_url.split('@')[-1] if '@' in db_url else '***'}")
        
        # Подключаемся к БД
        conn = await asyncpg.connect(db_url)
        print("✅ Подключение к PostgreSQL установлено")
        
        # Получаем SQL миграции
        sql = get_migration_sql()
        
        # Выполняем миграцию
        print("\n📝 Выполнение миграции...")
        await conn.execute(sql)
        await conn.close()
        
        print("✅ Миграция выполнена успешно")
        print("✅ Таблица unified_knowledge_base создана")
        print("✅ Индексы созданы")
        print("✅ Триггеры созданы")
        print("✅ Комментарии добавлены")
        
        print("\n" + "=" * 70)
        print("✅ ГОТОВО")
        print("=" * 70)
        print("\n💡 Таблица unified_knowledge_base готова к использованию.")
        print("   Для миграции данных выполните:")
        print("   python scripts/migrate_to_unified_knowledge_base.py")
        
    except asyncpg.exceptions.DuplicateTableError:
        print("ℹ️  Таблица unified_knowledge_base уже существует")
        print("✅ Миграция идемпотентна - можно запускать повторно")
    except asyncpg.exceptions.DuplicateObjectError as e:
        if "already exists" in str(e) or "уже существует" in str(e):
            print(f"ℹ️  Объект уже существует: {e}")
            print("✅ Миграция идемпотентна - можно запускать повторно")
        else:
            raise
    except Exception as e:
        print(f"❌ Ошибка при выполнении миграции: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_migration())
