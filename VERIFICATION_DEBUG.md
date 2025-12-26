# Отладка системы верификации

## Проверка настроек

1. **Убедитесь, что верификация включена в `.env`:**
   ```
   ENABLE_VERIFICATION=True
   ```

2. **Проверьте, что бот является администратором группы** с правами:
   - ✅ Удалять сообщения
   - ✅ Ограничивать участников
   - ✅ Отправлять сообщения

## Проверка работы системы

### 1. При добавлении нового пользователя в группу

Проверьте логи бота. Должны быть записи:
```
New member <user_id> in chat <chat_id>, is_verified: False
✅ Restricted unverified user <user_id> in chat <chat_id>
✅ Sent welcome message with Start button...
```

**Если нет записи "Restricted":**
- Бот не имеет прав администратора
- Или пользователь уже верифицирован

**Если нет записи "Sent welcome message":**
- Проверьте права бота на отправку сообщений
- Проверьте, что группа найдена в БД

### 2. При нажатии кнопки "Старт"

Проверьте логи:
```
User <user_id> called /start. ENABLE_VERIFICATION=True, is_curator=False, has_user_service=True, has_state=True
User <user_id> called /start with param: 'verify', is_verified: False
Starting verification process for user <user_id>
```

**Если нет записи "Starting verification process":**
- Проверьте, что `ENABLE_VERIFICATION=True`
- Проверьте, что пользователь не куратор
- Проверьте, что `user_service` и `state` доступны

### 3. При вводе фамилии и имени

Проверьте логи:
```
Verifying user <user_id> with name: <last_name> <first_name>
User <user_id> verified successfully. is_verified=True
✅ Restored permissions for user <user_id> in group <group_name>
```

**Если нет записи "Restored permissions":**
- Проверьте, что группа найдена в БД
- Проверьте, что пользователь является участником группы
- Проверьте права бота на изменение прав участников

## Частые проблемы

### Проблема: Кнопка "Старт" не появляется
**Решение:**
- Проверьте, что `ENABLE_VERIFICATION=True`
- Проверьте логи на наличие ошибок при отправке сообщения
- Проверьте права бота в группе

### Проблема: После нажатия кнопки ничего не происходит
**Решение:**
- Проверьте логи на наличие записи "User called /start"
- Проверьте, что бот может отправлять сообщения в приватный чат
- Проверьте, что пользователь начал диалог с ботом

### Проблема: После верификации права не восстанавливаются
**Решение:**
- Проверьте логи на наличие ошибок при восстановлении прав
- Проверьте, что группа найдена в БД
- Проверьте, что пользователь является участником группы
- Проверьте права бота на изменение прав участников

### Проблема: Пользователь не может писать после верификации
**Решение:**
- Проверьте логи на наличие записи "Restored permissions"
- Проверьте, что права действительно восстановлены (через `get_chat_member`)
- Убедитесь, что бот имеет права администратора

## Ручная проверка через БД

```sql
-- Проверить статус верификации пользователя
SELECT id, first_name, last_name, is_verified 
FROM users 
WHERE id = <user_id>;

-- Проверить все неверифицированные пользователи
SELECT id, first_name, last_name, is_verified 
FROM users 
WHERE is_verified = false;
```

## Ручная проверка через Telegram API

Используйте скрипт для проверки прав пользователя:
```python
from aiogram import Bot
import asyncio

async def check_user_permissions():
    bot = Bot(token="YOUR_BOT_TOKEN")
    chat_id = -1001234567890  # ID группы
    user_id = 123456789  # ID пользователя
    
    member = await bot.get_chat_member(chat_id, user_id)
    print(f"Status: {member.status}")
    if hasattr(member, 'permissions'):
        print(f"Can send messages: {member.permissions.can_send_messages}")
    
    await bot.session.close()

asyncio.run(check_user_permissions())
```

