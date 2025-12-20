"""
Скрипт для сравнения списка сотрудников с пользователями в базе данных бота.
Поддерживает XML файлы и текстовые списки.
"""
import asyncio
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Set

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import AsyncSessionLocal
from sqlalchemy import text


async def get_db_users() -> Dict[int, Dict]:
    """Получить всех пользователей из базы данных."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT id, first_name, last_name, username, is_verified
                FROM users
            """)
        )
        users = result.fetchall()
        
        db_users = {}
        for user_id, first_name, last_name, username, is_verified in users:
            db_users[user_id] = {
                'first_name': first_name,
                'last_name': last_name,
                'username': username,
                'is_verified': is_verified,
                'full_name': f"{first_name or ''} {last_name or ''}".strip() or username or f"User {user_id}"
            }
        return db_users


def parse_xml_file(file_path: str) -> List[Dict]:
    """Парсить XML файл со списком сотрудников."""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        employees = []
        # Пробуем разные структуры XML
        for employee in root.findall('.//employee') or root.findall('.//user') or root.findall('.//courier'):
            emp_data = {}
            emp_data['name'] = employee.findtext('name', '') or employee.findtext('full_name', '')
            emp_data['username'] = employee.findtext('username', '') or employee.get('username', '')
            emp_data['telegram_id'] = employee.findtext('telegram_id', '') or employee.get('telegram_id', '')
            if emp_data['name'] or emp_data['username']:
                employees.append(emp_data)
        
        # Если структура другая, пробуем найти все текстовые элементы
        if not employees:
            for elem in root.iter():
                if elem.text and elem.text.strip():
                    employees.append({'name': elem.text.strip()})
        
        return employees
    except Exception as e:
        print(f"⚠️  Ошибка при парсинге XML: {e}")
        return []


def parse_text_file(file_path: str) -> List[Dict]:
    """Парсить текстовый файл со списком сотрудников."""
    employees = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Пробуем разные форматы
                    parts = line.split('\t') or line.split(',') or [line]
                    emp_data = {'name': parts[0].strip()}
                    if len(parts) > 1:
                        emp_data['username'] = parts[1].strip()
                    if len(parts) > 2:
                        emp_data['telegram_id'] = parts[2].strip()
                    employees.append(emp_data)
    except Exception as e:
        print(f"⚠️  Ошибка при чтении файла: {e}")
    return employees


async def compare_employees_with_db(file_path: str = None):
    """Сравнить список сотрудников с пользователями в БД."""
    db_users = await get_db_users()
    
    print(f"📋 Пользователей в базе данных: {len(db_users)}\n")
    
    # Если файл не указан, просто показываем пользователей из БД
    if not file_path:
        print("💡 Для сравнения укажите путь к файлу со списком сотрудников:")
        print("   python scripts/compare_employees_with_db.py path/to/List.MXL")
        print("\n📊 Пользователи в базе данных:")
        print("=" * 80)
        for user_id, user_data in sorted(db_users.items()):
            status = "✅" if user_data['is_verified'] else "❌"
            print(f"{status} {user_data['full_name']} (@{user_data['username'] or 'нет username'}) - ID: {user_id}")
        return
    
    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        print(f"❌ Файл не найден: {file_path}")
        return
    
    # Парсим файл
    if file_path_obj.suffix.lower() == '.xml' or file_path_obj.suffix.lower() == '.mxl':
        employees = parse_xml_file(str(file_path_obj))
    else:
        employees = parse_text_file(str(file_path_obj))
    
    if not employees:
        print(f"❌ Не удалось извлечь данные из файла: {file_path}")
        return
    
    print(f"📋 Сотрудников в файле: {len(employees)}\n")
    
    # Сравниваем по именам и username
    db_names = {user['full_name'].lower(): user_id for user_id, user in db_users.items()}
    db_usernames = {user['username'].lower(): user_id for user_id, user in db_users.items() if user['username']}
    
    found_in_db = []
    not_found_in_db = []
    
    for emp in employees:
        emp_name = emp.get('name', '').lower().strip()
        emp_username = emp.get('username', '').lower().strip().lstrip('@')
        
        found = False
        matched_user_id = None
        
        # Ищем по имени
        if emp_name and emp_name in db_names:
            matched_user_id = db_names[emp_name]
            found = True
        
        # Ищем по username
        if not found and emp_username and emp_username in db_usernames:
            matched_user_id = db_usernames[emp_username]
            found = True
        
        if found:
            found_in_db.append({
                'employee': emp,
                'db_user': db_users[matched_user_id],
                'user_id': matched_user_id
            })
        else:
            not_found_in_db.append(emp)
    
    # Выводим результаты
    print("=" * 80)
    print("✅ НАЙДЕНЫ В БАЗЕ ДАННЫХ:")
    print("=" * 80)
    for item in found_in_db:
        emp = item['employee']
        db_user = item['db_user']
        print(f"\n📌 {emp.get('name', 'Не указано')}")
        print(f"   В БД: {db_user['full_name']} (@{db_user['username'] or 'нет'})")
        print(f"   ID: {item['user_id']}")
        print(f"   Статус: {'✅ Верифицирован' if db_user['is_verified'] else '❌ Не верифицирован'}")
    
    print("\n" + "=" * 80)
    print("❌ НЕ НАЙДЕНЫ В БАЗЕ ДАННЫХ:")
    print("=" * 80)
    for emp in not_found_in_db:
        print(f"   • {emp.get('name', 'Не указано')} (@{emp.get('username', 'нет')})")
    
    print("\n" + "=" * 80)
    print("📊 СТАТИСТИКА:")
    print(f"   Всего в файле: {len(employees)}")
    print(f"   Найдено в БД: {len(found_in_db)}")
    print(f"   Не найдено в БД: {len(not_found_in_db)}")
    print(f"   Покрытие: {len(found_in_db) / len(employees) * 100:.1f}%")


if __name__ == "__main__":
    file_path = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(compare_employees_with_db(file_path))


