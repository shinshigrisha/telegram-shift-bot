#!/usr/bin/env python3
"""
Скрипт для инициализации базы данных FAQ для AI-куратора.

Выполняет:
1. Создание таблицы faq_ai
2. Создание индексов
3. Вставку начальных данных

Использование:
    # В Docker-контейнере (рекомендуется):
    docker compose run --rm bot python scripts/init_faq_database.py
    
    # Или напрямую (если зависимости установлены локально):
    python scripts/init_faq_database.py
    
    # С указанием DATABASE_URL:
    DATABASE_URL=postgresql://user:pass@host:5432/dbname python scripts/init_faq_database.py
"""
import asyncio
import sys
import os
from pathlib import Path
import asyncpg
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

# Пытаемся получить DATABASE_URL из переменных окружения
database_url = os.getenv('DATABASE_URL')

# Если не найден, пробуем импортировать из settings (если доступен)
if not database_url:
    try:
        # Добавляем корневую директорию в путь
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from config.settings import settings
        database_url = getattr(settings, 'DATABASE_URL', None)
    except ImportError:
        pass

async def init_faq_database():
    """Инициализировать базу данных FAQ."""
    if not database_url:
        print("❌ DATABASE_URL не найден")
        print("\nУстановите DATABASE_URL одним из способов:")
        print("1. В файле .env: DATABASE_URL=postgresql://user:pass@host:5432/dbname")
        print("2. В переменных окружения: export DATABASE_URL=...")
        print("3. При запуске: DATABASE_URL=... python scripts/init_faq_database.py")
        sys.exit(1)
    
    try:
        # Подключаемся к БД
        conn = await asyncpg.connect(database_url)
        
        print("✅ Подключение к PostgreSQL установлено")
        
        # Читаем миграции
        migrations_dir = Path(__file__).parent.parent / "migrations"
        
        # Миграция 1: создание таблицы
        migration_1 = migrations_dir / "001_create_faq_ai_table.sql"
        if migration_1.exists():
            print(f"📄 Выполняю миграцию: {migration_1.name}")
            with open(migration_1, 'r', encoding='utf-8') as f:
                sql = f.read()
            await conn.execute(sql)
            print("✅ Таблица faq_ai и связанные объекты созданы/обновлены")
        else:
            print(f"⚠️  Файл миграции не найден: {migration_1}")
        
        # Миграция 2: начальные данные
        migration_2 = migrations_dir / "002_insert_initial_faq_data.sql"
        if migration_2.exists():
            print(f"📄 Выполняю миграцию: {migration_2.name}")
            with open(migration_2, 'r', encoding='utf-8') as f:
                sql = f.read()
            await conn.execute(sql)
            print("✅ Начальные данные вставлены")
        else:
            print(f"⚠️  Файл миграции не найден: {migration_2}")
        
        # Миграция 3: расширенный набор кейсов (50 ситуаций)
        migration_3 = migrations_dir / "003_insert_extended_cases.sql"
        if migration_3.exists():
            print(f"📄 Выполняю миграцию: {migration_3.name}")
            with open(migration_3, 'r', encoding='utf-8') as f:
                sql = f.read()
            await conn.execute(sql)
            print("✅ Расширенный набор кейсов добавлен")
        else:
            print(f"⚠️  Файл миграции не найден: {migration_3}")
        
        # Миграция 4: создание таблицы ml_cases
        migration_4 = migrations_dir / "004_create_ml_cases_table.sql"
        if migration_4.exists():
            print(f"📄 Выполняю миграцию: {migration_4.name}")
            with open(migration_4, 'r', encoding='utf-8') as f:
                sql = f.read()
            await conn.execute(sql)
            print("✅ Таблица ml_cases и связанные объекты созданы/обновлены")
        else:
            print(f"⚠️  Файл миграции не найден: {migration_4}")
        
        # Проверяем количество записей
        count = await conn.fetchval("SELECT COUNT(*) FROM faq_ai")
        print(f"✅ В базе данных {count} записей FAQ")
        
        await conn.close()
        print("\n✅ Инициализация базы данных FAQ завершена успешно")
        
    except Exception as e:
        print(f"❌ Ошибка при инициализации базы данных: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(init_faq_database())
