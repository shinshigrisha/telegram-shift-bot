#!/usr/bin/env python3
"""
Скрипт для выполнения миграции users таблицы.
"""
import asyncio
import sys
from pathlib import Path

import asyncpg
from config.settings import settings


async def run_migration():
    """Выполнить миграцию для таблицы users."""
    try:
        # Подключаемся к БД
        conn = await asyncpg.connect(settings.DATABASE_URL)
        
        # Читаем SQL файл миграции
        migration_file = Path(__file__).parent.parent / "migrations" / "005_create_users_table.sql"
        
        if not migration_file.exists():
            print(f"❌ Файл миграции не найден: {migration_file}")
            sys.exit(1)
        
        with open(migration_file, 'r', encoding='utf-8') as f:
            sql = f.read()
        
        # Выполняем миграцию
        await conn.execute(sql)
        await conn.close()
        
        print("✅ Миграция users выполнена успешно")
        print("✅ Таблица users создана")
        print("✅ Индексы созданы")
        print("✅ Триггеры созданы")
        
    except asyncpg.exceptions.DuplicateTableError:
        print("ℹ️ Таблица users уже существует")
    except asyncpg.exceptions.DuplicateObjectError as e:
        if "already exists" in str(e):
            print(f"ℹ️ Объект уже существует: {e}")
        else:
            raise
    except Exception as e:
        print(f"❌ Ошибка при выполнении миграции: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_migration())
