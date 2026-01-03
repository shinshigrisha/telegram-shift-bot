# 🚀 Деплой

Руководство по развертыванию Telegram Shift Bot в production.

---

## 📋 Требования

### Сервер

- **ОС:** Linux (Ubuntu 20.04+ рекомендуется)
- **RAM:** минимум 2GB (рекомендуется 4GB+)
- **CPU:** минимум 2 ядра
- **Диск:** минимум 20GB свободного места

### Программное обеспечение

- **Docker** 20.10+
- **Docker Compose** 2.0+
- **Git**

---

## 🐳 Docker Compose (рекомендуется)

### Быстрый старт

```bash
# 1. Клонируйте репозиторий
git clone <repository-url>
cd telegram-shift-bot

# 2. Создайте .env файл
cp .env.example .env
nano .env  # Заполните все переменные

# 3. Запустите все сервисы
docker compose up -d

# 4. Проверьте логи
docker compose logs -f bot
```

### Структура сервисов

```yaml
services:
  postgres:    # PostgreSQL 15
  redis:       # Redis 7
  bot:         # Telegram бот
```

### Управление сервисами

```bash
# Запуск всех сервисов
docker compose up -d

# Остановка всех сервисов
docker compose down

# Перезапуск бота
docker compose restart bot

# Просмотр логов
docker compose logs -f bot

# Просмотр статуса
docker compose ps
```

---

## 🔧 Настройка production

### 1. Переменные окружения

Создайте файл `.env` с production настройками:

```env
# Telegram Bot
BOT_TOKEN=your_production_bot_token
ADMIN_IDS=123456789,987654321

# База данных PostgreSQL
DATABASE_URL=postgresql://bot_user:strong_password@postgres:5432/shift_bot

# Redis
REDIS_URL=redis://:strong_redis_password@redis:6379/0

# AI-куратор
GROQ_API_KEY=your_groq_api_key

# Настройки
TZ=Europe/Moscow
LOG_LEVEL=INFO

# Production настройки
ENABLE_VERIFICATION=True
ENABLE_ADMIN_NOTIFICATIONS=True
ENABLE_COURIER_WARNINGS=True
```

**Важно:**
- Используйте сильные пароли для production
- Не коммитьте `.env` в git
- Регулярно обновляйте пароли

### 2. Безопасность

#### Пароли

```bash
# Генерация сильного пароля для PostgreSQL
openssl rand -base64 32

# Генерация сильного пароля для Redis
openssl rand -base64 32
```

#### Ограничение доступа

```bash
# Ограничьте доступ к портам PostgreSQL и Redis только для локальных подключений
# В docker-compose.yml уберите порты из секции ports для postgres и redis
# Или используйте firewall
```

### 3. Логирование

Логи сохраняются в:
- `logs/bot.log` — основной лог бота
- `logs/explainability/` — логи explainability для AI-куратора

**Ротация логов:**

```bash
# Установите logrotate
sudo apt-get install logrotate

# Создайте конфигурацию
sudo nano /etc/logrotate.d/telegram-shift-bot
```

```conf
/path/to/telegram-shift-bot/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    missingok
    create 0644 root root
}
```

---

## 📦 Обновление на сервере

### Автоматическое обновление

```bash
# Используйте скрипт для автоматического обновления
cd /opt/telegram-shift-bot
bash scripts/deploy_update.sh
```

### Ручное обновление

```bash
# 1. Остановите бота
docker compose stop bot

# 2. Сделайте бэкап
bash scripts/backup_all.sh

# 3. Обновите код
git pull origin main

# 4. Пересоберите образ
docker compose build --no-cache bot

# 5. Выполните миграции (если есть)
docker compose run --rm bot python scripts/run_migration_users.py

# 6. Запустите бота
docker compose up -d bot

# 7. Проверьте логи
docker compose logs -f bot
```

---

## 💾 Резервное копирование

### Автоматические бэкапы

#### PostgreSQL

```bash
# Создайте cron задачу
crontab -e

# Добавьте задачу (каждый день в 2:00)
0 2 * * * /path/to/telegram-shift-bot/scripts/backup_postgres.sh >> /var/log/postgres_backup.log 2>&1
```

#### Redis

```bash
# Добавьте задачу (каждый день в 3:00)
0 3 * * * /path/to/telegram-shift-bot/scripts/backup_redis.sh >> /var/log/redis_backup.log 2>&1
```

