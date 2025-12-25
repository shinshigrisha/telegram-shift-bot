import asyncio
import json
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError

from config.settings import settings
from src.bot import setup_bot

# #region agent log
DEBUG_LOG_PATH = Path("/Users/senya.miroshnichenko/Desktop/telegram-shift-bot/.cursor/debug.log")

def debug_log(session_id: str, run_id: str, hypothesis_id: str, location: str, message: str, data: dict) -> None:
    """Записать отладочный лог в NDJSON формате."""
    try:
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            log_entry = {
                "sessionId": session_id,
                "runId": run_id,
                "hypothesisId": hypothesis_id,
                "location": location,
                "message": message,
                "data": data,
                "timestamp": asyncio.get_event_loop().time() * 1000 if hasattr(asyncio, "get_event_loop") else 0,
            }
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        pass  # Игнорируем ошибки логирования
# #endregion


# Глобальные переменные для корректной остановки
bot_instance: Optional[Bot] = None
dp_instance: Optional[Dispatcher] = None
shutdown_event = asyncio.Event()


async def check_telegram_connection(bot: Bot, max_retries: int = 5, retry_delay: float = 5.0) -> bool:
    """
    Проверка подключения к Telegram API с повторными попытками.
    
    Args:
        bot: Экземпляр бота
        max_retries: Максимальное количество попыток
        retry_delay: Задержка между попытками в секундах
    
    Returns:
        True если подключение успешно, False иначе
    """
    logger = logging.getLogger(__name__)
    
    for attempt in range(1, max_retries + 1):
        try:
            # #region agent log
            debug_log("debug-session", "connection", "G", f"main.py:check_telegram_connection:{attempt}", "Attempting connection", {
                "attempt": attempt,
                "max_retries": max_retries,
            })
            # #endregion
            await bot.get_me()
            logger.info("Подключение к Telegram API успешно установлено")
            # #region agent log
            debug_log("debug-session", "connection", "G", f"main.py:check_telegram_connection:{attempt}", "Connection successful", {
                "attempt": attempt,
            })
            # #endregion
            return True
        except TelegramNetworkError as e:
            # #region agent log
            debug_log("debug-session", "connection", "G", f"main.py:check_telegram_connection:{attempt}", "Connection failed", {
                "attempt": attempt,
                "error_type": type(e).__name__,
                "error_msg": str(e)[:200],
            })
            # #endregion
            if attempt < max_retries:
                logger.warning(
                    "Попытка %d/%d: Не удалось подключиться к Telegram API: %s. "
                    "Повторная попытка через %.1f секунд...",
                    attempt,
                    max_retries,
                    str(e)[:100],
                    retry_delay,
                )
                await asyncio.sleep(retry_delay)
            else:
                logger.error(
                    "Не удалось подключиться к Telegram API после %d попыток: %s",
                    max_retries,
                    str(e)[:200],
                )
                return False
        except Exception as e:  # noqa: BLE001
            logger.error("Неожиданная ошибка при проверке подключения: %s", e, exc_info=True)
            return False
    
    return False


