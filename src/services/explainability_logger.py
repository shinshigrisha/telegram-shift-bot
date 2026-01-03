"""
Логгер explainability для AI-куратора.

Логирует все решения бота в структурированном виде для аудита.
"""
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class ExplainabilityLogger:
    """
    Логгер explainability для AI-куратора.
    
    Сохраняет все решения в структурированном виде:
    - user_query
    - matched_source
    - decision_route
    - confidence_score
    - reason
    """
    
    def __init__(self, log_dir: Optional[Path] = None):
        """
        Инициализация логгера.
        
        Args:
            log_dir: Директория для сохранения логов (если None, используется логирование)
        """
        self.log_dir = log_dir
        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def log_decision(
        self,
        user_id: int,
        user_query: str,
        decision: Dict[str, Any],
        validation_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Залогировать решение бота.
        
        Args:
            user_id: ID пользователя
            user_query: Вопрос пользователя
            decision: Решение движка принятия решений
            validation_result: Результат валидации ответа
        
        Returns:
            Словарь с логом решения
        """
        # Формируем matched_source
        matched_source = {
            "type": "fallback",
            "id": None,
            "source": None,
        }
        
        if decision.get("must_match_case"):
            matched_source = {
                "type": "must_match_case",
                "id": decision["must_match_case"].get("id"),
                "source": decision["must_match_case"].get("source"),
            }
        elif decision.get("faqs") and len(decision["faqs"]) > 0:
            matched_source = {
                "type": "faq",
                "id": decision["faqs"][0].get("id"),
                "source": "unified_knowledge_base",
            }
        
        # Формируем лог
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "user_query": user_query,
            "matched_source": matched_source,
            "decision_route": decision.get("decision_route"),
            "confidence_score": decision.get("confidence_score"),
            "confidence_level": decision.get("confidence_level"),
            "confidence_breakdown": decision.get("confidence_breakdown", {}),
            "selected_tag": decision.get("selected_tag"),
            "responsibility": decision.get("must_match_case", {}).get("responsible") if decision.get("must_match_case") else None,
            "reason": decision.get("escalation_reason") or "Решение принято на основе confidence score",
            "validation_result": validation_result or {},
            "forbidden_check_passed": validation_result.get("valid", True) if validation_result else True,
        }
        
        # Логируем в файл, если указана директория
        if self.log_dir:
            self._save_to_file(log_entry)
        
        # Логируем в стандартный логгер
        logger.info(
            "Explainability log: user_id=%s, route=%s, confidence=%.2f, tag=%s",
            user_id,
            log_entry["decision_route"],
            log_entry["confidence_score"],
            log_entry["selected_tag"],
        )
        
        return log_entry
    
    def _save_to_file(self, log_entry: Dict[str, Any]) -> None:
        """
        Сохранить лог в файл.
        
        Args:
            log_entry: Запись лога
        """
        try:
            # Сохраняем в JSONL файл (по одному дню)
            date_str = datetime.utcnow().strftime("%Y-%m-%d")
            log_file = self.log_dir / f"explainability_{date_str}.jsonl"
            
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        
        except Exception as e:
            logger.error("Ошибка при сохранении explainability log: %s", e, exc_info=True)
