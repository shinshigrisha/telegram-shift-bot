"""
Новый AI-куратор с интеграцией DecisionEngine, ResponseValidator и ExplainabilityLogger.

Использует новую архитектуру:
1. DecisionEngine для принятия решений
2. ResponseValidator для валидации ответов
3. ExplainabilityLogger для логирования
4. Groq API для генерации ответов
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

from groq import Groq  # pyright: ignore[reportMissingImports]

from config.settings import settings
from src.repositories.faq_repository import FAQRepository
from src.services.decision_engine import DecisionEngine
from src.services.response_validator import ResponseValidator
from src.services.explainability_logger import ExplainabilityLogger
from src.utils.config_loader import (
    get_response_structure,
    get_bot_restrictions,
    get_delivery_codex,
    get_knowledge_base_rules,
    get_escalation_message,
)

logger = logging.getLogger(__name__)


class NewCuratorService:
    """
    Новый AI-куратор с интеграцией DecisionEngine.
    
    Использует:
    - DecisionEngine для принятия решений
    - ResponseValidator для валидации ответов
    - ExplainabilityLogger для логирования
    - Groq API для генерации ответов
    """
    
    def __init__(
        self,
        faq_repo: FAQRepository,
        groq_api_key: Optional[str] = None,
        log_dir: Optional[Path] = None,
    ):
        """
        Инициализация нового AI-куратора.
        
        Args:
            faq_repo: Репозиторий для работы с FAQ
            groq_api_key: API ключ Groq (если не передан, берется из settings)
            log_dir: Директория для сохранения explainability логов
        """
        self.faq_repo = faq_repo
        self.decision_engine = DecisionEngine(faq_repo)
        self.validator = ResponseValidator()
        self.logger_explain = ExplainabilityLogger(log_dir)
        
        # Инициализация Groq API
        api_key = groq_api_key or settings.GROQ_API_KEY
        if api_key:
            try:
                self.client = Groq(api_key=api_key)
                self.model_name = "llama-3.1-8b-instant"
                self.groq_enabled = True
            except Exception as e:
                logger.warning("Не удалось инициализировать Groq API: %s", e)
                self.groq_enabled = False
        else:
            self.groq_enabled = False
            logger.warning("GROQ_API_KEY не установлен, форматирование через AI отключено")
    
    def _build_system_prompt(self, decision: Dict[str, Any]) -> str:
        """
        Построить системный промпт на основе решения DecisionEngine.
        
        Args:
            decision: Решение от DecisionEngine
        
        Returns:
            Системный промпт для Groq API
        """
        response_structure = get_response_structure()
        bot_restrictions = get_bot_restrictions()
        delivery_codex = get_delivery_codex()
        knowledge_rules = get_knowledge_base_rules()
        
        mandatory_blocks = response_structure.get("mandatory_blocks", [])
        conditional_blocks = response_structure.get("conditional_blocks", {})
        
        # Формируем структуру ответа
        structure_text = "\n".join([f"{block}:\n[Содержание блока]" for block in mandatory_blocks])
        if conditional_blocks:
            structure_text += f"\n\nУсловные блоки:\n"
            if conditional_blocks.get("tagged"):
                structure_text += f"- Если есть тег: {conditional_blocks.get('tagged')}\n"
            if conditional_blocks.get("not_tagged"):
                structure_text += f"- Если нет тега: {conditional_blocks.get('not_tagged')}\n"
        
        # Формируем контекст из решения
        context_parts = []
        
        if decision.get("must_match_case"):
            case = decision["must_match_case"]
            context_parts.append(f"""
=== MUST-MATCH КЕЙС (ID: {case.get('id')}) ===
Тег: {case.get('main_tag')}
Ответственный: {case.get('responsible')}
Ситуация: {case.get('situation', '')}
Почему: {case.get('why', '')}
Действия: {', '.join(case.get('actions', []))}
""")
        
        if decision.get("faqs") and len(decision["faqs"]) > 0:
            context_parts.append("=== БАЗА ЗНАНИЙ ===")
            for faq in decision["faqs"][:3]:  # Берем первые 3 FAQ
                context_parts.append(f"""
Вопрос: {faq.get('question', '')}
Ответ: {faq.get('answer', '')}
Тег: {faq.get('tag', '')}
""")
        
        context_text = "\n".join(context_parts)
        
        # Формируем ограничения
        restrictions_text = "\n".join([f"- {restriction}" for restriction in bot_restrictions])
        
        # Формируем информацию о кодексе
        codex_principle = delivery_codex.get("principle", "Если нет прямого правила — решение принимает живой куратор.")
        codex_prohibitions = delivery_codex.get("prohibitions", [])
        prohibitions_text = "\n".join([f"- {prohibition}" for prohibition in codex_prohibitions]) if codex_prohibitions else ""
        
        prompt = f"""Ты — виртуальный куратор курьерской доставки ВкусВилл.
Твоя задача — помогать курьерам, отвечая на их вопросы по регламенту и правилам работы.

КОМПАНИЯ: ВкусВилл — сеть магазинов здорового питания и доставки продуктов.

ПРИНЦИП РАБОТЫ: {codex_principle}

