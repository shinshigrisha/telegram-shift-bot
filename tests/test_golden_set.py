"""
Автотесты по Golden Set для AI-куратора.

Каждый Golden Case = тест.
Любой fail блокирует сборку.
"""
import pytest
import asyncio
from typing import Dict, Any, List

from src.services.decision_engine import DecisionEngine
from src.repositories.faq_repository import FAQRepository
from src.utils.db_pool import get_db_pool
from src.utils.config_loader import get_golden_set

# Все тесты асинхронные
pytestmark = pytest.mark.asyncio


class TestGoldenSet:
    """
    Тесты по Golden Set.
    
    Каждый кейс из golden_set проверяется:
    - Правильный decision_route
    - Правильный тег (если ожидается)
    - Правильная ответственность (если ожидается)
    - Валидная структура ответа
    """
    
    @pytest.fixture(scope="class")
    async def decision_engine(self):
        """Создать DecisionEngine для тестов."""
        pool = await get_db_pool()
        faq_repo = FAQRepository(pool)
        engine = DecisionEngine(faq_repo)
        return engine
    
    @pytest.fixture(scope="class")
    def golden_cases(self) -> List[Dict[str, Any]]:
        """Загрузить Golden Set из конфига."""
        return get_golden_set()
    
    @pytest.mark.asyncio
    async def test_golden_case_gs_001(self, decision_engine):
        """Тест GS_001: Яйца приехали разбитые, что делать?"""
        question = "Яйца приехали разбитые, что делать?"
        
        decision = await decision_engine.make_decision(
            user_id=1,
            question=question
        )
        
        # Проверяем ожидаемый маршрут
        assert decision["decision_route"] == "auto_answer", \
            f"Ожидался auto_answer, получен {decision['decision_route']}"
        
        # Проверяем тег
        assert decision["selected_tag"] == "Неаккуратная доставка", \
            f"Ожидался тег 'Неаккуратная доставка', получен '{decision['selected_tag']}'"
        
        # Проверяем confidence
        assert decision["confidence_score"] >= 0.8, \
            f"Ожидался confidence >= 0.8, получен {decision['confidence_score']}"
    
    @pytest.mark.asyncio
    async def test_golden_case_gs_002(self, decision_engine):
        """Тест GS_002: Курьер не дозвонился и оставил заказ у двери"""
        question = "Курьер не дозвонился и оставил заказ у двери"
        
        decision = await decision_engine.make_decision(
            user_id=1,
            question=question
        )
        
        assert decision["decision_route"] == "auto_answer"
        assert decision["selected_tag"] == "Оставил заказ на адресе / не вернул на ТТ"
        assert decision["confidence_score"] >= 0.8
    
    @pytest.mark.asyncio
    async def test_golden_case_gs_003(self, decision_engine):
        """Тест GS_003: Курьер попросил меня выйти за заказом к машине"""
        question = "Курьер попросил меня выйти за заказом к машине"
        
        decision = await decision_engine.make_decision(
            user_id=1,
            question=question
        )
        
        assert decision["decision_route"] == "auto_answer"
        assert decision["selected_tag"] == "Отказ курьера доставлять до двери"
        assert decision["confidence_score"] >= 0.8
    
    @pytest.mark.asyncio
    async def test_golden_case_gs_004(self, decision_engine):
        """Тест GS_004: Курьер грубо разговаривал"""
        question = "Курьер грубо разговаривал"
        
        decision = await decision_engine.make_decision(
            user_id=1,
            question=question
        )
        
        assert decision["decision_route"] == "auto_answer"
        assert decision["selected_tag"] == "Коммуникация с покупателем"
        assert decision["confidence_score"] >= 0.8
    
    @pytest.mark.asyncio
    async def test_golden_case_gs_005(self, decision_engine):
        """Тест GS_005: Заказ задержался, но непонятно почему (route_to_curator)"""
        question = "Заказ задержался, но непонятно почему"
        
        decision = await decision_engine.make_decision(
            user_id=1,
            question=question
        )
        
        # Должен быть route_to_curator из-за недостатка данных
        assert decision["decision_route"] == "route_to_curator", \
            f"Ожидался route_to_curator, получен {decision['decision_route']}"
        
        # Confidence должен быть низким
        assert decision["confidence_score"] < 0.6, \
            f"Ожидался confidence < 0.6, получен {decision['confidence_score']}"
    
    @pytest.mark.asyncio
    async def test_golden_case_gs_006(self, decision_engine):
        """Тест GS_006: Можно ли оштрафовать курьера за опоздание? (route_to_curator)"""
        question = "Можно ли оштрафовать курьера за опоздание?"
        
        decision = await decision_engine.make_decision(
            user_id=1,
            question=question
        )
        
        # Должен быть route_to_curator из-за запроса о дисциплинарных мерах
        assert decision["decision_route"] == "route_to_curator"
        assert decision["requires_escalation"] is True
    
    @pytest.mark.asyncio
    async def test_all_golden_cases(self, decision_engine, golden_cases):
        """
        Тест всех кейсов из Golden Set.
        
        Параметризованный тест для всех кейсов.
        """
        for case in golden_cases:
            case_id = case.get("id")
            question = case.get("question")
            expected_route = case.get("expected_route")
            expected_tag = case.get("expected_tag")
            expected_responsible = case.get("expected_responsible")
            
            if not question:
                continue
            
            decision = await decision_engine.make_decision(
                user_id=1,
                question=question
            )
            
            # Проверяем маршрут
            if expected_route:
                assert decision["decision_route"] == expected_route, \
                    f"Кейс {case_id}: ожидался {expected_route}, получен {decision['decision_route']}"
            
            # Проверяем тег
            if expected_tag:
                assert decision["selected_tag"] == expected_tag, \
                    f"Кейс {case_id}: ожидался тег '{expected_tag}', получен '{decision['selected_tag']}'"
            
            # Проверяем ответственность (если есть must-match кейс)
            if expected_responsible and decision.get("must_match_case"):
                assert decision["must_match_case"].get("responsible") == expected_responsible, \
                    f"Кейс {case_id}: ожидалась ответственность '{expected_responsible}'"
            
            # Проверяем, что решение логируется
            assert "confidence_score" in decision
            assert "decision_route" in decision
            assert "timestamp" in decision
