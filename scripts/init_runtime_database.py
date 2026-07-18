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

BASE_DIR = Path(__file__).parent.parent
MIGRATIONS_DIR = BASE_DIR / "migrations"


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

CREATE TABLE IF NOT EXISTS poll_reminder_dispatches (
    id SERIAL PRIMARY KEY,
    poll_id UUID NOT NULL REFERENCES daily_polls(id) ON DELETE CASCADE,
    reminder_hour INTEGER NOT NULL,
    is_night BOOLEAN NOT NULL DEFAULT FALSE,
    sent_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (poll_id, reminder_hour, is_night)
);

CREATE INDEX IF NOT EXISTS idx_poll_reminder_dispatches_poll_id
    ON poll_reminder_dispatches (poll_id);
"""

SCHEMA_MIGRATIONS_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR(255) NOT NULL UNIQUE,
    applied_at TIMESTAMP NOT NULL DEFAULT NOW()
);
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


def _get_migration_files() -> list[Path]:
    if not MIGRATIONS_DIR.exists():
        return []
    return sorted(
        path for path in MIGRATIONS_DIR.glob("*.sql")
        if path.is_file()
    )


async def _ensure_schema_migrations(conn: asyncpg.Connection) -> None:
    await conn.execute(SCHEMA_MIGRATIONS_SQL)


async def _get_applied_migrations(conn: asyncpg.Connection) -> set[str]:
    rows = await conn.fetch("SELECT migration_name FROM schema_migrations")
    return {row["migration_name"] for row in rows}


async def _apply_migrations(conn: asyncpg.Connection) -> list[str]:
    await _ensure_schema_migrations(conn)
    applied = await _get_applied_migrations(conn)
    applied_now: list[str] = []

    for migration_path in _get_migration_files():
        migration_name = migration_path.name
        if migration_name in applied:
            continue

        migration_sql = migration_path.read_text(encoding="utf-8")
        async with conn.transaction():
            await conn.execute(migration_sql)
            await conn.execute(
                """
                INSERT INTO schema_migrations (migration_name)
                VALUES ($1)
                ON CONFLICT (migration_name) DO NOTHING
                """,
                migration_name,
            )
        applied_now.append(migration_name)

    return applied_now


async def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        sys.path.insert(0, str(BASE_DIR))
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
                applied_migrations = await _apply_migrations(conn)
                print(f"✅ Рабочая схема БД инициализирована: {candidate}")
                if applied_migrations:
                    print("📦 Применены миграции:")
                    for migration_name in applied_migrations:
                        print(f"  - {migration_name}")
                else:
                    print("ℹ️ Новых миграций нет")
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