ТВОЯ РОЛЬ:
- ОБЪЯСНЯТЬ правила и регламенты из базы знаний
- ПОДСКАЗЫВАТЬ решения на основе примеров и кейсов
- ССЫЛАТЬСЯ на конкретные теги, правила, категории

ТЫ НЕ ДОЛЖЕН:
{restrictions_text}

ЖЕСТКИЕ ПРАВИЛА (КРИТИЧЕСКИ ВАЖНО):
1. Используй ТОЛЬКО информацию из базы знаний, которая будет предоставлена ниже
2. Если в базе знаний нет прямого ответа на вопрос — ОБЯЗАТЕЛЬНО скажи:
   "В базе знаний нет однозначного правила. Рекомендуется обратиться к куратору."
3. НИКОГДА не выдумывай информацию, даже если кажется, что знаешь ответ
4. НИКОГДА не давай обещаний от имени компании
5. Если видишь примеры кейсов в базе знаний — используй их для объяснения

ЗАПРЕЩЕНО:
{prohibitions_text}

СТРУКТУРА ОТВЕТА (обязательный шаблон):
Отвечай строго по следующему шаблону:

{structure_text}

Если информации в базе знаний недостаточно, обязательно скажи:
"В базе знаний нет однозначного правила. Рекомендуется обратиться к куратору."

КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ:
{context_text}

ТОН ОБЩЕНИЯ:
- Дружелюбный, но профессиональный
- Понятный для курьеров (без сложных терминов)
- Конструктивный и полезный
- Поддерживающий, но четкий

ЯЗЫК: ТОЛЬКО русский язык

ОГРАНИЧЕНИЯ:
- Максимум 200 слов на ответ
- Не критикуй курьера, а помогай разобраться
- Всегда будь вежливым, даже если вопрос повторяется
"""
        return prompt
    
    async def get_answer(
        self,
        question: str,
        user_id: Optional[int] = None,
    ) -> str:
        """
        Получить ответ на вопрос курьера.
        
        Использует новую архитектуру:
        1. DecisionEngine для принятия решения
        2. Groq API для генерации ответа
        3. ResponseValidator для валидации
        4. ExplainabilityLogger для логирования
        
        Args:
            question: Вопрос курьера
            user_id: ID пользователя (для логирования)
        
        Returns:
            Ответ AI-куратора или сообщение об эскалации
        """
        user_id = user_id or 0
        
        try:
            # 1. Принимаем решение через DecisionEngine
            decision = await self.decision_engine.make_decision(user_id, question)
            
            # 2. Если требуется эскалация — возвращаем сообщение
            if decision["decision_route"] == "route_to_curator":
                escalation_message = get_escalation_message()
                
                # Логируем решение
                self.logger_explain.log_decision(
                    user_id,
                    question,
                    decision,
                    validation_result={"valid": True, "errors": [], "warnings": []}
                )
                
                return escalation_message
            
            # 3. Генерируем ответ через Groq API
            if not self.groq_enabled:
                # Fallback: используем первый FAQ, если есть
                if decision.get("faqs") and len(decision["faqs"]) > 0:
                    return decision["faqs"][0].get("answer", get_escalation_message())
                return get_escalation_message()
            
            # Строим системный промпт
            system_prompt = self._build_system_prompt(decision)
            
            # Формируем пользовательский промпт
            user_prompt = f"""Вопрос курьера:
{question}

Сформируй ответ на основе предоставленного контекста из базы знаний.
Ответ должен строго соответствовать структуре ответа."""
            
            # Генерируем ответ через Groq API
            try:
                response = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.2,
                    max_tokens=400,
                )
                
                answer = response.choices[0].message.content.strip()
                
                if not answer:
                    answer = get_escalation_message()
            
            except Exception as e:
                logger.error("Ошибка при вызове Groq API: %s", e, exc_info=True)
                answer = get_escalation_message()
            
            # 4. Валидируем ответ
            has_tag = decision.get("selected_tag") is not None
            matched_source = {
                "type": "must_match_case" if decision.get("must_match_case") else "faq",
                "id": decision.get("must_match_case", {}).get("id") if decision.get("must_match_case") else decision.get("faqs", [{}])[0].get("id"),
            } if decision.get("must_match_case") or decision.get("faqs") else None
            
            is_valid, errors, warnings = self.validator.validate(
                answer,
                has_tag=has_tag,
                matched_source=matched_source
            )
            
            validation_result = self.validator.format_validation_result(
                is_valid,
                errors,
                warnings
            )
            
            # 5. Логируем решение
            self.logger_explain.log_decision(
                user_id,
                question,
                decision,
                validation_result=validation_result
            )
            
            # 6. Если валидация не прошла — возвращаем fallback
            if not is_valid:
                logger.warning(
                    "Ответ не прошел валидацию для пользователя %s: %s",
                    user_id,
                    errors
                )
                # Используем fallback сообщение
                return get_escalation_message()
            
            # 7. Возвращаем валидный ответ
            return answer
        
        except Exception as e:
            logger.error(
                "Ошибка при получении ответа для пользователя %s: %s",
                user_id,
                e,
                exc_info=True
            )
            return get_escalation_message()
