#!/usr/bin/env python3
"""
Скрипт для верификации и обновления данных пользователей.
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import AsyncSessionLocal
from src.repositories.user_repository import UserRepository
from src.services.user_service import UserService

# Импортируем все модели для правильной инициализации SQLAlchemy
from src.models.user import User  # noqa: F401


# Данные пользователей для обновления и верификации
USERS_DATA = [
    {"user_id": 187538798, "full_name": "Шигапов Артур"},
    {"user_id": 234368197, "full_name": "Гениев Азиз"},
    {"user_id": 304884791, "full_name": "Раев Алексей"},
    {"user_id": 586980459, "full_name": "Быков Алексей"},
    {"user_id": 627046105, "full_name": "Мукамбетов Тагай"},
    {"user_id": 729828165, "full_name": "Матираимов Манасбек"},
    {"user_id": 733803410, "full_name": "Азизов Эльдар"},
    {"user_id": 747884239, "full_name": "Мусралиев Арстан"},
    {"user_id": 774644785, "full_name": "Давидочкин Андрей"},
    {"user_id": 814439240, "full_name": "Ольга Кузнецова"},
    {"user_id": 912701050, "full_name": "Левчаев Ярослав"},
    {"user_id": 913414619, "full_name": "Добрынин Николай"},
    {"user_id": 946958248, "full_name": "Шуваев Кирилл"},
    {"user_id": 961829308, "full_name": "Гимбатов Марсель"},
    {"user_id": 979547312, "full_name": "Асадбек Нуралиев"},
    {"user_id": 1017228084, "full_name": "Тошев Фарход"},
    {"user_id": 1030361842, "full_name": "Смирнов Константин"},
    {"user_id": 1048083769, "full_name": "Сафаралиев Бахлул"},
    {"user_id": 1149806115, "full_name": "Евгений Аксентьев"},
    {"user_id": 1177831441, "full_name": "Михаил Логинов"},
    {"user_id": 1231171701, "full_name": "Озтораман ангин"},
    {"user_id": 1247703073, "full_name": "Алмардогов Искандар"},
    {"user_id": 1280679498, "full_name": "Альжанов Артём"},
    {"user_id": 1312213431, "full_name": "Иванов Вадим"},
    {"user_id": 1381787087, "full_name": "Шевелев Гоша"},
    {"user_id": 1428179405, "full_name": "Исаев Никита"},
    {"user_id": 1662491469, "full_name": "Маралин Семен"},
    {"user_id": 5000862646, "full_name": "Музафаров Умед"},
    {"user_id": 5062375341, "full_name": "Нурзода Бунёд"},
    {"user_id": 5142238496, "full_name": "Мампория Дмитрий"},
    {"user_id": 5398536529, "full_name": "Косимов Насим"},
    {"user_id": 5468085358, "full_name": "Азимов Рахматулло"},
    {"user_id": 5492009651, "full_name": "Атамов Мирлан"},
    {"user_id": 5616106740, "full_name": "Одинаев Фаррух"},
    {"user_id": 5969137292, "full_name": "Ловягин Кирилл"},
    {"user_id": 5979778886, "full_name": "Жуман Мухаммедали"},
    {"user_id": 6020477842, "full_name": "Замирбеков Далимбек"},
    {"user_id": 6065514830, "full_name": "Рахимов Хайрулло"},
    {"user_id": 6249171593, "full_name": "Махмалиев Солех"},
    {"user_id": 6278091785, "full_name": "Ардашер С"},
    {"user_id": 6336843295, "full_name": "Саидов Ëкубжон"},
    {"user_id": 6681427127, "full_name": "Алимардоров Файзали"},
    {"user_id": 7040200938, "full_name": "Боев Далер"},
    {"user_id": 7051295902, "full_name": "Шоев Новруз"},
    {"user_id": 7371104282, "full_name": "Алишер Шапатаев"},
    {"user_id": 7531566123, "full_name": "Мирзалиев Акмалджон"},
    {"user_id": 7546966341, "full_name": "Исоев Давлат"},
    {"user_id": 7743403234, "full_name": "Обдумали Абдуганиев"},
    {"user_id": 7784572644, "full_name": "Кузнецов Евгений"},
    {"user_id": 7912942516, "full_name": "Сатторов Рамазон"},
    {"user_id": 7927919635, "full_name": "Жээнали Уулу Жоодарбек"},
    {"user_id": 8401132767, "full_name": "Глеб Филипенко"},
]


async def verify_and_update_users():
    """Верифицировать и обновить данные пользователей."""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        
        verified_count = 0
        updated_count = 0
        not_found_count = 0
        errors = []
        
        print("\n" + "=" * 100)
        print("✅ ВЕРИФИКАЦИЯ И ОБНОВЛЕНИЕ ПОЛЬЗОВАТЕЛЕЙ")
        print("=" * 100)
        
        for user_data in USERS_DATA:
            user_id = user_data["user_id"]
            full_name = user_data["full_name"].strip()
            
            # Разделяем полное имя на фамилию и имя
            # Формат: "Фамилия Имя" или "Фамилия Имя Отчество"
            name_parts = full_name.split()
            if len(name_parts) >= 2:
                last_name = name_parts[0]  # Фамилия
                first_name = " ".join(name_parts[1:])  # Имя (может быть с отчеством)
            elif len(name_parts) == 1:
                # Если только одно слово, считаем его именем
                first_name = name_parts[0]
                last_name = None
            else:
                first_name = None
                last_name = None
            
            try:
                # Получаем пользователя
                user = await user_service.user_repo.get_by_id(user_id)
                
                if not user:
                    not_found_count += 1
                    print(f"  ⚠️  Не найден: ID {user_id} | {full_name}")
                    continue
                
                # Обновляем данные и верифицируем
                updated = False
                if first_name and user.first_name != first_name:
                    user.first_name = first_name
                    updated = True
                if last_name and user.last_name != last_name:
                    user.last_name = last_name
                    updated = True
                
                # Верифицируем пользователя
                if not user.is_verified:
                    user.is_verified = True
                    verified_count += 1
                    updated = True
                
                if updated:
                    await session.flush()
                    updated_count += 1
                    print(f"  ✅ Обновлен и верифицирован: ID {user_id} | {full_name}")
                else:
                    print(f"  ℹ️  Уже верифицирован: ID {user_id} | {full_name}")
                    
            except Exception as e:
                error_msg = f"Ошибка при обновлении пользователя {user_id}: {e}"
                errors.append(error_msg)
                print(f"  ❌ {error_msg}")
        
        # Коммитим изменения
        try:
            await session.commit()
            print("\n" + "=" * 100)
            print(f"✅ Верифицировано пользователей: {verified_count}")
            print(f"🔄 Обновлено пользователей: {updated_count}")
            if not_found_count > 0:
                print(f"⚠️  Не найдено пользователей: {not_found_count}")
            if errors:
                print(f"❌ Ошибок: {len(errors)}")
                for error in errors:
                    print(f"   • {error}")
            print("=" * 100)
        except Exception as e:
            await session.rollback()
            print(f"\n❌ Ошибка при сохранении изменений: {e}")
            raise


async def main():
    """Главная функция."""
    try:
        await verify_and_update_users()
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

