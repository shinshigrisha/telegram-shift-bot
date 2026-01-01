#!/usr/bin/env python3
"""
Скрипт для импорта ML-кейсов из JSONL файла в PostgreSQL.

Использование:
    python scripts/import_ml_cases_jsonl.py <путь_к_файлу.jsonl>
    
Или через stdin:
    cat cases.jsonl | python scripts/import_ml_cases_jsonl.py
"""
import asyncio
import sys
import os
import json
from pathlib import Path
import asyncpg
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Пытаемся получить DATABASE_URL
database_url = os.getenv('DATABASE_URL')

# Если не найден, пробуем импортировать из settings
if not database_url:
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from config.settings import settings
        database_url = getattr(settings, 'DATABASE_URL', None)
    except ImportError:
        pass


async def import_jsonl_to_db(jsonl_file_path: str = None):
    """
    Импортировать ML-кейсы из JSONL файла в PostgreSQL.
    
    Args:
        jsonl_file_path: Путь к JSONL файлу (если None, читает из stdin)
    """
    if not database_url:
        print("❌ DATABASE_URL не найден")
        print("\nУстановите DATABASE_URL одним из способов:")
        print("1. В файле .env: DATABASE_URL=postgresql://user:pass@host:5432/dbname")
        print("2. В переменных окружения: export DATABASE_URL=...")
        sys.exit(1)
    
    try:
        # Подключаемся к БД
        conn = await asyncpg.connect(database_url)
        print("✅ Подключение к PostgreSQL установлено")
        
        # Читаем JSONL
        if jsonl_file_path:
            if not Path(jsonl_file_path).exists():
                print(f"❌ Файл не найден: {jsonl_file_path}")
                sys.exit(1)
            
            with open(jsonl_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        else:
            # Читаем из stdin
            print("📥 Чтение данных из stdin...")
            lines = sys.stdin.readlines()
        
        if not lines:
            print("❌ Нет данных для импорта")
            sys.exit(1)
        
        print(f"📄 Найдено {len(lines)} строк для импорта")
        
        # Парсим и вставляем данные
        inserted = 0
        skipped = 0
        errors = 0
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                # Парсим JSON
                case = json.loads(line)
                
                # Проверяем обязательные поля
                if not all(key in case for key in ['input', 'label', 'explanation']):
                    print(f"⚠️  Строка {line_num}: отсутствуют обязательные поля, пропускаю")
                    skipped += 1
                    continue
                
                # Вставляем в БД
                await conn.execute(
                    """
                    INSERT INTO ml_cases (input, label, decision, explanation)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT DO NOTHING
                    """,
                    case['input'],
                    case['label'],
                    case.get('decision'),
                    case['explanation']
                )
                
                inserted += 1
                
                if inserted % 10 == 0:
                    print(f"  ✅ Импортировано {inserted} кейсов...")
            
            except json.JSONDecodeError as e:
                print(f"❌ Строка {line_num}: ошибка парсинга JSON: {e}")
                errors += 1
            except Exception as e:
                print(f"❌ Строка {line_num}: ошибка при вставке: {e}")
                errors += 1
        
        # Статистика
        total_count = await conn.fetchval("SELECT COUNT(*) FROM ml_cases")
        
        print("\n" + "=" * 70)
        print("✅ ИМПОРТ ЗАВЕРШЁН")
        print("=" * 70)
        print(f"  ✅ Успешно импортировано: {inserted} кейсов")
        print(f"  ⚠️  Пропущено: {skipped} кейсов")
        print(f"  ❌ Ошибок: {errors} кейсов")
        print(f"  📊 Всего в базе: {total_count} кейсов")
        
        # Статистика по меткам
        stats = await conn.fetch(
            """
            SELECT label, COUNT(*) as cnt
            FROM ml_cases
            GROUP BY label
            ORDER BY cnt DESC
            """
        )
        
        if stats:
            print("\n📊 Статистика по меткам:")
            for row in stats:
                print(f"  • {row['label']}: {row['cnt']} кейсов")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка при импорте: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    jsonl_file = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(import_jsonl_to_db(jsonl_file))
