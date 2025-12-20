"""
Скрипт для добавления курьеров ДС 8958 в базу данных на основе скриншотов Telegram.
Курьеры идентифицируются по тегу "8958" или "7368" в имени.
"""
import asyncio
import sys
from pathlib import Path

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
    
    # Дополнительные из опросов
    {"name": "Артём Альжанов", "telegram_id": None, "username": None},
    {"name": "Левчаев Ярослав", "telegram_id": None, "username": None},
    {"name": "Valentin VV", "telegram_id": None, "username": None, "tag": "6028"},
    {"name": "Мусралиев Арстан", "telegram_id": None, "username": None},
    {"name": "ИСАЕВ НИКИТА", "telegram_id": None, "username": None},
    {"name": "петр иванов", "telegram_id": 6538286769, "username": "AnastasiaPolonskaya"},
    {"name": "Bunyod", "telegram_id": 5062375341, "username": "buned94"},
    {"name": "五条 悟", "telegram_id": 1017228084, "username": "Farkhod222"},
    {"name": "R.B", "telegram_id": 7935173316, "username": None},
]


async def add_couriers_to_db():
    """Добавить курьеров ДС 8958 в базу данных."""
    async with AsyncSessionLocal() as session:
        added_count = 0
        updated_count = 0
        skipped_count = 0
        
        print(f"📋 Обработка {len(COURIERS_DS_8958)} курьеров ДС 8958...\n")
        
        for courier in COURIERS_DS_8958:
            name = courier.get("name", "").strip()
            username = courier.get("username")
            telegram_id = courier.get("telegram_id")
            tag = courier.get("tag", "8958")
            
            if not name:
                skipped_count += 1
                continue
            
            # Разделяем имя на first_name и last_name
            name_parts = name.split(maxsplit=1)
            first_name = name_parts[0] if name_parts else name
            last_name = name_parts[1] if len(name_parts) > 1 else None
            
            # Если есть telegram_id, используем его для поиска
            if telegram_id:
                result = await session.execute(
                    text("SELECT id, first_name, last_name FROM users WHERE id = :id"),
                    {"id": telegram_id}
                )
                existing = result.fetchone()
                
                if existing:
                    # Обновляем существующего пользователя
                    await session.execute(
                        text("""
                            UPDATE users 
                            SET first_name = :first_name, last_name = :last_name, 
                                username = COALESCE(:username, username), is_verified = TRUE
                            WHERE id = :id
                        """),
                        {
                            "id": telegram_id,
                            "first_name": first_name,
                            "last_name": last_name,
                            "username": username
                        }
                    )
                    updated_count += 1
                    print(f"🔄 Обновлен: {name} (ID: {telegram_id})")
                else:
                    # Создаем нового пользователя
                    await session.execute(
                        text("""
                            INSERT INTO users (id, first_name, last_name, username, is_verified)
                            VALUES (:id, :first_name, :last_name, :username, TRUE)
                        """),
                        {
                            "id": telegram_id,
                            "first_name": first_name,
                            "last_name": last_name,
                            "username": username
                        }
                    )
                    added_count += 1
                    print(f"✅ Добавлен: {name} (ID: {telegram_id})")
            else:
                # Ищем по имени или username
                if username:
                    result = await session.execute(
                        text("SELECT id FROM users WHERE username = :username"),
                        {"username": username}
                    )
                    existing = result.fetchone()
                    
                    if existing:
                        # Обновляем по username
                        await session.execute(
                            text("""
                                UPDATE users 
                                SET first_name = :first_name, last_name = :last_name, is_verified = TRUE
                                WHERE username = :username
                            """),
                            {
                                "username": username,
                                "first_name": first_name,
                                "last_name": last_name
                            }
                        )
                        updated_count += 1
                        print(f"🔄 Обновлен по username: {name} (@{username})")
                    else:
                        skipped_count += 1
                        print(f"⏭️  Пропущен (нет ID): {name} (@{username})")
                else:
                    # Ищем по имени
                    result = await session.execute(
                        text("""
                            SELECT id FROM users 
                            WHERE (first_name = :first_name AND last_name = :last_name)
                               OR (first_name = :name AND last_name IS NULL)
                        """),
                        {
                            "first_name": first_name,
                            "last_name": last_name,
                            "name": name
                        }
                    )
                    existing = result.fetchone()
                    
                    if existing:
                        updated_count += 1
                        print(f"🔄 Найден по имени: {name}")
                    else:
                        skipped_count += 1
                        print(f"⏭️  Пропущен (нет ID и username): {name}")
        
        await session.commit()
        
        print("\n" + "=" * 80)
        print("📊 ИТОГОВАЯ СТАТИСТИКА:")
        print(f"   Всего обработано: {len(COURIERS_DS_8958)}")
        print(f"   Добавлено новых: {added_count}")
        print(f"   Обновлено существующих: {updated_count}")
        print(f"   Пропущено (нет ID): {skipped_count}")
        print("\n💡 Для полного добавления курьеров нужны их Telegram ID.")
        print("   Telegram ID можно получить через бота @userinfobot или @RawDataBot")


if __name__ == "__main__":
    asyncio.run(add_couriers_to_db())


