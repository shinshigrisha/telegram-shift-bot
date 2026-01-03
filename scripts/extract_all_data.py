#!/usr/bin/env python3
"""
Скрипт для извлечения всех данных из текущих источников (ЭТАП 2 - ИЗВЛЕЧЕНИЕ).

Извлекает:
1. FAQ из faq_ai и unified_knowledge_base
2. Кейсы из ml_cases и ml_cases.jsonl
3. Правила из delivery_curator_config.json

Нормализует структуру и сохраняет в JSON для миграции.
"""
import asyncio
import sys
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Set
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


async def extract_faq_from_table(conn: asyncpg.Connection, table_name: str) -> List[Dict[str, Any]]:
    """
    Извлечь FAQ из таблицы.
    
    Args:
        conn: Соединение с БД
        table_name: Имя таблицы ('faq_ai' или 'unified_knowledge_base')
    
    Returns:
        Список FAQ записей
    """
    faqs = []
    
    try:
        if table_name == 'faq_ai':
            query = """
                SELECT 
                    id,
                    question,
                    answer,
                    keywords,
                    category,
                    tag,
                    created_at,
                    updated_at
                FROM faq_ai
                ORDER BY id
            """
            rows = await conn.fetch(query)
            
            for row in rows:
                faqs.append({
                    'id': row['id'],
                    'question': row['question'],
                    'answer': row['answer'],
                    'keywords': row['keywords'] or [],
                    'category': row['category'],
                    'tag': row['tag'],
                    'source_table': 'faq_ai',
                    'created_at': str(row['created_at']) if row['created_at'] else None,
                    'updated_at': str(row['updated_at']) if row['updated_at'] else None,
                })
        
        elif table_name == 'unified_knowledge_base':
            query = """
                SELECT 
                    id,
                    type,
                    question,
                    answer,
                    keywords,
                    category,
                    tag,
                    source,
                    chunk_index,
                    content,
                    created_at,
                    updated_at
                FROM unified_knowledge_base
                WHERE type = 'faq'
                ORDER BY id
            """
            rows = await conn.fetch(query)
            
            for row in rows:
                faqs.append({
                    'id': row['id'],
                    'question': row['question'],
                    'answer': row['answer'],
                    'keywords': row['keywords'] or [],
                    'category': row['category'],
                    'tag': row['tag'],
                    'source_table': 'unified_knowledge_base',
                    'created_at': str(row['created_at']) if row['created_at'] else None,
                    'updated_at': str(row['updated_at']) if row['updated_at'] else None,
                })
    
    except Exception as e:
        print(f"⚠️  Ошибка при извлечении из {table_name}: {e}")
    
    return faqs


async def extract_ml_cases(conn: asyncpg.Connection) -> List[Dict[str, Any]]:
    """
    Извлечь ML-кейсы из таблицы ml_cases.
    
    Args:
        conn: Соединение с БД
    
    Returns:
        Список ML-кейсов
    """
    cases = []
    
    try:
        query = """
            SELECT 
                id,
                input,
                label,
                decision,
                explanation,
                created_at,
                updated_at
            FROM ml_cases
            ORDER BY id
        """
        rows = await conn.fetch(query)
        
        for row in rows:
            cases.append({
                'id': row['id'],
                'input': row['input'],
                'label': row['label'],
                'decision': row['decision'],
                'explanation': row['explanation'],
                'created_at': str(row['created_at']) if row['created_at'] else None,
                'updated_at': str(row['updated_at']) if row['updated_at'] else None,
            })
    
    except Exception as e:
        print(f"⚠️  Ошибка при извлечении ML-кейсов: {e}")
    
    return cases


