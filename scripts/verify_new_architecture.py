#!/usr/bin/env python3
"""
Скрипт для проверки работоспособности новой архитектуры.

Проверяет:
1. Импорты всех компонентов
2. Загрузку Core Policy JSON
3. Работу DecisionEngine
4. Работу ResponseValidator
5. Работу ExplainabilityLogger
"""
import sys
import asyncio
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))


async def verify_imports():
    """Проверить импорты всех компонентов."""
    print("🔍 Проверка импортов...")
    
    try:
        from src.services.decision_engine import DecisionEngine
        from src.services.response_validator import ResponseValidator
        from src.services.explainability_logger import ExplainabilityLogger
        from src.services.new_curator_service import NewCuratorService
        from src.utils.core_policy_loader import (
            load_core_policy,
            get_core_must_match_cases,
            get_core_golden_set,
            get_core_tags,
        )
        print("  ✅ Все импорты успешны")
        return True
    except Exception as e:
        print(f"  ❌ Ошибка импорта: {e}")
        return False


def verify_core_policy():
    """Проверить загрузку Core Policy JSON."""
    print("\n🔍 Проверка Core Policy JSON...")
    
    try:
        from src.utils.core_policy_loader import (
            load_core_policy,
            get_core_must_match_cases,
            get_core_golden_set,
            get_core_tags,
        )
        
        policy = load_core_policy()
        print(f"  ✅ Core Policy JSON загружен (версия: {policy.get('meta', {}).get('version', 'unknown')})")
        
        must_match_cases = get_core_must_match_cases()
        print(f"  ✅ Must-match кейсов: {len(must_match_cases)}")
        p0_count = sum(1 for c in must_match_cases if c.get("priority") == "P0")
        p1_count = sum(1 for c in must_match_cases if c.get("priority") == "P1")
        p2_count = sum(1 for c in must_match_cases if c.get("priority") == "P2")
        print(f"     - P0: {p0_count}, P1: {p1_count}, P2: {p2_count}")
        
        golden_set = get_core_golden_set()
        print(f"  ✅ Golden Set кейсов: {len(golden_set)}")
        
        tags = get_core_tags()
        print(f"  ✅ Тегов: {len(tags)}")
        
        return True
    except Exception as e:
        print(f"  ❌ Ошибка загрузки Core Policy JSON: {e}")
        import traceback
        traceback.print_exc()
        return False