async def main() -> None:
    """Точка входа для запуска Telegram-бота."""

    # Настройка логирования
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(settings.LOG_FILE),
            logging.StreamHandler(),
        ],
    )

    logger = logging.getLogger(__name__)

    global bot_instance, dp_instance
    exit_code = 0  # Код выхода (0 = успех, 1 = ошибка)

    try:
        logger.info("Запуск Telegram бота для планирования смен...")
        
        # #region agent log
        debug_log("debug-session", "startup", "A", "main.py:111", "Startup begin", {
            "has_bot_token": bool(settings.BOT_TOKEN),
            "bot_token_length": len(settings.BOT_TOKEN) if settings.BOT_TOKEN else 0,
        })
        # #endregion

        # Создаем бота с настройками по умолчанию
        # #region agent log
        debug_log("debug-session", "startup", "B", "main.py:114", "Before Bot creation", {})
        # #endregion
        bot_instance = Bot(
            token=settings.BOT_TOKEN,
            parse_mode=ParseMode.HTML,
        )
        # #region agent log
        debug_log("debug-session", "startup", "B", "main.py:120", "After Bot creation", {
            "bot_id": bot_instance.id if hasattr(bot_instance, "id") else None,
        })
        # #endregion

        # Настройка Redis для FSM
        from redis.asyncio import Redis
        from aiogram.fsm.storage.redis import RedisStorage

        # #region agent log
        debug_log("debug-session", "startup", "C", "main.py:125", "Before Redis connection", {
            "redis_host": settings.REDIS_HOST,
            "redis_port": settings.REDIS_PORT,
            "has_redis_password": bool(settings.REDIS_PASSWORD),
        })
        # #endregion
        redis = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=settings.REDIS_DB,
            decode_responses=True,
        )
        # #region agent log
        debug_log("debug-session", "startup", "C", "main.py:135", "After Redis creation", {})
        # #endregion

        storage = RedisStorage(redis=redis)

        # Создаем диспетчер с storage
        # #region agent log
        debug_log("debug-session", "startup", "D", "main.py:140", "Before Dispatcher creation", {})
        # #endregion
        dp_instance = Dispatcher(storage=storage)
        # #region agent log
        debug_log("debug-session", "startup", "D", "main.py:143", "After Dispatcher creation", {})
        # #endregion

        # #region agent log
        debug_log("debug-session", "run1", "A", "main.py:114", "Before setup_bot - checking scheduler state", {
            "has_scheduler": "scheduler_service" in dp_instance.workflow_data if dp_instance else False,
        })
        # #endregion
        
        # Настраиваем бота (middlewares, роутеры, сервисы)
        # #region agent log
        debug_log("debug-session", "startup", "E", "main.py:150", "Before setup_bot", {})
        # #endregion
        await setup_bot(bot_instance, dp_instance, redis)
        # #region agent log
        debug_log("debug-session", "startup", "E", "main.py:153", "After setup_bot", {})
        # #endregion

        # #region agent log
        debug_log("debug-session", "run1", "A", "main.py:118", "After setup_bot - checking scheduler state", {
            "has_scheduler": "scheduler_service" in dp_instance.workflow_data if dp_instance else False,
            "scheduler_running": dp_instance.workflow_data.get("scheduler_service").scheduler.running if dp_instance and "scheduler_service" in dp_instance.workflow_data else False,
        })
        # #endregion

        # Проверяем подключение к Telegram API перед запуском поллинга
        logger.info("Проверка подключения к Telegram API...")
        # #region agent log
        debug_log("debug-session", "startup", "F", "main.py:160", "Before connection check", {})
        # #endregion
        connection_result = await check_telegram_connection(bot_instance, max_retries=5, retry_delay=5.0)
        # #region agent log
        debug_log("debug-session", "startup", "F", "main.py:163", "After connection check", {
            "connection_result": connection_result,
        })
        # #endregion
        if not connection_result:
            logger.error(
                "Не удалось установить подключение к Telegram API. "
                "Проверьте интернет-соединение и доступность api.telegram.org"
            )
            # #region agent log
            debug_log("debug-session", "run1", "B", "main.py:153", "Connection failed - before raise", {
                "has_scheduler": "scheduler_service" in dp_instance.workflow_data if dp_instance else False,
                "scheduler_running": dp_instance.workflow_data.get("scheduler_service").scheduler.running if dp_instance and "scheduler_service" in dp_instance.workflow_data else False,
            })
            # #endregion
            raise ConnectionError("Не удалось подключиться к Telegram API")

        # Инициализация планировщика ПОСЛЕ успешной проверки подключения
        # #region agent log
        debug_log("debug-session", "post-fix", "A", "main.py:164", "Before init_scheduler after connection check", {
            "has_scheduler": "scheduler_service" in dp_instance.workflow_data if dp_instance else False,
        })
        # #endregion
        
        from src.bot import init_scheduler
        await init_scheduler(bot_instance, dp_instance)
        
        # #region agent log
        debug_log("debug-session", "post-fix", "A", "main.py:170", "After init_scheduler after connection check", {
            "has_scheduler": "scheduler_service" in dp_instance.workflow_data if dp_instance else False,
            "scheduler_running": dp_instance.workflow_data.get("scheduler_service").scheduler.running if dp_instance and "scheduler_service" in dp_instance.workflow_data else False,
        })
        # #endregion

        # Настройка обработки сигналов для корректной остановки
        def signal_handler(signum, frame):
            """Обработчик сигналов для корректной остановки."""
            logger.info(f"Получен сигнал {signum}, начинаем остановку...")
            shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # Docker stop, systemd stop

        # Запускаем поллинг с поддержкой graceful shutdown
        # Параметры поллинга:
        # - handle_as_tasks=True: обработка обновлений в отдельных задачах для параллелизма
        # - close_bot_session=True: автоматическое закрытие сессии при остановке
        # - request_timeout: таймаут для запросов (по умолчанию 5 секунд)
        # - allowed_updates: разрешенные типы обновлений (None = все)
        logger.info("Запуск поллинга обновлений от Telegram API...")
        await dp_instance.start_polling(
            bot_instance,
            handle_as_tasks=True,
            close_bot_session=True,
            # Увеличиваем таймаут для более устойчивой работы при сетевых проблемах
            request_timeout=10.0,
        )

    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания (Ctrl+C)")
    except ConnectionError as e:
        # #region agent log
        debug_log("debug-session", "run1", "B", "main.py:209", "ConnectionError caught - checking cleanup", {
            "has_scheduler": "scheduler_service" in dp_instance.workflow_data if dp_instance else False,
            "scheduler_running": dp_instance.workflow_data.get("scheduler_service").scheduler.running if dp_instance and "scheduler_service" in dp_instance.workflow_data else False,
            "bot_has_session": hasattr(bot_instance, "session") if bot_instance else False,
        })
        # #endregion
        logger.error("Ошибка подключения: %s", e)
        logger.info(
            "Возможные причины:\n"
            "  1. Проблемы с интернет-соединением\n"
            "  2. Блокировка доступа к api.telegram.org\n"
            "  3. Временные проблемы на стороне Telegram API\n"
            "Попробуйте запустить бота позже или проверьте настройки сети."
        )
        exit_code = 1
    except TelegramNetworkError as e:
        # #region agent log
        debug_log("debug-session", "error", "I", "main.py:TelegramNetworkError", "TelegramNetworkError caught", {
            "error_msg": str(e)[:200],
            "error_type": type(e).__name__,
        })
        # #endregion
        logger.error("Ошибка сети Telegram: %s", e)
        logger.info(
            "Не удалось подключиться к Telegram API. "
            "Проверьте интернет-соединение и попробуйте запустить бота позже."
        )
        exit_code = 1
    except Exception as e:
        # #region agent log
        debug_log("debug-session", "error", "J", "main.py:Exception", "Unexpected exception caught", {
            "error_type": type(e).__name__,
            "error_msg": str(e)[:200],
        })
        # #endregion
        logger.error("Не удалось запустить бота: %s", e, exc_info=True)
        exit_code = 1
    else:
        exit_code = 0
    finally:
        logger.info("Завершение работы бота...")
        
        # #region agent log
        debug_log("debug-session", "post-fix", "B", "main.py:237", "Finally block entered", {
            "has_scheduler": "scheduler_service" in dp_instance.workflow_data if dp_instance else False,
            "scheduler_running": dp_instance.workflow_data.get("scheduler_service").scheduler.running if dp_instance and "scheduler_service" in dp_instance.workflow_data else False,
            "bot_has_session": hasattr(bot_instance, "session") if bot_instance else False,
        })
        # #endregion
        
        # Останавливаем планировщик, если он был запущен
        if dp_instance and "scheduler_service" in dp_instance.workflow_data:
            try:
                # #region agent log
                debug_log("debug-session", "post-fix", "B", "main.py:247", "Stopping scheduler", {
                    "scheduler_running": dp_instance.workflow_data["scheduler_service"].scheduler.running,
                })
                # #endregion
                await dp_instance.workflow_data["scheduler_service"].stop()  # type: ignore[index]
                logger.info("Планировщик остановлен")
            except Exception as e:
                logger.error("Ошибка при остановке планировщика: %s", e)
        
        # Закрываем сессию бота
        if bot_instance:
            try:
                # Проверяем, есть ли сессия (она может быть создана лениво)
                if hasattr(bot_instance, "session"):
                    # #region agent log
                    debug_log("debug-session", "post-fix", "C", "main.py:263", "Closing bot session", {
                        "session_type": str(type(bot_instance.session)),
                    })
                    # #endregion
                    # AiohttpSession не имеет атрибута 'closed', просто вызываем close()
                    await bot_instance.session.close()
                    logger.info("Сессия бота закрыта")
                else:
                    logger.debug("Сессия бота еще не создана")
            except Exception as e:
                logger.error("Ошибка при закрытии сессии бота: %s", e, exc_info=True)
        
        # Закрываем Redis соединение
        if dp_instance and "redis" in dp_instance.workflow_data:
            try:
                await dp_instance.workflow_data["redis"].aclose()  # type: ignore[index]
                logger.info("Redis соединение закрыто")
            except Exception as e:
                logger.error("Ошибка при закрытии Redis соединения: %s", e)
        
        # #region agent log
        debug_log("debug-session", "post-fix", "C", "main.py:277", "After cleanup - final state", {
            "bot_has_session": hasattr(bot_instance, "session") if bot_instance else False,
            "scheduler_running": dp_instance.workflow_data.get("scheduler_service").scheduler.running if dp_instance and "scheduler_service" in dp_instance.workflow_data else False,
        })
        # #endregion
        
        logger.info("Бот остановлен")
        
        # Вызываем sys.exit только после завершения всех операций в finally
        if exit_code != 0:
            sys.exit(exit_code)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Бот остановлен пользователем")
    except Exception as e:
        logging.getLogger(__name__).error("Критическая ошибка: %s", e, exc_info=True)
        sys.exit(1)
