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

## После запуска

- Проверьте логи: `docker compose logs -f bot`
- Проверьте таблицы: `docker compose exec postgres psql -U bot_user -d shift_bot -c "\dt"`
- Проверьте Redis: `docker compose exec redis redis-cli -a "$REDIS_PASSWORD" ping`

## Сброс перед новым стартом

```bash
docker compose exec -T postgres psql -U bot_user -d shift_bot < scripts/reset_runtime_data.sql
bash scripts/reset_redis_data.sh
python3 scripts/init_runtime_database.py
```
