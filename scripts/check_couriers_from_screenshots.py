"""
Скрипт для проверки, какие курьеры из скриншотов уже внесены в базу данных.
Сравнивает список курьеров из скриншотов с пользователями в БД.
"""
import asyncio
import sys
import re
from pathlib import Path
from typing import List, Dict, Set

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import AsyncSessionLocal
from sqlalchemy import text

# Список курьеров ДС 8958 из скриншотов Telegram групп
COURIERS_DS_8958 = [
    # ЗИЗ-1
    {"name": "Шахбози Эшонхоча", "telegram_id": None, "username": None},
    {"name": "Шапатаев Алишер", "telegram_id": None, "username": None},
    {"name": "Саидов Ёкубджон", "telegram_id": None, "username": None},
    {"name": "Нурзода Бунёд", "telegram_id": None, "username": None},
    {"name": "Королев Никита", "telegram_id": None, "username": "Korolev_Nikita_20"},
    
    # ЗИЗ-2
    {"name": "Фарис", "telegram_id": None, "username": None},
    {"name": "Рузибоев Бехруз", "telegram_id": None, "username": None},
    {"name": "Сэр_Го", "telegram_id": None, "username": "Sir_Go"},
    {"name": "Мухаммаджон Амонов", "telegram_id": None, "username": None},
    {"name": "ШАРАПОВ МИРЛАНБЕК", "telegram_id": None, "username": None},
    
    # ЗИЗ-3
    {"name": "Богданов Олег", "telegram_id": None, "username": None},
    {"name": "Жээнали Уулу Жоодарбек", "telegram_id": None, "username": None},
    {"name": "Шахбозбек Абдурахманов", "telegram_id": None, "username": None},
    {"name": "Шигапов Артур", "telegram_id": None, "username": None},
    {"name": "Евгений Аксентьев", "telegram_id": None, "username": None},
    
    # ЗИЗ-4
    {"name": "Левчаев Ярослав", "telegram_id": None, "username": None},
    {"name": "Мусралиев Арстан", "telegram_id": None, "username": None},
    {"name": "Артём Альжанов", "telegram_id": None, "username": None},
    {"name": "АЗИЗОВ ЭЛЬДАР", "telegram_id": None, "username": None},
    {"name": "Раев Алексей", "telegram_id": None, "username": None},
    {"name": "Valentin VV", "telegram_id": None, "username": None, "tag": "6028"},
    {"name": "Гимбатов Марсель", "telegram_id": None, "username": None},
    {"name": "ИСАЕВ НИКИТА", "telegram_id": None, "username": None},
    
    # ЗИЗ-5
    {"name": "Азим Нуркыял", "telegram_id": None, "username": None},
    {"name": "Атамов Мирлан", "telegram_id": None, "username": None},
    {"name": "Куцар Василий", "telegram_id": None, "username": "Brillian1t88"},
    {"name": "Жуман Мухамадали", "telegram_id": None, "username": None},
    {"name": "Быков Алексей", "telegram_id": None, "username": None},
    {"name": "Асадбек Нуралиев", "telegram_id": None, "username": None},
    {"name": "Искандаров Руслан", "telegram_id": None, "username": None},
    {"name": "Ловягин Кирилл", "telegram_id": None, "username": None},
    
    # ЗИЗ-6
    {"name": "Замирбеков Далимбек", "telegram_id": None, "username": None},
    {"name": "Ардашер С", "telegram_id": None, "username": None},
    {"name": "Мукамбетов Тагай", "telegram_id": None, "username": None},
    
    # ЗИЗ-7
    {"name": "Иванов Вадим", "telegram_id": None, "username": None, "tag": "6028"},
    {"name": "Далер Боев", "telegram_id": None, "username": None},
    {"name": "Алимардоров Файзали", "telegram_id": None, "username": None},
    {"name": "Ганиев Азиз", "telegram_id": None, "username": None},
    {"name": "Раджабек Хасанов", "telegram_id": None, "username": "Rajik_007"},
    {"name": "Одинаев Фарух", "telegram_id": None, "username": None},
    {"name": "Новруз Шоев", "telegram_id": None, "username": None},
    {"name": "Абдуганиев Абдумалик", "telegram_id": None, "username": None},
    
    # ЗИЗ-8
    {"name": "Давлат Исоев", "telegram_id": None, "username": None},
    {"name": "Сатторов Рамазон", "telegram_id": None, "username": None},
    {"name": "Камалов Сергей", "telegram_id": None, "username": None},
    {"name": "Ибрагимов Санутулло", "telegram_id": None, "username": None},
    {"name": "Шуваев Кирилл", "telegram_id": None, "username": None},
    {"name": "Азизбек Мадиеров", "telegram_id": None, "username": None},
    {"name": "Фаридун Хусайнов", "telegram_id": None, "username": None, "tag": "7368"},
    
    # ЗИЗ-9
    {"name": "Мухаммад Авазов", "telegram_id": None, "username": None},
    {"name": "Мухаммадамин Кодирзода", "telegram_id": None, "username": None},
    {"name": "Иссаилтуллоджони Атахон", "telegram_id": None, "username": None},
    {"name": "Иномжон Хужамбердиев", "telegram_id": None, "username": None},
    {"name": "Озтораман Энгин", "telegram_id": None, "username": None},
    {"name": "Сафар Хасанов", "telegram_id": None, "username": None},
    {"name": "Илхомиддин Бобишоев", "telegram_id": None, "username": None},
    
    # ЗИЗ-11(12)
    {"name": "P Роман Трофимов", "telegram_id": None, "username": None},
    {"name": "П Пристов Егор", "telegram_id": None, "username": None},
    {"name": "СМ Семен Маралин", "telegram_id": None, "username": None},
    {"name": "Матираимов Манасбек", "telegram_id": None, "username": None},
    {"name": "Сафаралиев Бахлул", "telegram_id": None, "username": None},
    {"name": "Д Добрынин Николай", "telegram_id": None, "username": None},
    {"name": "Гоша Шевелев", "telegram_id": None, "username": None},
    {"name": "А Ашурбоев Хожимурот", "telegram_id": None, "username": None},
    {"name": "Евдосеев Сергей", "telegram_id": None, "username": None},
    
    # ЗИЗ-13
    {"name": "Азимов Рахматулло", "telegram_id": None, "username": None},
    {"name": "Рахимов Хайрулло", "telegram_id": None, "username": None},
    {"name": "Сомон Хусайнов", "telegram_id": None, "username": None},
    {"name": "Дмитрий Мампория", "telegram_id": None, "username": None},
    {"name": "Андрей Давидочкин", "telegram_id": None, "username": None},
    {"name": "Тошмадов Аслиддин", "telegram_id": None, "username": None},
    {"name": "Насим Косимов", "telegram_id": None, "username": None, "tag": "7368"},
    
    # ЗИЗ-14
    {"name": "Асозода Муххамаджон", "telegram_id": None, "username": None},
    {"name": "Ураков Рустам", "telegram_id": None, "username": None},
    {"name": "Фарухи Кадами", "telegram_id": None, "username": None},
    {"name": "Ахмед Асодави", "telegram_id": None, "username": None},
    {"name": "Алмардогов Искандар", "telegram_id": None, "username": None, "tag": "7368"},
    {"name": "Дарвешов Фаридун", "telegram_id": None, "username": None},
    {"name": "Махмалиев Солех", "telegram_id": None, "username": None, "tag": "7368"},
]


