# 🚀 Деплой

## Через Docker Compose

```bash
git clone <repository-url>
cd telegram-shift-bot
cp .env.example .env
# отредактируйте .env под ваш сервер
docker compose up -d postgres redis
python3 scripts/init_runtime_database.py
docker compose up -d bot
```

`scripts/init_runtime_database.py` не только создает базовую схему, но и автоматически применяет новые SQL-миграции из папки `migrations/`.

## Что проверить перед боевым запуском

- бот добавлен в нужные группы и назначен администратором;
- у каждой группы сохранен корректный `Chat ID`;
- в `.env` заполнены `BOT_TOKEN`, `ADMIN_IDS`, `DB_*`, `REDIS_*`;
- если Redis запущен с паролем, тот же пароль указан в `REDIS_PASSWORD`;
- после создания группы проверьте, что у дневных групп появились стандартные слоты;
- выполните один тестовый опрос и одно ручное закрытие через `/admin`.

## После запуска

- Проверьте логи: `docker compose logs -f bot`
- Проверьте таблицы: `docker compose exec postgres psql -U bot_user -d shift_bot -c "\dt"`
- Проверьте Redis: `docker compose exec redis redis-cli -a "$REDIS_PASSWORD" ping`
- Проверьте статус контейнеров: `docker compose ps`

## Сброс перед новым стартом

```bash
docker compose exec -T postgres psql -U bot_user -d shift_bot < scripts/reset_runtime_data.sql
bash scripts/reset_redis_data.sh
python3 scripts/init_runtime_database.py
```

## Обновление на сервере

```bash
bash scripts/deploy_update.sh
```

Скрипт обновления делает три обязательных шага перед запуском:
- пересобирает контейнер бота;
- выполняет `python3 -m compileall src config scripts`;
- применяет новые миграции через `python3 scripts/init_runtime_database.py`.
