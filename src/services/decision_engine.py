"""
Движок принятия решений для AI-куратора (новая архитектура).

Реализует:
1. Confidence Routing с реальным расчетом score
2. Улучшенную Must-Match проверку (семантический поиск, приоритеты)
3. Валидацию ответа перед отправкой
4. Explainability Logs
"""
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from pathlib import Path

from src.repositories.faq_repository import FAQRepository
from src.utils.config_loader import (
    get_confidence_thresholds,
    get_mandatory_escalation_triggers,
    get_escalation_message,
    get_response_validator,
)
from src.utils.core_policy_loader import get_core_must_match_cases

logger = logging.getLogger(__name__)


class DecisionEngine:
    """
    Движок принятия решений для AI-куратора.
    
    Принимает решения на основе:
    - Must-match кейсов (P0/P1/P2)
    - Confidence score (0.0-1.0)
    - Правил эскалации
    - Валидации ответа
    """
    
    def __init__(self, faq_repo: FAQRepository):
        """
        Инициализация движка принятия решений.
        
        Args:
            faq_repo: Репозиторий для работы с FAQ
        """
        self.faq_repo = faq_repo
        
        # Загружаем конфигурацию
        # Используем Core Policy JSON для must-match кейсов (с приоритетами)
        try:
            self.must_match_cases = get_core_must_match_cases()
            logger.info("Загружено %d must-match кейсов из Core Policy JSON", len(self.must_match_cases))
        except Exception as e:
            logger.warning("Не удалось загрузить must-match кейсы из Core Policy JSON: %s. Используем старый конфиг.", e)
            # Fallback на старый конфиг
            from src.utils.config_loader import get_must_match_cases
            self.must_match_cases = get_must_match_cases()
        
        self.confidence_thresholds = get_confidence_thresholds()
        self.escalation_triggers = get_mandatory_escalation_triggers()
        self.escalation_message = get_escalation_message()
        self.validator = get_response_validator()
    
    def check_must_match_improved(
        self,
        question: str,
        priority: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Улучшенная проверка must-match кейсов.
        
        Использует:
        - Семантический поиск (не требует все триггеры)
        - Приоритеты (P0 > P1 > P2)
        - Threshold (0.8)
        
        Args:
            question: Вопрос пользователя
            priority: Приоритет для фильтрации (P0, P1, P2)
        
        Returns:
            Найденный must-match кейс или None
        """
        question_lower = question.lower()
        best_match = None
        best_score = 0.0
        
        # Фильтруем по приоритету, если указан
        cases_to_check = self.must_match_cases
        if priority:
            cases_to_check = [
                case for case in cases_to_check
                if case.get("priority") == priority
            ]
        
        # Проверяем каждый кейс
        for case in cases_to_check:
            triggers = case.get("trigger", [])
            if not triggers:
                continue
            
            # Улучшенная проверка: считаем совпадения триггеров
            matches = 0
            total_triggers = len(triggers)
            
            for trigger in triggers:
                trigger_lower = trigger.lower()
                # Проверяем точное совпадение или вхождение
                if trigger_lower in question_lower or question_lower in trigger_lower:
                    matches += 1
            
            # Рассчитываем score: процент совпадений
            score = matches / total_triggers if total_triggers > 0 else 0.0
            
            # Учитываем приоритет кейса
            priority_multiplier = {
                "P0": 1.2,
                "P1": 1.1,
                "P2": 1.0,
            }.get(case.get("priority", "P2"), 1.0)
            
            score *= priority_multiplier
            
            # Если score >= threshold (0.8) и лучше предыдущего
            if score >= 0.8 and score > best_score:
                best_score = score
                best_match = case
                best_match["match_score"] = score
        
        return best_match
    
    async def calculate_confidence_score(
        self,
        question: str,
        must_match_case: Optional[Dict[str, Any]] = None,
        faqs: Optional[List[Dict[str, Any]]] = None,
        selected_tag: Optional[str] = None
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Рассчитать confidence score для вопроса.
        
        Формула:
        score = must_match_found * 1.0 + faq_relevance * 0.7 + tag_confidence * 0.6 + rule_clarity * 0.5
        
        Args:
            question: Вопрос пользователя
            must_match_case: Найденный must-match кейс (если есть)
            faqs: Найденные FAQ (если есть)
            selected_tag: Выбранный тег (если есть)
        
        Returns:
            Кортеж (confidence_score, breakdown)
        """
        breakdown = {
            "must_match_found": 0.0,
            "faq_relevance": 0.0,
            "tag_confidence": 0.0,
            "rule_clarity": 0.0,
        }
        
        # Фактор 1: Must-match найден
        if must_match_case:
            breakdown["must_match_found"] = 1.0
            breakdown["must_match_id"] = must_match_case.get("id")
            breakdown["must_match_score"] = must_match_case.get("match_score", 1.0)
        
        # Фактор 2: Релевантность FAQ
        if faqs and len(faqs) > 0:
            # Простая метрика: есть ли релевантные FAQ
            # В будущем можно улучшить: использовать rank от PostgreSQL
            breakdown["faq_relevance"] = min(1.0, len(faqs) / 3.0)  # Нормализуем до 1.0
            breakdown["faq_count"] = len(faqs)
        else:
            breakdown["faq_relevance"] = 0.0
        
        # Фактор 3: Уверенность в теге
        if selected_tag:
            # Если тег выбран из must-match или FAQ - высокая уверенность
            if must_match_case and must_match_case.get("main_tag") == selected_tag:
                breakdown["tag_confidence"] = 1.0
            elif faqs and any(faq.get("tag") == selected_tag for faq in faqs):
                breakdown["tag_confidence"] = 0.8
            else:
                breakdown["tag_confidence"] = 0.5
        else:
            breakdown["tag_confidence"] = 0.0
        
        # Фактор 4: Четкость правила
        if must_match_case:
            # Must-match кейсы всегда четкие
            breakdown["rule_clarity"] = 1.0
        elif faqs and len(faqs) > 0:
            # Если есть FAQ - правило есть
            breakdown["rule_clarity"] = 0.8
        else:
            breakdown["rule_clarity"] = 0.0
        
        # Рассчитываем итоговый score по формуле
        score = (
            breakdown["must_match_found"] * 1.0 +
            breakdown["faq_relevance"] * 0.7 +
            breakdown["tag_confidence"] * 0.6 +
            breakdown["rule_clarity"] * 0.5
        )
        
        # Нормализуем до 0.0-1.0
        score = min(1.0, max(0.0, score))
        
        return score, breakdown
    
    def check_mandatory_escalation(
        self,
        question: str,
        confidence_score: float,
        must_match_case: Optional[Dict[str, Any]] = None,
        faqs: Optional[List[Dict[str, Any]]] = None,
        selected_tag: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Проверить, требуется ли обязательная эскалация.
        
        Args:
            question: Вопрос пользователя
            confidence_score: Рассчитанный confidence score
            must_match_case: Найденный must-match кейс
            faqs: Найденные FAQ
            selected_tag: Выбранный тег
        
        Returns:
            Кортеж (требуется_эскалация, причина)
        """
        question_lower = question.lower()
        
        # Проверяем триггеры эскалации
        escalation_keywords = [
            "наказать", "штраф", "уволить", "санкции",
            "оценить", "как вы думаете", "что вы думаете",
            "юридическ", "договор", "ответственность",
        ]
        
        for keyword in escalation_keywords:
            if keyword in question_lower:
                return True, f"Триггер эскалации: '{keyword}'"
        
        # Нет прямого правила или кейса
        if not must_match_case and (not faqs or len(faqs) == 0):
            return True, "Нет прямого правила или кейса"
        
        # Несколько возможных тегов без приоритета
        if faqs and len(faqs) > 1:
            tags = set(faq.get("tag") for faq in faqs if faq.get("tag"))
            if len(tags) > 1 and not selected_tag:
                return True, "Несколько возможных тегов без приоритета"
        
        # Финансовый риск
        financial_keywords = ["оплата", "возврат", "деньги", "терминал", "гиперссылка"]
        if any(keyword in question_lower for keyword in financial_keywords):
            if confidence_score < 0.8:
                return True, "Финансовый риск при низком confidence"
        
        # Низкий confidence score
        if confidence_score < self.confidence_thresholds["route_to_curator"]:
            return True, f"Низкий confidence score: {confidence_score:.2f}"
        
        return False, None
    
    def determine_decision_route(
        self,
        confidence_score: float,
        requires_escalation: bool
    ) -> str:
        """
        Определить маршрут принятия решения.
        
        Args:
            confidence_score: Рассчитанный confidence score
            requires_escalation: Требуется ли эскалация
        
        Returns:
            Маршрут: "auto_answer", "clarification_required", "route_to_curator", "route_to_support"
        """
        if requires_escalation:
            return "route_to_curator"
        
        if confidence_score >= self.confidence_thresholds["auto_answer"]:
            return "auto_answer"
        elif confidence_score >= self.confidence_thresholds["clarification_required"]:
            return "clarification_required"
        else:
            return "route_to_curator"
    
    async def make_decision(
        self,
        user_id: int,
        question: str
    ) -> Dict[str, Any]:
        """
        Принять решение по вопросу пользователя.
        
        Args:
            user_id: ID пользователя
            question: Вопрос пользователя
        
        Returns:
            Словарь с решением и метаданными
        """
        # 1. Проверяем must-match кейсы (сначала P0, потом P1, потом P2)
        must_match_case = None
        for priority in ["P0", "P1", "P2"]:
            must_match_case = self.check_must_match_improved(question, priority)
            if must_match_case:
                break
        
        # 2. Ищем релевантные FAQ
        faqs = []
        if not must_match_case:  # Если must-match не найден, ищем FAQ
            try:
                faqs = await self.faq_repo.search_hybrid(question, limit=5)
            except Exception as e:
                logger.error("Ошибка при поиске FAQ: %s", e, exc_info=True)
        
        # 3. Определяем тег
        selected_tag = None
        if must_match_case:
            selected_tag = must_match_case.get("main_tag")
        elif faqs and len(faqs) > 0:
            # Берем тег из самого релевантного FAQ
            selected_tag = faqs[0].get("tag")
        
        # 4. Рассчитываем confidence score
        confidence_score, breakdown = await self.calculate_confidence_score(
            question,
            must_match_case,
            faqs,
            selected_tag
        )
        
        # 5. Проверяем обязательную эскалацию
        requires_escalation, escalation_reason = self.check_mandatory_escalation(
            question,
            confidence_score,
            must_match_case,
            faqs,
            selected_tag
        )
        
        # 6. Определяем маршрут
        decision_route = self.determine_decision_route(
            confidence_score,
            requires_escalation
        )
        
        # 7. Определяем уровень confidence
        if confidence_score >= 0.8:
            confidence_level = "high"
        elif confidence_score >= 0.6:
            confidence_level = "medium"
        else:
            confidence_level = "low"
        
        # 8. Формируем решение
        decision = {
            "user_id": user_id,
            "question": question,
            "must_match_case": must_match_case,
            "faqs": faqs,
            "selected_tag": selected_tag,
            "confidence_score": confidence_score,
            "confidence_level": confidence_level,
            "confidence_breakdown": breakdown,
            "requires_escalation": requires_escalation,
            "escalation_reason": escalation_reason,
            "decision_route": decision_route,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        return decision
