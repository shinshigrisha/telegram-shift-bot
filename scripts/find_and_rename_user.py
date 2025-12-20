"""
Скрипт для поиска и переименования пользователя в базе данных.
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import AsyncSessionLocal
from sqlalchemy import text


async def find_and_rename_user(search_text: str, new_first_name: str, new_last_name: str, auto_confirm: bool = False):
    """
    Найти пользователя по части имени и переименовать его.
    
    Args:
        search_text: Текст для поиска (может быть частью имени, фамилии или полного имени)
        new_first_name: Новое имя
        new_last_name: Новая фамилия
        auto_confirm: Автоматически подтвердить обновление без запроса
    """
    async with AsyncSessionLocal() as session:
        # Ищем пользователей по части имени или фамилии
        search_pattern = f"%{search_text}%"
        
        result = await session.execute(
            text("""
                SELECT id, first_name, last_name, username, is_verified
                FROM users 
                WHERE first_name ILIKE :pattern 
                   OR last_name ILIKE :pattern
                   OR CONCAT(first_name, ' ', last_name) ILIKE :pattern
                ORDER BY id
            """),
            {"pattern": search_pattern}
        )
        users = result.fetchall()
        
        if not users:
            print(f"❌ Пользователи с текстом '{search_text}' не найдены")
            return
        
        print(f"🔍 Найдено пользователей: {len(users)}\n")
        
        for idx, (user_id, first_name, last_name, username, is_verified) in enumerate(users, 1):
            print(f"{idx}. ID: {user_id}")
            print(f"   Имя: {first_name}")
            print(f"   Фамилия: {last_name}")
            print(f"   Username: {username or 'нет'}")
            print(f"   Верифицирован: {'✅' if is_verified else '❌'}")
            print()
        
        if len(users) == 1:
            # Если найден только один пользователь, обновляем его
            user_id, old_first_name, old_last_name, username, is_verified = users[0]
            
            print(f"📝 Обновление пользователя ID {user_id}:")
            print(f"   Было: {old_first_name} {old_last_name}")
            print(f"   Станет: {new_first_name} {new_last_name}")
            
            # Подтверждение
            if not auto_confirm:
                try:
                    confirm = input("\n❓ Продолжить? (yes/no): ").strip().lower()
                    if confirm not in ['yes', 'y', 'да', 'д']:
                        print("❌ Отменено")
                        return
                except EOFError:
                    print("⚠️  Нет интерактивного ввода, используйте флаг --auto для автоматического подтверждения")
                    return
            
            # Обновляем имя
            await session.execute(
                text("""
                    UPDATE users 
                    SET first_name = :first_name, last_name = :last_name
                    WHERE id = :id
                """),
                {
                    "id": user_id,
                    "first_name": new_first_name,
                    "last_name": new_last_name
                }
            )
            await session.commit()
            
            print(f"\n✅ Имя обновлено успешно!")
            print(f"   ID: {user_id}")
            print(f"   Новое имя: {new_first_name} {new_last_name}")
        else:
            # Если найдено несколько пользователей, просим выбрать
            print("⚠️  Найдено несколько пользователей. Выберите номер для обновления:")
            choice = input("Введите номер (или 'cancel' для отмены): ").strip()
            
            if choice.lower() in ['cancel', 'отмена', 'н']:
                print("❌ Отменено")
                return
            
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(users):
                    user_id, old_first_name, old_last_name, username, is_verified = users[idx]
                    
                    print(f"\n📝 Обновление пользователя ID {user_id}:")
                    print(f"   Было: {old_first_name} {old_last_name}")
                    print(f"   Станет: {new_first_name} {new_last_name}")
                    
                    if not auto_confirm:
                        try:
                            confirm = input("\n❓ Продолжить? (yes/no): ").strip().lower()
                            if confirm not in ['yes', 'y', 'да', 'д']:
                                print("❌ Отменено")
                                return
                        except EOFError:
                            print("⚠️  Нет интерактивного ввода, используйте флаг --auto для автоматического подтверждения")
                            return
                    
                    await session.execute(
                        text("""
                            UPDATE users 
                            SET first_name = :first_name, last_name = :last_name
                            WHERE id = :id
                        """),
                        {
                            "id": user_id,
                            "first_name": new_first_name,
                            "last_name": new_last_name
                        }
                    )
                    await session.commit()
                    
                    print(f"\n✅ Имя обновлено успешно!")
                    print(f"   ID: {user_id}")
                    print(f"   Новое имя: {new_first_name} {new_last_name}")
                else:
                    print("❌ Неверный номер")
            except ValueError:
                print("❌ Неверный ввод")


if __name__ == "__main__":
    # Пример использования
    # Можно передать аргументы командной строки или использовать значения по умолчанию
    
    auto_confirm = "--auto" in sys.argv or "-y" in sys.argv
    if "--auto" in sys.argv:
        sys.argv.remove("--auto")
    if "-y" in sys.argv:
        sys.argv.remove("-y")
    
    if len(sys.argv) >= 4:
        search_text = sys.argv[1]
        new_first_name = sys.argv[2]
        new_last_name = sys.argv[3]
    else:
        # Значения по умолчанию для поиска пользователя с неправильным именем
        search_text = "Закройте этот заказ"
        new_first_name = "Асозода"
        new_last_name = "Муххамаджон"
        
        print("💡 Использование: python scripts/find_and_rename_user.py <поиск> <имя> <фамилия> [--auto]")
        print(f"📋 Поиск по умолчанию: '{search_text}'")
        print(f"📝 Новое имя: {new_first_name} {new_last_name}\n")
    
    asyncio.run(find_and_rename_user(search_text, new_first_name, new_last_name, auto_confirm=auto_confirm))