def extract_ml_cases_from_jsonl(jsonl_path: Path) -> List[Dict[str, Any]]:
    """
    Извлечь ML-кейсы из JSONL файла.
    
    Args:
        jsonl_path: Путь к JSONL файлу
    
    Returns:
        Список ML-кейсов
    """
    cases = []
    
    if not jsonl_path.exists():
        print(f"⚠️  Файл не найден: {jsonl_path}")
        return cases
    
    try:
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    case = json.loads(line)
                    case['source_file'] = str(jsonl_path)
                    case['line_number'] = line_num
                    cases.append(case)
                except json.JSONDecodeError as e:
                    print(f"⚠️  Ошибка парсинга JSON в строке {line_num}: {e}")
    
    except Exception as e:
        print(f"⚠️  Ошибка при чтении {jsonl_path}: {e}")
    
    return cases


def extract_config_data() -> Dict[str, Any]:
    """
    Извлечь данные из delivery_curator_config.json.
    
    Returns:
        Словарь с данными из конфига
    """
    config_path = Path(__file__).parent.parent / "src" / "ai" / "delivery_curator_config.json"
    
    if not config_path.exists():
        print(f"⚠️  Файл конфигурации не найден: {config_path}")
        return {}
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Извлекаем только нужные секции
        extracted = {
            'knowledge_base': {
                'rules': config.get('knowledge_base', {}).get('rules', []),
                'tags': config.get('knowledge_base', {}).get('tags', []),
            },
            'must_match_cases': config.get('must_match_cases', {}).get('cases', []),
            'golden_set': config.get('golden_set', []),
            'training_cases': config.get('training_cases', []),
            'courier_rules': config.get('courier_rules', []),
            'no_contact_and_return_policy': config.get('no_contact_and_return_policy', []),
            'payment_policy': config.get('payment_policy', {}),
            'returns_policy_v1_1': config.get('returns_policy_v1_1', {}),
            'response_structure': config.get('response_structure', {}),
            'response_validator': config.get('response_validator', {}),
            'confidence_routing': config.get('confidence_routing', {}),
        }
        
        return extracted
    
    except Exception as e:
        print(f"⚠️  Ошибка при чтении конфигурации: {e}")
        return {}