#### Комплексный бэкап

```bash
# Добавьте задачу (каждый день в 4:00)
0 4 * * * /path/to/telegram-shift-bot/scripts/backup_all.sh >> /var/log/backup_all.log 2>&1
```

### Восстановление из бэкапа

#### PostgreSQL

```bash
# Остановите бота
docker compose stop bot

# Восстановите из бэкапа
docker compose exec -T postgres psql -U bot_user -d shift_bot < backups/postgres_backup_YYYYMMDD_HHMMSS.sql

# Запустите бота
docker compose start bot
```

#### Redis

```bash
# Остановите Redis
docker compose stop redis

# Скопируйте бэкап
docker cp backups/redis_backup_YYYYMMDD_HHMMSS.rdb $(docker compose ps -q redis):/data/dump.rdb

# Запустите Redis
docker compose start redis
```

---

## 🔍 Мониторинг

### Системный мониторинг

**Через админ-панель:**

1. Откройте админ-панель (`/admin`)
2. Нажмите "📈 Мониторинг"
3. Нажмите "💻 Системный статус"
4. Просмотрите:
   - CPU usage
   - RAM usage
   - Disk usage
   - System uptime

### Логи

**Просмотр логов:**

```bash
# Логи бота
docker compose logs -f bot

# Или напрямую
tail -f logs/bot.log

# Логи explainability
ls -la logs/explainability/
```

### Health checks

**Проверка здоровья сервисов:**

```bash
# PostgreSQL
docker compose exec postgres pg_isready -U bot_user

# Redis
docker compose exec redis redis-cli ping

# Бот (проверка через логи)
docker compose logs bot | tail -20
```

---

## 🔧 Troubleshooting

### Проблема: Бот не запускается

**Решение:**

```bash
# Проверьте логи
docker compose logs bot

# Проверьте переменные окружения
docker compose config

# Проверьте подключение к БД
docker compose exec postgres psql -U bot_user -d shift_bot -c "SELECT 1;"
```

### Проблема: Ошибки подключения к БД

**Решение:**

```bash
# Проверьте, запущена ли БД
docker compose ps postgres

# Проверьте логи PostgreSQL
docker compose logs postgres

# Проверьте параметры подключения в .env
cat .env | grep DATABASE
```

### Проблема: Ошибки подключения к Redis

**Решение:**

```bash
# Проверьте, запущен ли Redis
docker compose ps redis

# Проверьте логи Redis
docker compose logs redis

# Проверьте пароль
docker compose exec redis redis-cli -a your_password ping
```

### Проблема: Миграции не выполняются

**Решение:**

```bash
# Выполните миграцию вручную
docker compose exec -T postgres psql -U bot_user -d shift_bot < migrations/009_create_unified_knowledge_base.sql

# Или через Python скрипт
docker compose run --rm bot python scripts/run_migration_users.py
```

---

## 📊 Производительность

### Оптимизация PostgreSQL

```sql
-- Проверка индексов
SELECT tablename, indexname FROM pg_indexes WHERE schemaname = 'public';

-- Анализ таблиц
ANALYZE faq_ai;
ANALYZE unified_knowledge_base;
```

### Оптимизация Redis

```bash
# Проверка использования памяти
docker compose exec redis redis-cli INFO memory

# Очистка старых данных (осторожно!)
docker compose exec redis redis-cli FLUSHDB
```

---

## 🔒 Безопасность

### Рекомендации

1. **Используйте сильные пароли** для всех сервисов
2. **Ограничьте доступ** к портам PostgreSQL и Redis
3. **Регулярно обновляйте** зависимости
4. **Делайте бэкапы** регулярно
5. **Мониторьте логи** на наличие ошибок
6. **Используйте HTTPS** для всех внешних подключений (если применимо)

### Обновление зависимостей

```bash
# Обновите requirements.txt
pip list --outdated

# Обновите Docker образы
docker compose pull

# Пересоберите образы
docker compose build --no-cache
```

---

## 📚 Дополнительные ресурсы

- [Быстрый старт](GETTING_STARTED.md)
- [Архитектура](ARCHITECTURE.md)
- [База данных](DATABASE.md)

---

**Версия:** 2.0.0  
**Последнее обновление:** 2026-01-01
