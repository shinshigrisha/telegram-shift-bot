"""
Скрипт для исправления ADMIN_IDS - удаление ID ботов.
"""
import re
from pathlib import Path

# Путь к .env файлу
env_path = Path(__file__).parent.parent / ".env"

# ID ботов, которые нужно удалить (вызывают ошибки)
bot_ids_to_remove = [7578248340, 5128512787]

# ID пользователей, которые нужно оставить
valid_user_ids = [445137184, 1010897385]

def fix_admin_ids():
    """Исправить ADMIN_IDS в .env файле."""
    if not env_path.exists():
        print(f"❌ Файл .env не найден: {env_path}")
        return
    
    # Читаем .env файл
    with open(env_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Ищем строку с ADMIN_IDS
    pattern = r'ADMIN_IDS=\[(.*?)\]'
    match = re.search(pattern, content)
    
    if not match:
        print("❌ ADMIN_IDS не найден в .env файле")
        return
    
    # Парсим текущие ID
    current_ids_str = match.group(1)
    current_ids = [int(id.strip()) for id in current_ids_str.split(',') if id.strip()]
    
    print(f"📋 Текущие ADMIN_IDS: {current_ids}")
    
    # Удаляем ID ботов
    filtered_ids = [id for id in current_ids if id not in bot_ids_to_remove]
    
    if filtered_ids == current_ids:
        print("✅ Все ID уже корректны, изменений не требуется")
        return
    
    print(f"❌ Удаляем ID ботов: {bot_ids_to_remove}")
    print(f"✅ Оставляем ID пользователей: {filtered_ids}")
    
    # Формируем новую строку
    new_ids_str = ','.join(map(str, filtered_ids))
    new_line = f"ADMIN_IDS=[{new_ids_str}]"
    
    # Заменяем в содержимом
    new_content = re.sub(pattern, new_line, content)
    
    # Создаем резервную копию
    backup_path = env_path.with_suffix('.env.backup')
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"💾 Создана резервная копия: {backup_path}")
    
    # Записываем обновленный файл
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✅ ADMIN_IDS обновлен: {new_line}")
    print("\n⚠️  ВАЖНО: Перезапустите бота, чтобы изменения вступили в силу!")


if __name__ == "__main__":
    fix_admin_ids()

