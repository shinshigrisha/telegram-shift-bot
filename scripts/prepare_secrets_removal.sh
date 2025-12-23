#!/bin/bash
# Скрипт для подготовки к удалению секретов из истории git

echo "🔐 Подготовка к удалению секретов из истории git"
echo ""
echo "Этот скрипт поможет вам подготовиться к удалению секретов."
echo ""

# Проверяем наличие git-filter-repo
if ! command -v git-filter-repo &> /dev/null; then
    echo "📦 Установка git-filter-repo..."
    pip3 install git-filter-repo || {
        echo "❌ Ошибка: не удалось установить git-filter-repo"
        echo "Установите вручную: pip3 install git-filter-repo"
        exit 1
    }
    echo "✅ git-filter-repo установлен"
else
    echo "✅ git-filter-repo уже установлен"
fi

echo ""
echo "📋 Чек-лист перед удалением секретов из истории:"
echo ""
echo "1. ✅ Сменить BOT_TOKEN:"
echo "   - Откройте @BotFather в Telegram"
echo "   - Отправьте /revoke и выберите вашего бота"
echo "   - Получите новый токен командой /token"
echo "   - Обновите BOT_TOKEN в .env файле"
echo ""
echo "2. ✅ Сменить DB_PASSWORD:"
echo "   - Подключитесь к PostgreSQL: psql -U bot_user -d shift_bot"
echo "   - Выполните: ALTER USER bot_user WITH PASSWORD 'новый_пароль';"
echo "   - Обновите DB_PASSWORD в .env файле"
echo ""
echo "3. ✅ Сменить REDIS_PASSWORD:"
echo "   - Измените requirepass в redis.conf"
echo "   - Перезапустите Redis"
echo "   - Обновите REDIS_PASSWORD в .env файле"
echo ""
echo "4. ✅ Сменить ENCRYPTION_KEY:"
echo "   - Сгенерируйте новый ключ: python3 -c \"import secrets; print(secrets.token_urlsafe(32))\""
echo "   - Обновите ENCRYPTION_KEY в .env файле"
echo ""
echo "5. ✅ Сделать резервную копию репозитория:"
echo "   - git clone --mirror <repository-url> backup-repo.git"
echo ""
echo "6. ✅ Уведомить коллабораторов (если есть)"
echo ""
read -p "Все ключи изменены? (yes/no): " keys_changed

if [ "$keys_changed" != "yes" ]; then
    echo ""
    echo "⚠️  Сначала смените все ключи, затем запустите:"
    echo "   bash scripts/remove_secrets_from_history.sh"
    exit 0
fi

echo ""
echo "✅ Готово к удалению секретов из истории!"
echo ""
echo "Следующий шаг:"
echo "   bash scripts/remove_secrets_from_history.sh"
echo ""