def normalize_name(name: str) -> str:
    """Нормализовать имя для сравнения."""
    # Убираем лишние пробелы, приводим к нижнему регистру
    name = re.sub(r'\s+', ' ', name.strip().lower())
    # Убираем префиксы типа "P ", "Д ", "А ", "СМ " и т.д.
    name = re.sub(r'^[а-яa-z]\s+', '', name)
    return name


def normalize_db_name(first_name: str, last_name: str) -> str:
    """Нормализовать имя из БД для сравнения."""
    parts = []
    if first_name:
        parts.append(first_name.strip())
    if last_name:
        parts.append(last_name.strip())
    return normalize_name(' '.join(parts)) if parts else ""


async def check_couriers_in_db():
    """Проверить, какие курьеры из скриншотов уже есть в базе данных."""
    async with AsyncSessionLocal() as session:
        # Получаем всех пользователей из БД
        users_result = await session.execute(
            text("""
                SELECT id, first_name, last_name, username, is_verified
                FROM users
                ORDER BY first_name, last_name
            """)
        )
        db_users = users_result.fetchall()
        
        # Получаем всех пользователей из опросов с тегами
        votes_result = await session.execute(
            text("""
                SELECT DISTINCT uv.user_id, uv.user_name
                FROM user_votes uv
                WHERE uv.user_name IS NOT NULL
                ORDER BY uv.user_name
            """)
        )
        votes = votes_result.fetchall()
        
        # Создаем словарь для быстрого поиска по именам
        db_by_name = {}
        db_by_username = {}
        db_by_id = {}
        
        for user_id, first_name, last_name, username, is_verified in db_users:
            db_by_id[user_id] = {
                'first_name': first_name,
                'last_name': last_name,
                'username': username,
                'is_verified': is_verified
            }
            
            normalized_name = normalize_db_name(first_name or '', last_name or '')
            if normalized_name:
                db_by_name[normalized_name] = user_id
            
            if username:
                db_by_username[username.lower()] = user_id
        
        # Создаем словарь пользователей из опросов
        votes_by_name = {}
        votes_by_id = {}
        courier_tags = ['8958', '7368', '6028']
        
        for user_id, user_name in votes:
            if not user_name:
                continue
            
            votes_by_id[user_id] = user_name
            
            # Нормализуем имя из опроса (убираем теги)
            normalized_vote_name = normalize_name(re.sub(r'\s*\d{4}\s*$', '', user_name))
            if normalized_vote_name:
                votes_by_name[normalized_vote_name] = (user_id, user_name)
        
        # Проверяем курьеров из скриншотов
        found_in_db = []
        found_in_votes = []
        not_found = []
        
        print("=" * 100)
        print("🔍 ПРОВЕРКА КУРЬЕРОВ ИЗ СКРИНШОТОВ")
        print("=" * 100)
        print(f"\n📋 Всего курьеров в списке: {len(COURIERS_DS_8958)}")
        print(f"📊 Пользователей в БД: {len(db_users)}")
        print(f"📊 Уникальных голосовавших: {len(votes)}\n")
        
        for courier in COURIERS_DS_8958:
            name = courier.get("name", "").strip()
            username = courier.get("username")
            telegram_id = courier.get("telegram_id")
            tag = courier.get("tag", "8958")
            
            if not name:
                continue
            
            # Нормализуем имя для поиска
            normalized_name = normalize_name(name)
            
            found = False
            match_type = None
            match_info = None
            
            # Проверяем по telegram_id
            if telegram_id and telegram_id in db_by_id:
                found = True
                match_type = "ID"
                match_info = db_by_id[telegram_id]
            
            # Проверяем по username
            elif username:
                username_lower = username.lower()
                if username_lower in db_by_username:
                    found = True
                    match_type = "username"
                    user_id = db_by_username[username_lower]
                    match_info = db_by_id.get(user_id, {})
            
            # Проверяем по имени в БД
            elif normalized_name in db_by_name:
                found = True
                match_type = "имя (БД)"
                user_id = db_by_name[normalized_name]
                match_info = db_by_id.get(user_id, {})
            
            # Проверяем по имени в опросах
            elif normalized_name in votes_by_name:
                found = True
                match_type = "имя (опросы)"
                user_id, vote_name = votes_by_name[normalized_name]
                match_info = {'user_id': user_id, 'vote_name': vote_name}
            
            # Проверяем частичное совпадение имени
            if not found:
                for db_normalized, db_user_id in db_by_name.items():
                    if normalized_name in db_normalized or db_normalized in normalized_name:
                        found = True
                        match_type = "частичное совпадение (БД)"
                        match_info = db_by_id.get(db_user_id, {})
                        break
            
            if found:
                if match_type in ["ID", "username", "имя (БД)"]:
                    found_in_db.append({
                        'name': name,
                        'match_type': match_type,
                        'match_info': match_info
                    })
                else:
                    found_in_votes.append({
                        'name': name,
                        'match_type': match_type,
                        'match_info': match_info
                    })
            else:
                not_found.append({
                    'name': name,
                    'username': username,
                    'tag': tag
                })
        
        # Выводим результаты
        print("\n" + "=" * 100)
        print("✅ НАЙДЕНО В БАЗЕ ДАННЫХ")
        print("=" * 100)
        if found_in_db:
            for item in found_in_db:
                info = item['match_info']
                db_name = f"{info.get('first_name', '')} {info.get('last_name', '')}".strip()
                db_username = info.get('username', '')
                verified = "✅" if info.get('is_verified') else "❌"
                print(f"  {verified} {item['name']:40} → {db_name:30} (@{db_username}) [{item['match_type']}]")
        else:
            print("  Не найдено")
        
        print("\n" + "=" * 100)
        print("📊 НАЙДЕНО В ОПРОСАХ (но не в БД)")
        print("=" * 100)
        if found_in_votes:
            for item in found_in_votes:
                info = item['match_info']
                vote_name = info.get('vote_name', '')
                user_id = info.get('user_id', '')
                print(f"  📊 {item['name']:40} → {vote_name:40} (ID: {user_id})")
        else:
            print("  Не найдено")
        
        print("\n" + "=" * 100)
        print("❌ НЕ НАЙДЕНО")
        print("=" * 100)
        if not_found:
            for item in not_found:
                username_str = f"@{item['username']}" if item['username'] else "нет username"
                tag_str = f"тег: {item['tag']}" if item.get('tag') else "тег: 8958"
                print(f"  ❌ {item['name']:40} ({username_str}, {tag_str})")
        else:
            print("  Все найдены!")
        
        print("\n" + "=" * 100)
        print("📊 СТАТИСТИКА")
        print("=" * 100)
        print(f"  ✅ Найдено в БД: {len(found_in_db)}")
        print(f"  📊 Найдено в опросах: {len(found_in_votes)}")
        print(f"  ❌ Не найдено: {len(not_found)}")
        print(f"  📈 Всего найдено: {len(found_in_db) + len(found_in_votes)}/{len(COURIERS_DS_8958)}")
        
        if not_found:
            print("\n💡 Рекомендация: Запустите скрипт add_couriers_from_list.py для автоматического добавления курьеров из опросов:")
            print("   python scripts/add_couriers_from_list.py")


if __name__ == "__main__":
    asyncio.run(check_couriers_in_db())

