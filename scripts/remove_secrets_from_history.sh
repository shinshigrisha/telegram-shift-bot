#!/bin/bash
# ⚠️ ВНИМАНИЕ: Этот скрипт удалит секреты из истории git
# Это изменит историю репозитория - используйте с осторожностью!

set -e

echo "⚠️  ВНИМАНИЕ: Этот скрипт удалит секреты из истории git"
echo "Это изменит историю репозитория!"
echo ""
echo "Перед выполнением убедитесь, что:"
echo "1. Вы сделали резервную копию репозитория"
echo "2. Все коллабораторы знают об изменении истории"
echo "3. Вы готовы к force push"
echo ""
read -p "Продолжить? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Отменено."
    exit 1
fi

# Проверяем наличие git-filter-repo
if ! command -v git-filter-repo &> /dev/null; then
    echo "Установка git-filter-repo..."
    pip install git-filter-repo || {
        echo "Ошибка: не удалось установить git-filter-repo"
        echo "Установите вручную: pip install git-filter-repo"
        exit 1
    }
fi

echo ""
echo "Удаление секретов из истории..."

# Список секретов для удаления (из коммита 70cbd358)
SECRETS=(
    "BOT_TOKEN=<REMOVED>"
    "DB_PASSWORD=<REMOVED>"
    "REDIS_PASSWORD=<REMOVED>"
    "ENCRYPTION_KEY=<REMOVED>="
)

# Создаем временный файл с паттернами для замены
TEMP_FILE=$(mktemp)
for secret in "${SECRETS[@]}"; do
    # Извлекаем ключ и значение
    key=$(echo "$secret" | cut -d'=' -f1)
    value=$(echo "$secret" | cut -d'=' -f2-)
    # Заменяем значение на placeholder
    echo "s|${key}=${value}|${key}=<REMOVED>|g" >> "$TEMP_FILE"
done

# Используем git-filter-repo для удаления секретов
git filter-repo --replace-text "$TEMP_FILE" --force

# Удаляем временный файл
rm "$TEMP_FILE"

echo ""
echo "✅ Секреты удалены из истории!"
echo ""
echo "⚠️  ВАЖНО: Теперь нужно:"
echo "1. Сменить все ключи (BOT_TOKEN, DB_PASSWORD, REDIS_PASSWORD, ENCRYPTION_KEY)"
echo "2. Сделать force push: git push --force --all"
echo "3. Уведомить всех коллабораторов о необходимости пересоздать репозиторий"
echo ""
echo "⚠️  КРИТИЧЕСКИ ВАЖНО: Смените все ключи немедленно!"
echo "   - BOT_TOKEN: получите новый у @BotFather"
echo "   - DB_PASSWORD: измените пароль в PostgreSQL"
echo "   - REDIS_PASSWORD: измените пароль в Redis"
echo "   - ENCRYPTION_KEY: сгенерируйте новый ключ"

