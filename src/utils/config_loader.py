"""
Загрузчик конфигурации для AI-куратора.

Загружает и валидирует финальную конфигурацию из delivery_curator_config.json.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)

# Путь к финальной конфигурации
CONFIG_PATH = Path(__file__).parent.parent / "ai" / "delivery_curator_config.json"

# Кэш конфигурации (загружается один раз при старте)
_config_cache: Optional[Dict[str, Any]] = None


def load_config() -> Dict[str, Any]:
    """
    Загрузить финальную конфигурацию AI-куратора.
    
    Returns:
        Словарь с конфигурацией
        
    Raises:
        FileNotFoundError: Если файл конфигурации не найден
        json.JSONDecodeError: Если файл содержит невалидный JSON
    """
    global _config_cache
    
    if _config_cache is not None:
        return _config_cache
    
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            _config_cache = json.load(f)
        logger.info("Конфигурация AI-куратора загружена успешно")
        return _config_cache
    except FileNotFoundError:
        logger.error("Файл конфигурации не найден: %s", CONFIG_PATH)
        raise
    except json.JSONDecodeError as e:
        logger.error("Ошибка парсинга JSON конфигурации: %s", e)
        raise


def get_must_match_cases() -> List[Dict[str, Any]]:
    """
    Получить список must-match кейсов из конфигурации.
    
    Returns:
        Список must-match кейсов
    """
    config = load_config()
    must_match = config.get("must_match_cases", {})
    return must_match.get("cases", [])


def check_must_match_case(question: str) -> Optional[Dict[str, Any]]:
    """
    Проверить, совпадает ли вопрос с must-match кейсом.
    
    Args:
        question: Вопрос пользователя
        
    Returns:
        Найденный must-match кейс или None
    """
    question_lower = question.lower()
    must_match_cases = get_must_match_cases()
    
    for case in must_match_cases:
        triggers = case.get("trigger", [])
        # Проверяем, содержатся ли все триггеры в вопросе
        if all(trigger.lower() in question_lower for trigger in triggers):
            return case
    
    return None


def get_golden_set() -> List[Dict[str, Any]]:
    """
    Получить golden set из конфигурации.
    
    Returns:
        Список эталонных вопросов
    """
    config = load_config()
    return config.get("golden_set", [])


def get_confidence_thresholds() -> Dict[str, float]:
    """
    Получить пороги confidence из конфигурации.
    
    Returns:
        Словарь с порогами (auto_answer, clarification_required, route_to_curator)
    """
    config = load_config()
    routing = config.get("confidence_routing", {})
    thresholds = routing.get("confidence_score", {}).get("thresholds", {})
    return {
        "auto_answer": thresholds.get("auto_answer", 0.8),
        "clarification_required": thresholds.get("clarification_required", 0.6),
        "route_to_curator": thresholds.get("route_to_curator", 0.0),
    }


def get_mandatory_escalation_triggers() -> List[str]:
    """
    Получить список обязательных триггеров эскалации.
    
    Returns:
        Список триггеров эскалации
    """
    config = load_config()
    routing = config.get("confidence_routing", {})
    return routing.get("mandatory_escalation", [])


def get_escalation_message() -> str:
    """
    Получить сообщение об эскалации из конфигурации.
    
    Returns:
        Текст сообщения об эскалации
    """
    config = load_config()
    routing = config.get("confidence_routing", {})
    return routing.get("escalation_message", "В базе знаний нет однозначного правила. Рекомендуется обратиться к куратору.")


def get_response_structure() -> Dict[str, Any]:
    """
    Получить структуру ответа из конфигурации.
    
    Returns:
        Словарь с обязательными и условными блоками ответа
    """
    config = load_config()
    return config.get("response_structure", {})


def get_tags() -> List[Dict[str, Any]]:
    """
    Получить список тегов из конфигурации.
    
    Returns:
        Список тегов с описаниями
    """
    config = load_config()
    knowledge_base = config.get("knowledge_base", {})
    return knowledge_base.get("tags", [])


def get_knowledge_base_rules() -> List[Dict[str, Any]]:
    """
    Получить правила из базы знаний.
    
    Returns:
        Список правил из базы знаний
    """
    config = load_config()
    knowledge_base = config.get("knowledge_base", {})
    return knowledge_base.get("rules", [])


def get_training_cases() -> List[Dict[str, Any]]:
    """
    Получить обучающие кейсы из конфигурации.
    
    Returns:
        Список обучающих кейсов
    """
    config = load_config()
    return config.get("training_cases", [])


def get_delivery_codex() -> Dict[str, Any]:
    """
    Получить кодекс доставки из конфигурации.
    
    Returns:
        Словарь с кодексом доставки
    """
    config = load_config()
    return config.get("delivery_codex", {})


def get_situation_tag_matrix() -> List[Dict[str, Any]]:
    """
    Получить матрицу ситуаций и тегов из конфигурации.
    
    Returns:
        Список соответствий ситуаций и тегов
    """
    config = load_config()
    return config.get("situation_tag_matrix", [])


def get_response_validator() -> Dict[str, Any]:
    """
    Получить правила валидации ответов из конфигурации.
    
    Returns:
        Словарь с правилами валидации
    """
    config = load_config()
    return config.get("response_validator", {})


def get_bot_restrictions() -> List[str]:
    """
    Получить список ограничений для бота из конфигурации.
    
    Returns:
        Список ограничений
    """
    config = load_config()
    return config.get("bot_restrictions", [])


def get_mandatory_escalation_triggers_detailed() -> List[Dict[str, Any]]:
    """
    Получить детальный список триггеров эскалации из конфигурации.
    
    Returns:
        Список триггеров эскалации с описаниями
    """
    config = load_config()
    return config.get("mandatory_escalation_triggers", [])


def get_delivery_codex_bot_version() -> Dict[str, Any]:
    """
    Получить версию кодекса доставки для бота из конфигурации.
    
    Returns:
        Словарь с версией кодекса для бота
    """
    config = load_config()
    return config.get("delivery_codex_bot_version", {})


def get_courier_rules() -> List[Dict[str, Any]]:
    """
    Получить правила курьера из конфигурации.
    
    Returns:
        Список правил курьера (CR_001-CR_004)
    """
    config = load_config()
    return config.get("courier_rules", [])


def get_no_contact_and_return_policy() -> List[Dict[str, Any]]:
    """
    Получить политику недозвона и возврата из конфигурации.
    
    Returns:
        Список правил недозвона и возврата (NR_001-NR_004)
    """
    config = load_config()
    return config.get("no_contact_and_return_policy", [])


def get_temperature_policy() -> Dict[str, Any]:
    """
    Получить политику температурного режима из конфигурации.
    
    Returns:
        Словарь с правилами температурного режима
    """
    config = load_config()
    return config.get("temperature_policy", {})


def get_mandatory_escalation_cases() -> List[str]:
    """
    Получить список обязательных случаев эскалации по Кодексу.
    
    Returns:
        Список случаев обязательной эскалации
    """
    config = load_config()
    return config.get("mandatory_escalation_cases", [])


def get_communication_ethics_policy() -> Dict[str, Any]:
    """
    Получить политику этики общения из конфигурации.
    
    Returns:
        Словарь с политикой этики общения
    """
    config = load_config()
    return config.get("communication_ethics_policy", {})


def get_communication_rules() -> List[Dict[str, Any]]:
    """
    Получить правила общения из конфигурации.
    
    Returns:
        Список правил общения (COM_001-COM_004)
    """
    config = load_config()
    return config.get("communication_rules", [])


def get_bot_communication_behavior() -> Dict[str, Any]:
    """
    Получить правила поведения бота при общении из конфигурации.
    
    Returns:
        Словарь с правилами поведения (must и must_not)
    """
    config = load_config()
    return config.get("bot_communication_behavior", {})


def get_communication_escalation() -> List[Dict[str, Any]]:
    """
    Получить правила эскалации по коммуникации из конфигурации.
    
    Returns:
        Список условий эскалации по коммуникации
    """
    config = load_config()
    return config.get("communication_escalation", [])


def get_payment_policy() -> Dict[str, Any]:
    """
    Получить политику оплаты из конфигурации.
    
    Returns:
        Словарь с политикой оплаты
    """
    config = load_config()
    return config.get("payment_policy", {})


def get_payment_basic_rules() -> List[Dict[str, Any]]:
    """
    Получить базовые правила оплаты из конфигурации.
    
    Returns:
        Список базовых правил оплаты (PAY_001, PAY_002)
    """
    config = load_config()
    return config.get("payment_basic_rules", [])


def get_terminal_payment() -> Dict[str, Any]:
    """
    Получить правила оплаты по терминалу из конфигурации.
    
    Returns:
        Словарь с шагами оплаты по терминалу
    """
    config = load_config()
    return config.get("terminal_payment", {})


def get_mixed_payment_policy() -> List[Dict[str, Any]]:
    """
    Получить политику смешанных типов оплаты из конфигурации.
    
    Returns:
        Список правил смешанной оплаты (PAY_MIX_001-PAY_MIX_003)
    """
    config = load_config()
    return config.get("mixed_payment_policy", [])


def get_terminal_restrictions() -> List[Dict[str, Any]]:
    """
    Получить ограничения по типу терминала из конфигурации.
    
    Returns:
        Список ограничений по типу терминала
    """
    config = load_config()
    return config.get("terminal_restrictions", [])


def get_terminal_refund_policy() -> List[Dict[str, Any]]:
    """
    Получить политику возвратов по терминалу из конфигурации.
    
    Returns:
        Список правил возвратов (REF_001-REF_003)
    """
    config = load_config()
    return config.get("terminal_refund_policy", [])


def get_bot_payment_restrictions() -> List[str]:
    """
    Получить ограничения для бота по финансам из конфигурации.
    
    Returns:
        Список ограничений для бота по оплате
    """
    config = load_config()
    return config.get("bot_payment_restrictions", [])


def get_payment_hyperlink_policy() -> Dict[str, Any]:
    """
    Получить политику оплаты по гиперссылке из конфигурации.
    
    Returns:
        Словарь с политикой оплаты по гиперссылке
    """
    config = load_config()
    return config.get("payment_hyperlink_policy", {})


def get_hyperlink_basic_rules() -> List[Dict[str, Any]]:
    """
    Получить базовые правила оплаты по гиперссылке из конфигурации.
    
    Returns:
        Список базовых правил (HL_001-HL_003)
    """
    config = load_config()
    return config.get("hyperlink_basic_rules", [])


def get_hyperlink_courier_behavior() -> List[Dict[str, Any]]:
    """
    Получить правила поведения курьера при оплате по гиперссылке из конфигурации.
    
    Returns:
        Список правил поведения курьера
    """
    config = load_config()
    return config.get("hyperlink_courier_behavior", [])


def get_hyperlink_order_closing() -> Dict[str, Any]:
    """
    Получить правила закрытия заказа при оплате по гиперссылке из конфигурации.
    
    Returns:
        Словарь с правилами закрытия заказа
    """
    config = load_config()
    return config.get("hyperlink_order_closing", {})


def get_hyperlink_force_close() -> Dict[str, Any]:
    """
    Получить правила принудительного закрытия заказа из конфигурации.
    
    Returns:
        Словарь с правилами принудительного закрытия
    """
    config = load_config()
    return config.get("hyperlink_force_close", {})


def get_hyperlink_restrictions() -> List[Dict[str, Any]]:
    """
    Получить ограничения по оплате по гиперссылке из конфигурации.
    
    Returns:
        Список ограничений (HL_RESTR_001-HL_RESTR_003)
    """
    config = load_config()
    return config.get("hyperlink_restrictions", [])


def get_confidence_routing_hyperlink() -> Dict[str, Any]:
    """
    Получить правила confidence routing для оплаты по гиперссылке из конфигурации.
    
    Returns:
        Словарь с правилами confidence routing
    """
    config = load_config()
    return config.get("confidence_routing_hyperlink", {})


def get_explainability_log_schema() -> Dict[str, Any]:
    """
    Получить схему логов объяснимости из конфигурации.
    
    Returns:
        Словарь со схемой логов объяснимости
    """
    config = load_config()
    return config.get("explainability_log_schema", {})


def get_golden_set_extended() -> Dict[str, Any]:
    """
    Получить метаданные расширенного golden set из конфигурации.
    
    Returns:
        Словарь с метаданными расширенного golden set
    """
    config = load_config()
    return config.get("golden_set_extended", {})


def get_autotest_schema() -> Dict[str, Any]:
    """
    Получить схему автотестов из конфигурации.
    
    Returns:
        Словарь со схемой автотестов
    """
    config = load_config()
    return config.get("autotest_schema", {})


def get_returns_policy_v1_1() -> Dict[str, Any]:
    """
    Получить политику возвратов v1.1 (P0) из конфигурации.
    
    Returns:
        Словарь с политикой возвратов v1.1
    """
    config = load_config()
    return config.get("returns_policy_v1_1", {})


def get_must_match_returns() -> List[Dict[str, Any]]:
    """
    Получить must-match кейсы по возвратам из конфигурации.
    
    Returns:
        Список must-match кейсов по возвратам (MM_RET_P0_001, MM_RET_P0_002)
    """
    config = load_config()
    return config.get("must_match_returns", [])


def reload_config() -> None:
    """
    Перезагрузить конфигурацию (очистить кэш).
    
    Полезно при разработке или обновлении конфигурации без перезапуска бота.
    """
    global _config_cache
    _config_cache = None
    logger.info("Кэш конфигурации очищен")


def validate_config() -> Tuple[bool, List[str]]:
    """
    Валидировать структуру конфигурации.
    
    Returns:
        Кортеж (валидна ли конфигурация, список ошибок)
    """
    errors = []
    
    try:
        config = load_config()
    except Exception as e:
        return False, [f"Ошибка загрузки конфигурации: {e}"]
    
    # Проверяем обязательные поля
    required_sections = [
        "meta",
        "knowledge_base",
        "must_match_cases",
        "confidence_routing",
        "golden_set",
    ]
    
    for section in required_sections:
        if section not in config:
            errors.append(f"Отсутствует обязательная секция: {section}")
    
    # Проверяем структуру confidence_routing
    if "confidence_routing" in config:
        routing = config["confidence_routing"]
        if "confidence_score" not in routing:
            errors.append("Отсутствует confidence_score в confidence_routing")
        else:
            score_config = routing["confidence_score"]
            if "thresholds" not in score_config:
                errors.append("Отсутствует thresholds в confidence_score")
    
    # Проверяем must_match_cases
    if "must_match_cases" in config:
        must_match = config["must_match_cases"]
        if "cases" not in must_match:
            errors.append("Отсутствует cases в must_match_cases")
        else:
            for idx, case in enumerate(must_match["cases"]):
                if "id" not in case:
                    errors.append(f"must_match_cases.cases[{idx}]: отсутствует id")
                if "trigger" not in case:
                    errors.append(f"must_match_cases.cases[{idx}]: отсутствует trigger")
                if "main_tag" not in case:
                    errors.append(f"must_match_cases.cases[{idx}]: отсутствует main_tag")
    
    return len(errors) == 0, errors
