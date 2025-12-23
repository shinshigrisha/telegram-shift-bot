#!/bin/bash
# Скрипт для проверки наличия секретов в коммитах

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Проверка наличия секретов в staged файлах...${NC}"

# Файлы, которые можно игнорировать (примеры, документация)
IGNORE_FILES=(
    ".env.example"
    ".git-secrets"
    "README.md"
    "docs/SECURITY.md"
    "SECURITY_SETUP.md"
    "scripts/README_SECURITY.md"
    "scripts/remove_secrets_from_history.sh"
    "scripts/check_secrets.sh"
)

# Функция проверки, нужно ли игнорировать файл
should_ignore_file() {
    local file="$1"
    for ignore_pattern in "${IGNORE_FILES[@]}"; do
        if [[ "$file" == *"$ignore_pattern"* ]]; then
            return 0  # Игнорировать
        fi
    done
    return 1  # Не игнорировать
}

# Паттерны для поиска реальных секретов (не примеров)
# Ищем значения, которые выглядят как реальные секреты
PATTERNS=(
    "BOT_TOKEN=[0-9]{10}:[A-Za-z0-9_-]{35}"  # Реальный формат токена Telegram
    "DB_PASSWORD=[A-Za-z0-9!@#\$%^&*]{12,}"  # Реальные пароли обычно длиннее
    "REDIS_PASSWORD=[A-Za-z0-9!@#\$%^&*]{12,}"
    "ENCRYPTION_KEY=[A-Za-z0-9+/=_-]{32,}"   # Реальные ключи обычно длиннее
)

# Значения-примеры, которые нужно игнорировать
EXAMPLE_VALUES=(
    "your_bot_token_here"
    "your_db_password_here"
    "your_secure_db_password_here"
    "your_secure_redis_password_here"
    "your_encryption_key_here"
    "your_secure_password"
    "<REMOVED>"
    "test_token"
    "example"
)

FOUND_SECRETS=false

# Проверяем staged файлы
for file in $(git diff --cached --name-only); do
    # Пропускаем игнорируемые файлы
    if should_ignore_file "$file"; then
        continue
    fi
    
    # Пропускаем .env файлы (они должны быть в .gitignore)
    if [[ "$file" == *".env"* ]] && [[ "$file" != *".env.example"* ]]; then
        echo -e "${RED}❌ ОШИБКА: Файл $file содержит .env в имени и не должен быть закоммичен!${NC}"
        FOUND_SECRETS=true
        continue
    fi
    
    # Получаем содержимое изменений
    file_content=$(git diff --cached "$file" 2>/dev/null || echo "")
    
    # Проверяем каждый паттерн
    for pattern in "${PATTERNS[@]}"; do
        matches=$(echo "$file_content" | grep -oiE "$pattern" || true)
        if [ -n "$matches" ]; then
            # Проверяем, не является ли это примером
            is_example=false
            for example in "${EXAMPLE_VALUES[@]}"; do
                if echo "$matches" | grep -qi "$example"; then
                    is_example=true
                    break
                fi
            done
            
            if [ "$is_example" = false ]; then
                echo -e "${RED}❌ ОШИБКА: В файле $file обнаружен потенциальный секрет!${NC}"
                echo -e "${RED}   Паттерн: $pattern${NC}"
                FOUND_SECRETS=true
            fi
        fi
    done
done

if [ "$FOUND_SECRETS" = true ]; then
    echo -e "\n${RED}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}  ВНИМАНИЕ: Обнаружены потенциальные секреты!${NC}"
    echo -e "${RED}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}Секреты не должны быть закоммичены в репозиторий!${NC}"
    echo -e "${YELLOW}Используйте переменные окружения (.env файл) для хранения секретов.${NC}"
    echo -e "${YELLOW}Убедитесь, что .env файл добавлен в .gitignore${NC}"
    echo ""
    exit 1
else
    echo -e "${GREEN}✅ Секреты не обнаружены.${NC}"
    exit 0
fi
