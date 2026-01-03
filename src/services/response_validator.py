"""
Валидатор ответов AI-куратора.

Проверяет ответ перед отправкой на соответствие требованиям:
- Все обязательные блоки присутствуют
- Только один тег
- Нет оценок личности
- Есть matched_source
"""
import re
import logging
from typing import Dict, Any, List, Tuple, Optional

from src.utils.config_loader import get_response_validator

logger = logging.getLogger(__name__)


class ResponseValidator:
    """
    Валидатор ответов AI-куратора.
    
    Проверяет ответ на соответствие правилам из response_validator.
    """
    
    def __init__(self):
        """Инициализация валидатора."""
        self.validator_config = get_response_validator()
        self.required_blocks = self.validator_config.get("required_blocks", [])
        self.rules = self.validator_config.get("rules", [])
        self.forbidden_words = self._extract_forbidden_words()
    
    def _extract_forbidden_words(self) -> List[str]:
        """Извлечь запрещенные слова из правил валидации."""
        words = []
        for rule in self.rules:
            if rule.get("id") == "VAL_003":  # Запрещены оценки личности
                words.extend(rule.get("forbidden_words", []))
        return words
    
    def validate(
        self,
        response: str,
        has_tag: bool = False,
        matched_source: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Валидировать ответ.
        
        Args:
            response: Текст ответа
            has_tag: Есть ли тег в ответе
            matched_source: Источник ответа (must_match_case, faq, etc.)
        
        Returns:
            Кортеж (валиден, ошибки, предупреждения)
        """
        errors = []
        warnings = []
        response_lower = response.lower()
        
        # VAL_001: Все обязательные блоки присутствуют
        missing_blocks = []
        for block in self.required_blocks:
            # Ищем блок в ответе (по ключевым словам)
            block_keywords = {
                "Суть ситуации": ["суть", "ситуация", "ситуации"],
                "Кто отвечает": ["кто отвечает", "ответственный", "ответственность"],
                "Почему": ["почему", "причина", "причины"],
                "Что делать сейчас": ["что делать", "действия", "сейчас"],
            }.get(block, [block.lower()])
            
            found = any(keyword in response_lower for keyword in block_keywords)
            if not found:
                missing_blocks.append(block)
        
        if missing_blocks:
            errors.append(f"VAL_001: Отсутствуют обязательные блоки: {', '.join(missing_blocks)}")
        
        # VAL_002: Только один тег (проверяем, если есть тег)
        if has_tag:
            # Считаем упоминания тегов в ответе
            tag_patterns = [
                r"тег[а]?:?\s*[«\"]([^»\"]+)[»\"]",
                r"тег[а]?:?\s*([А-Яа-я\s/]+)",
            ]
            tags_found = []
            for pattern in tag_patterns:
                matches = re.findall(pattern, response, re.IGNORECASE)
                tags_found.extend(matches)
            
            if len(tags_found) > 1:
                errors.append(f"VAL_002: Найдено более одного тега: {tags_found}")
        
        # VAL_003: Запрещены оценки личности
        for word in self.forbidden_words:
            if word.lower() in response_lower:
                errors.append(f"VAL_003: Найдено запрещенное слово: '{word}'")
        
        # VAL_004: Не более 1 уточняющего вопроса
        question_marks = response.count("?")
        if question_marks > 1:
            warnings.append(f"VAL_004: Найдено более одного вопроса ({question_marks})")
        
        # VAL_005: Есть matched_source
        if not matched_source:
            errors.append("VAL_005: Ответ не ссылается на базу знаний или кейсы")
        else:
            # Проверяем, что в ответе есть упоминание источника
            source_types = ["правило", "регламент", "кейс", "база знаний", "кодекс"]
            has_source_mention = any(source_type in response_lower for source_type in source_types)
            if not has_source_mention:
                warnings.append("VAL_005: В ответе нет явного упоминания источника")
        
        # Итоговый результат
        is_valid = len(errors) == 0
        
        return is_valid, errors, warnings
    
    def format_validation_result(
        self,
        is_valid: bool,
        errors: List[str],
        warnings: List[str]
    ) -> Dict[str, Any]:
        """
        Форматировать результат валидации.
        
        Args:
            is_valid: Валиден ли ответ
            errors: Список ошибок
            warnings: Список предупреждений
        
        Returns:
            Словарь с результатом валидации
        """
        return {
            "valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "error_count": len(errors),
            "warning_count": len(warnings),
        }