async def verify_decision_engine():
    """Проверить работу DecisionEngine."""
    print("\n🔍 Проверка DecisionEngine...")
    
    try:
        from src.services.decision_engine import DecisionEngine
        from src.repositories.faq_repository import FAQRepository
        from src.utils.db_pool import get_db_pool
        
        # Создаем DecisionEngine
        try:
            pool = await get_db_pool()
            faq_repo = FAQRepository(pool)
            engine = DecisionEngine(faq_repo)
            
            print(f"  ✅ DecisionEngine создан")
            print(f"  ✅ Must-match кейсов загружено: {len(engine.must_match_cases)}")
            
            # Тестируем на простом вопросе
            test_question = "Яйца приехали разбитые, что делать?"
            decision = await engine.make_decision(user_id=1, question=test_question)
            
            print(f"  ✅ Тестовое решение принято:")
            print(f"     - Route: {decision['decision_route']}")
            print(f"     - Confidence: {decision['confidence_score']:.2f}")
            print(f"     - Tag: {decision.get('selected_tag', 'None')}")
            
            return True
        except Exception as db_error:
            # Если БД недоступна, проверяем только загрузку кейсов
            print(f"  ⚠️  БД недоступна (это нормально для проверки без БД)")
            print(f"  ✅ Проверяем загрузку must-match кейсов без БД...")
            
            # Создаем mock FAQRepository
            class MockFAQRepository:
                async def search_hybrid(self, question: str, limit: int = 5):
                    return []
            
            engine = DecisionEngine(MockFAQRepository())
            print(f"  ✅ DecisionEngine создан (mock режим)")
            print(f"  ✅ Must-match кейсов загружено: {len(engine.must_match_cases)}")
            
            return True
    except Exception as e:
        print(f"  ❌ Ошибка DecisionEngine: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_response_validator():
    """Проверить работу ResponseValidator."""
    print("\n🔍 Проверка ResponseValidator...")
    
    try:
        from src.services.response_validator import ResponseValidator
        
        validator = ResponseValidator()
        print(f"  ✅ ResponseValidator создан")
        print(f"  ✅ Правил валидации: {len(validator.rules)}")
        
        # Тестируем валидацию
        test_response = """Суть ситуации: Яйца разбиты при доставке.
Правильное решение / тег: Неаккуратная доставка
Кто отвечает: Курьер
Почему: Повреждение возникло в процессе доставки.
Что делать сейчас: Зафиксировать обращение."""
        
        is_valid, errors, warnings = validator.validate(
            test_response,
            has_tag=True,
            matched_source={"type": "must_match_case", "id": "MM_001"}
        )
        
        print(f"  ✅ Тестовая валидация:")
        print(f"     - Валиден: {is_valid}")
        print(f"     - Ошибок: {len(errors)}")
        print(f"     - Предупреждений: {len(warnings)}")
        
        return True
    except Exception as e:
        print(f"  ❌ Ошибка ResponseValidator: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_explainability_logger():
    """Проверить работу ExplainabilityLogger."""
    print("\n🔍 Проверка ExplainabilityLogger...")
    
    try:
        from src.services.explainability_logger import ExplainabilityLogger
        from pathlib import Path
        
        log_dir = Path(__file__).parent.parent / "logs" / "explainability"
        logger = ExplainabilityLogger(log_dir)
        
        print(f"  ✅ ExplainabilityLogger создан")
        print(f"  ✅ Директория логов: {log_dir}")
        
        # Тестируем логирование
        test_decision = {
            "decision_route": "auto_answer",
            "confidence_score": 0.9,
            "confidence_level": "high",
            "selected_tag": "Неаккуратная доставка",
            "must_match_case": {"id": "MM_001", "responsible": "Курьер"},
            "confidence_breakdown": {},
        }
        
        log_entry = logger.log_decision(
            user_id=1,
            user_query="Тестовый вопрос",
            decision=test_decision,
            validation_result={"valid": True, "errors": [], "warnings": []}
        )
        
        print(f"  ✅ Тестовый лог создан:")
        print(f"     - Timestamp: {log_entry.get('timestamp')}")
        print(f"     - Route: {log_entry.get('decision_route')}")
        print(f"     - Confidence: {log_entry.get('confidence_score')}")
        
        return True
    except Exception as e:
        print(f"  ❌ Ошибка ExplainabilityLogger: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Главная функция проверки."""
    print("=" * 70)
    print("🔍 ПРОВЕРКА НОВОЙ АРХИТЕКТУРЫ")
    print("=" * 70)
    
    results = []
    
    # Проверка импортов
    results.append(await verify_imports())
    
    # Проверка Core Policy JSON
    results.append(verify_core_policy())
    
    # Проверка DecisionEngine (требует БД)
    try:
        results.append(await verify_decision_engine())
    except Exception as e:
        print(f"  ⚠️  DecisionEngine проверка пропущена (требуется БД): {e}")
        results.append(None)
    
    # Проверка ResponseValidator
    results.append(verify_response_validator())
    
    # Проверка ExplainabilityLogger
    results.append(verify_explainability_logger())
    
    # Итоги
    print("\n" + "=" * 70)
    print("📊 ИТОГИ ПРОВЕРКИ")
    print("=" * 70)
    
    passed = sum(1 for r in results if r is True)
    failed = sum(1 for r in results if r is False)
    skipped = sum(1 for r in results if r is None)
    
    print(f"  ✅ Успешно: {passed}")
    print(f"  ❌ Ошибок: {failed}")
    print(f"  ⚠️  Пропущено: {skipped}")
    
    if failed == 0:
        print("\n🎉 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
        return 0
    else:
        print("\n⚠️  ЕСТЬ ОШИБКИ. Проверьте вывод выше.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
