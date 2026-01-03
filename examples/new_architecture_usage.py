"""
Пример использования новой архитектуры AI-куратора.

Демонстрирует:
1. Использование DecisionEngine
2. Использование ResponseValidator
3. Использование ExplainabilityLogger
4. Использование NewCuratorService
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.decision_engine import DecisionEngine
from src.services.response_validator import ResponseValidator
from src.services.explainability_logger import ExplainabilityLogger
from src.services.new_curator_service import NewCuratorService
from src.repositories.faq_repository import FAQRepository
from src.utils.db_pool import get_db_pool


async def example_decision_engine():
    """Пример использования DecisionEngine."""
    print("=" * 70)
    print("📊 ПРИМЕР: DecisionEngine")
    print("=" * 70)
    
    # Создаем DecisionEngine
    pool = await get_db_pool()
    faq_repo = FAQRepository(pool)
    engine = DecisionEngine(faq_repo)
    
    # Тестовые вопросы
    test_questions = [
        "Яйца приехали разбитые, что делать?",
        "Курьер не дозвонился и оставил заказ у двери",
        "Можно ли оштрафовать курьера?",
    ]
    
    for question in test_questions:
        print(f"\n❓ Вопрос: {question}")
        
        decision = await engine.make_decision(user_id=1, question=question)
        
        print(f"  ✅ Решение:")
        print(f"     - Route: {decision['decision_route']}")
        print(f"     - Confidence: {decision['confidence_score']:.2f}")
        print(f"     - Level: {decision['confidence_level']}")
        print(f"     - Tag: {decision.get('selected_tag', 'None')}")
        print(f"     - Escalation: {decision.get('requires_escalation', False)}")
        
        if decision.get("must_match_case"):
            print(f"     - Must-match: {decision['must_match_case'].get('id')}")


def example_response_validator():
    """Пример использования ResponseValidator."""
    print("\n" + "=" * 70)
    print("📊 ПРИМЕР: ResponseValidator")
    print("=" * 70)
    
    validator = ResponseValidator()
    
    # Тестовые ответы
    test_responses = [
        {
            "text": """Суть ситуации: Яйца разбиты при доставке.
Правильное решение / тег: Неаккуратная доставка
Кто отвечает: Курьер
Почему: Повреждение возникло в процессе доставки.
Что делать сейчас: Зафиксировать обращение.""",
            "has_tag": True,
            "matched_source": {"type": "must_match_case", "id": "MM_001"}
        },
        {
            "text": "Короткий ответ без структуры",
            "has_tag": False,
            "matched_source": None
        }
    ]
    
    for i, response_data in enumerate(test_responses, 1):
        print(f"\n📝 Тест {i}:")
        print(f"   Текст: {response_data['text'][:50]}...")
        
        is_valid, errors, warnings = validator.validate(
            response_data["text"],
            has_tag=response_data["has_tag"],
            matched_source=response_data["matched_source"]
        )
        
        result = validator.format_validation_result(is_valid, errors, warnings)
        
        print(f"   ✅ Валиден: {result['valid']}")
        print(f"   ❌ Ошибок: {result['error_count']}")
        print(f"   ⚠️  Предупреждений: {result['warning_count']}")


def example_explainability_logger():
    """Пример использования ExplainabilityLogger."""
    print("\n" + "=" * 70)
    print("📊 ПРИМЕР: ExplainabilityLogger")
    print("=" * 70)
    
    log_dir = Path(__file__).parent.parent / "logs" / "explainability"
    logger = ExplainabilityLogger(log_dir)
    
    # Тестовое решение
    test_decision = {
        "decision_route": "auto_answer",
        "confidence_score": 0.95,
        "confidence_level": "high",
        "selected_tag": "Неаккуратная доставка",
        "must_match_case": {
            "id": "MM_001",
            "responsible": "Курьер"
        },
        "confidence_breakdown": {
            "must_match_found": 1.0,
            "faq_relevance": 0.8,
            "tag_confidence": 1.0,
            "rule_clarity": 1.0
        }
    }
    
    log_entry = logger.log_decision(
        user_id=123,
        user_query="Яйца приехали разбитые, что делать?",
        decision=test_decision,
        validation_result={"valid": True, "errors": [], "warnings": []}
    )
    
    print(f"✅ Лог создан:")
    print(f"   - Timestamp: {log_entry['timestamp']}")
    print(f"   - User ID: {log_entry['user_id']}")
    print(f"   - Route: {log_entry['decision_route']}")
    print(f"   - Confidence: {log_entry['confidence_score']}")
    print(f"   - Tag: {log_entry['selected_tag']}")
    print(f"   - Matched source: {log_entry['matched_source']}")


async def example_new_curator_service():
    """Пример использования NewCuratorService."""
    print("\n" + "=" * 70)
    print("📊 ПРИМЕР: NewCuratorService")
    print("=" * 70)
    
    pool = await get_db_pool()
    faq_repo = FAQRepository(pool)
    log_dir = Path(__file__).parent.parent / "logs" / "explainability"
    
    curator = NewCuratorService(faq_repo=faq_repo, log_dir=log_dir)
    
    # Тестовые вопросы
    test_questions = [
        "Яйца приехали разбитые, что делать?",
        "Курьер не дозвонился и оставил заказ у двери",
    ]
    
    for question in test_questions:
        print(f"\n❓ Вопрос: {question}")
        
        answer = await curator.get_answer(question, user_id=1)
        
        print(f"   ✅ Ответ ({len(answer)} символов):")
        print(f"   {answer[:200]}..." if len(answer) > 200 else f"   {answer}")


async def main():
    """Главная функция с примерами."""
    print("=" * 70)
    print("📚 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ НОВОЙ АРХИТЕКТУРЫ")
    print("=" * 70)
    
    try:
        # Пример 1: DecisionEngine
        await example_decision_engine()
        
        # Пример 2: ResponseValidator
        example_response_validator()
        
        # Пример 3: ExplainabilityLogger
        example_explainability_logger()
        
        # Пример 4: NewCuratorService
        await example_new_curator_service()
        
        print("\n" + "=" * 70)
        print("✅ ВСЕ ПРИМЕРЫ ВЫПОЛНЕНЫ")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
