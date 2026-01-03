"""
Загрузчик Core Policy JSON для новой архитектуры.

Загружает данные из core_policy.json (единый источник истины).
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Путь к Core Policy JSON
CORE_POLICY_PATH = Path(__file__).parent.parent / "ai" / "core_policy.json"

# Кэш конфигурации
_core_policy_cache: Optional[Dict[str, Any]] = None


def load_core_policy() -> Dict[str, Any]:
    """
    Загрузить Core Policy JSON.
    
    Returns:
        Словарь с Core Policy
    
    Raises:
        FileNotFoundError: Если файл не найден
        json.JSONDecodeError: Если файл содержит невалидный JSON
    """
    global _core_policy_cache
    
    if _core_policy_cache is not None:
        return _core_policy_cache
    
    try:
        with open(CORE_POLICY_PATH, "r", encoding="utf-8") as f:
            _core_policy_cache = json.load(f)
        logger.info("Core Policy JSON загружен успешно")
        return _core_policy_cache
    except FileNotFoundError:
        logger.error("Файл Core Policy JSON не найден: %s", CORE_POLICY_PATH)
        raise
    except json.JSONDecodeError as e:
        logger.error("Ошибка парсинга Core Policy JSON: %s", e)
        raise


def get_core_must_match_cases() -> List[Dict[str, Any]]:
    """
    Получить must-match кейсы из Core Policy JSON.
    
    Returns:
        Список must-match кейсов с приоритетами
    """
    policy = load_core_policy()
    must_match = policy.get("must_match_cases", {})
    return must_match.get("cases", [])


def get_core_golden_set() -> List[Dict[str, Any]]:
    """
    Получить Golden Set из Core Policy JSON.
    
    Returns:
        Список кейсов Golden Set
    """
    policy = load_core_policy()
    golden_set = policy.get("golden_set", {})
    return golden_set.get("cases", [])


def get_core_tags() -> List[Dict[str, Any]]:
    """
    Получить теги из Core Policy JSON.
    
    Returns:
        Список тегов
    """
    policy = load_core_policy()
    return policy.get("tags", [])


def get_core_rules() -> List[Dict[str, Any]]:
    """
    Получить правила из Core Policy JSON.
    
    Returns:
        Список правил
    """
    policy = load_core_policy()
    rules = policy.get("rules", {})
    return rules.get("items", [])


def get_core_confidence_routing() -> Dict[str, Any]:
    """
    Получить настройки confidence routing из Core Policy JSON.
    
    Returns:
        Словарь с настройками confidence routing
    """
    policy = load_core_policy()
    return policy.get("confidence_routing", {})


def reload_core_policy() -> None:
    """
    Перезагрузить Core Policy JSON (очистить кэш).
    
    Полезно при разработке или обновлении конфигурации без перезапуска бота.
    """
    global _core_policy_cache
    _core_policy_cache = None
    logger.info("Кэш Core Policy JSON очищен")
