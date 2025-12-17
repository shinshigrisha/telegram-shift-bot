import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import text

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.database import engine, AsyncSessionLocal


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_tables() -> None:
    """Создание таблиц в базе данных из db/init.sql (пооперационное выполнение)."""
    try:
        async with engine.begin() as conn:
            with open("db/init.sql", "r", encoding="utf-8") as f:
                sql_content = f.read()

            # Разбиваем по ; и выполняем по очереди (asyncpg не любит мульти-стейтмент в prepared)
            statements = [
                stmt.strip()
                for stmt in sql_content.split(";")
                if stmt.strip()
            ]

            for stmt in statements:
                await conn.execute(text(stmt))

            logger.info("Tables created successfully")
    except Exception as e:  # noqa: BLE001
        logger.error("Error creating tables: %s", e)
        raise


async def add_default_admin() -> None:
    """Добавление админа по умолчанию на основе ADMIN_IDS из .env."""
    import os
    import json
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()

    admin_ids_str = os.getenv("ADMIN_IDS", "[]")
    try:
        # Парсим JSON список
        admin_ids = json.loads(admin_ids_str)
        if not isinstance(admin_ids, list):
            admin_ids = []
    except (json.JSONDecodeError, TypeError):
        logger.warning("Invalid ADMIN_IDS format, skipping admin creation")
        return

    from sqlalchemy import text

    async with AsyncSessionLocal() as session:
        for admin_id in admin_ids:
            try:
                admin_id_int = int(admin_id) if isinstance(admin_id, str) else admin_id
                # Проверяем существование
                result = await session.execute(
                    text("SELECT user_id FROM administrators WHERE user_id = :user_id"),
                    {"user_id": int(admin_id)},
                )
                existing = result.scalar_one_or_none()

                if not existing:
                    # Создаем
                    await session.execute(
                        text(
                            """
                            INSERT INTO administrators (user_id, username, is_super_admin)
                            VALUES (:user_id, :username, :is_super_admin)
                            ON CONFLICT (user_id) DO UPDATE
                            SET username = EXCLUDED.username, is_super_admin = EXCLUDED.is_super_admin
                            """
                        ),
                        {
                            "user_id": admin_id_int,
                            "username": f"admin_{admin_id_int}",
                            "is_super_admin": True,
                        },
                    )
                    await session.commit()
                    logger.info("Added admin: %s", admin_id_int)
                else:
                    logger.info("Admin %s already exists", admin_id_int)
            except Exception as e:
                await session.rollback()
                logger.error("Error adding admin %s: %s", admin_id_int, e)


async def main() -> None:
    logger.info("Starting first setup...")
    try:
        await create_tables()
        await add_default_admin()
        logger.info("Setup completed successfully")
    except Exception as e:  # noqa: BLE001
        logger.error("Setup failed: %s", e)


if __name__ == "__main__":
    asyncio.run(main())


