#!/usr/bin/env python3
"""
Инициализация рабочей схемы БД для бота.
"""
import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import asyncpg
from dotenv import load_dotenv

load_dotenv()


CORE_SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    telegram_chat_id BIGINT NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    is_night BOOLEAN DEFAULT FALSE,
    poll_close_time TIME DEFAULT '19:00:00',
    settings JSONB DEFAULT '{"slots": [], "max_users_per_slot": 3}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_polls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    poll_date DATE NOT NULL,
    telegram_poll_id VARCHAR(255),
    telegram_message_id BIGINT,
    status VARCHAR(50) DEFAULT 'active',
    results JSONB DEFAULT '{}'::jsonb,
    screenshot_path TEXT,
    closed_at TIMESTAMP,
    reminder_sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(group_id, poll_date)
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_user_id BIGINT UNIQUE NOT NULL,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    username VARCHAR(255),
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS group_members (
    id SERIAL PRIMARY KEY,
    group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    full_name VARCHAR(255) NOT NULL,
    telegram_user_id BIGINT,
    username VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (group_id, full_name)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_group_members_group_telegram_unique
    ON group_members (group_id, telegram_user_id)
    WHERE telegram_user_id IS NOT NULL;
"""


def _build_connection_candidates(database_url: str) -> list[str]:
    candidates = [database_url]
    parsed = urlparse(database_url)

    if parsed.hostname == "postgres":
        localhost_netloc = parsed.netloc.replace("postgres", "localhost", 1)
        localhost_url = urlunparse(parsed._replace(netloc=localhost_netloc))
        if localhost_url not in candidates:
            candidates.append(localhost_url)

    return candidates


async def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from config.settings import settings
        database_url = settings.DATABASE_URL

    if not database_url:
        raise RuntimeError("DATABASE_URL не найден")

    errors: list[str] = []

    for candidate in _build_connection_candidates(database_url):
        try:
            conn = await asyncpg.connect(candidate, ssl=False)
            try:
                await conn.execute(CORE_SCHEMA_SQL)
                print(f"✅ Рабочая схема БД инициализирована: {candidate}")
                return
            finally:
                await conn.close()
        except Exception as exc:
            errors.append(f"{candidate} -> {exc}")

    raise RuntimeError(
        "Не удалось подключиться к PostgreSQL. Проверены варианты:\n- "
        + "\n- ".join(errors)
    )


if __name__ == "__main__":
    asyncio.run(main())