def normalize_faqs(faqs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Нормализовать FAQ записи (убрать дубликаты).
    
    Args:
        faqs: Список FAQ записей
    
    Returns:
        Нормализованный список (без дубликатов)
    """
    # Используем (question, answer) как ключ для дедупликации
    seen: Set[tuple] = set()
    normalized = []
    
    for faq in faqs:
        key = (faq.get('question', '').strip().lower(), faq.get('answer', '').strip().lower())
        
        if key not in seen and key[0] and key[1]:  # Пропускаем пустые
            seen.add(key)
            normalized.append(faq)
        else:
            print(f"  ⚠️  Дубликат FAQ: {faq.get('question', '')[:50]}...")
    
    return normalized


def normalize_ml_cases(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Нормализовать ML-кейсы (убрать дубликаты).
    
    Args:
        cases: Список ML-кейсов
    
    Returns:
        Нормализованный список (без дубликатов)
    """
    # Используем input как ключ для дедупликации
    seen: Set[str] = set()
    normalized = []
    
    for case in cases:
        key = case.get('input', '').strip().lower()
        
        if key not in seen and key:
            seen.add(key)
            normalized.append(case)
        else:
            print(f"  ⚠️  Дубликат кейса: {case.get('input', '')[:50]}...")
    
    return normalized


async def extract_all_data():
    """Извлечь все данные из текущих источников."""
    if not database_url:
        print("❌ DATABASE_URL не найден")
        sys.exit(1)
    
    output_dir = Path(__file__).parent.parent / "data" / "extracted"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print("📊 ИЗВЛЕЧЕНИЕ ДАННЫХ (ЭТАП 2)")
    print("=" * 70)
    
    try:
        # Подключаемся к БД
        conn = await asyncpg.connect(database_url)
        print("✅ Подключение к PostgreSQL установлено\n")
        
        # 1. Извлекаем FAQ
        print("📄 Извлечение FAQ...")
        faq_ai_faqs = await extract_faq_from_table(conn, 'faq_ai')
        print(f"  ✅ Из faq_ai: {len(faq_ai_faqs)} записей")
        
        unified_faqs = await extract_faq_from_table(conn, 'unified_knowledge_base')
        print(f"  ✅ Из unified_knowledge_base: {len(unified_faqs)} записей")
        
        all_faqs = faq_ai_faqs + unified_faqs
        print(f"  📊 Всего FAQ: {len(all_faqs)} записей")
        
        # Нормализуем FAQ
        normalized_faqs = normalize_faqs(all_faqs)
        print(f"  ✅ После нормализации: {len(normalized_faqs)} уникальных записей\n")
        
        # 2. Извлекаем ML-кейсы
        print("📄 Извлечение ML-кейсов...")
        ml_cases_db = await extract_ml_cases(conn)
        print(f"  ✅ Из ml_cases (БД): {len(ml_cases_db)} записей")
        
        jsonl_path = Path(__file__).parent.parent / "ml_cases.jsonl"
        ml_cases_jsonl = extract_ml_cases_from_jsonl(jsonl_path)
        print(f"  ✅ Из ml_cases.jsonl: {len(ml_cases_jsonl)} записей")
        
        all_ml_cases = ml_cases_db + ml_cases_jsonl
        print(f"  📊 Всего ML-кейсов: {len(all_ml_cases)} записей")
        
        # Нормализуем ML-кейсы
        normalized_ml_cases = normalize_ml_cases(all_ml_cases)
        print(f"  ✅ После нормализации: {len(normalized_ml_cases)} уникальных записей\n")
        
        # 3. Извлекаем данные из конфига
        print("📄 Извлечение данных из конфигурации...")
        config_data = extract_config_data()
        print(f"  ✅ Извлечено {len(config_data)} секций\n")
        
        await conn.close()
        
        # 4. Сохраняем результаты
        print("💾 Сохранение результатов...")
        
        # FAQ
        faq_output = output_dir / "faqs_normalized.json"
        with open(faq_output, 'w', encoding='utf-8') as f:
            json.dump(normalized_faqs, f, ensure_ascii=False, indent=2)
        print(f"  ✅ FAQ сохранены: {faq_output}")
        
        # ML-кейсы
        ml_cases_output = output_dir / "ml_cases_normalized.json"
        with open(ml_cases_output, 'w', encoding='utf-8') as f:
            json.dump(normalized_ml_cases, f, ensure_ascii=False, indent=2)
        print(f"  ✅ ML-кейсы сохранены: {ml_cases_output}")
        
        # Конфиг данные
        config_output = output_dir / "config_extracted.json"
        with open(config_output, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        print(f"  ✅ Данные конфига сохранены: {config_output}")
        
        # Сводный отчет
        summary = {
            'extraction_date': str(asyncio.get_event_loop().time()),
            'faqs': {
                'total_before_normalization': len(all_faqs),
                'total_after_normalization': len(normalized_faqs),
                'duplicates_removed': len(all_faqs) - len(normalized_faqs),
                'from_faq_ai': len(faq_ai_faqs),
                'from_unified_knowledge_base': len(unified_faqs),
            },
            'ml_cases': {
                'total_before_normalization': len(all_ml_cases),
                'total_after_normalization': len(normalized_ml_cases),
                'duplicates_removed': len(all_ml_cases) - len(normalized_ml_cases),
                'from_database': len(ml_cases_db),
                'from_jsonl': len(ml_cases_jsonl),
            },
            'config_sections': list(config_data.keys()),
        }
        
        summary_output = output_dir / "extraction_summary.json"
        with open(summary_output, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"  ✅ Сводка сохранена: {summary_output}\n")
        
        # Выводим статистику
        print("=" * 70)
        print("✅ ИЗВЛЕЧЕНИЕ ЗАВЕРШЕНО")
        print("=" * 70)
        print(f"  📊 FAQ: {len(normalized_faqs)} уникальных записей")
        print(f"  📊 ML-кейсы: {len(normalized_ml_cases)} уникальных записей")
        print(f"  📊 Секций конфига: {len(config_data)}")
        print(f"\n  💾 Результаты сохранены в: {output_dir}")
        
    except Exception as e:
        print(f"❌ Ошибка при извлечении данных: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(extract_all_data())
