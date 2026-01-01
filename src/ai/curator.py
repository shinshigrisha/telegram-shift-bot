"""
AI-куратор для курьеров с использованием Groq API (LLaMA 3).

Модуль обеспечивает интеллектуальную поддержку курьеров через:
- Генерацию ответов на вопросы с использованием Groq API (LLaMA 3)
- Поиск релевантных ответов в базе знаний (PostgreSQL)
- Хранение истории диалога в Redis
- Готовые промпты для разных сценариев (вопросы, замечания, рассылки)
"""
import asyncio
import json
import logging
from typing import List, Optional, Dict, Any

from groq import Groq  # pyright: ignore[reportMissingImports]
from redis.asyncio import Redis  # pyright: ignore[reportMissingImports]

from config.settings import settings  # pyright: ignore[reportMissingImports]
from src.repositories.faq_repository import FAQRepository
from src.utils.config_loader import (
    load_config,
    check_must_match_case,
    get_response_structure,
    get_tags,
    get_knowledge_base_rules,
    get_training_cases,
    get_delivery_codex,
    get_response_validator,
    get_bot_restrictions,
    get_escalation_message,
    get_confidence_thresholds,
    get_communication_rules,
    get_bot_communication_behavior,
    get_payment_policy,
    get_payment_basic_rules,
    get_terminal_payment,
    get_mixed_payment_policy,
    get_terminal_refund_policy,
    get_payment_hyperlink_policy,
    get_hyperlink_basic_rules,
    get_hyperlink_restrictions,
    get_returns_policy_v1_1,
    get_bot_payment_restrictions,
)

logger = logging.getLogger(__name__)


# ============================================================================
# ПРОМПТЫ ДЛЯ РАЗНЫХ СЦЕНАРИЕВ
# ============================================================================

def _build_system_prompt() -> str:
    """
    Построить системный промпт на основе конфигурации.
    
    Returns:
        Системный промпт для AI-куратора
    """
    try:
        config = load_config()
        response_structure = get_response_structure()
        bot_restrictions = get_bot_restrictions()
        delivery_codex = get_delivery_codex()
        knowledge_rules = get_knowledge_base_rules()
        training_cases = get_training_cases()
        
        mandatory_blocks = response_structure.get("mandatory_blocks", [])
        conditional_blocks = response_structure.get("conditional_blocks", {})
        
        # Формируем список основных правил
        rules_text = "\n".join([f"- {rule.get('rule', '')} (Ответственный: {rule.get('who_responsible', '')})" for rule in knowledge_rules[:5]])
        
        # Получаем дополнительные модули
        communication_rules = get_communication_rules()
        bot_comm_behavior = get_bot_communication_behavior()
        payment_policy = get_payment_policy()
        payment_rules = get_payment_basic_rules()
        terminal_payment = get_terminal_payment()
        mixed_payment = get_mixed_payment_policy()
        terminal_refund = get_terminal_refund_policy()
        hyperlink_policy = get_payment_hyperlink_policy()
        hyperlink_rules = get_hyperlink_basic_rules()
        hyperlink_restrictions = get_hyperlink_restrictions()
        returns_policy = get_returns_policy_v1_1()
        bot_payment_restrictions = get_bot_payment_restrictions()
        
        # Формируем список ограничений (общие + по оплате)
        all_restrictions = bot_restrictions + bot_payment_restrictions
        restrictions_text = "\n".join([f"- {restriction}" for restriction in all_restrictions])
        
        # Формируем правила общения
        comm_rules_text = "\n".join([f"- {rule.get('rule', '')} (Применяется к: {rule.get('applies_to', '')})" for rule in communication_rules[:4]])
        bot_must = bot_comm_behavior.get("must", [])
        bot_must_not = bot_comm_behavior.get("must_not", [])
        bot_behavior_text = ""
        if bot_must:
            bot_behavior_text += "\nОБЯЗАТЕЛЬНО:\n" + "\n".join([f"- {item}" for item in bot_must])
        if bot_must_not:
            bot_behavior_text += "\nЗАПРЕЩЕНО:\n" + "\n".join([f"- {item}" for item in bot_must_not])
        
        # Формируем правила оплаты
        payment_principle = payment_policy.get("principle", "")
        payment_rules_text = "\n".join([f"- {rule.get('rule', '')} (ID: {rule.get('id', '')})" for rule in payment_rules])
        terminal_steps = terminal_payment.get("steps", [])
        terminal_steps_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(terminal_steps)])
        terminal_important = terminal_payment.get("important", [])
        terminal_important_text = "\n".join([f"- {item}" for item in terminal_important])
        
        # Формируем правила смешанной оплаты
        mixed_payment_text = ""
        for mix in mixed_payment:
            if mix.get("situation"):
                mixed_payment_text += f"\n- {mix.get('situation')}: разрешено, но ОБЯЗАТЕЛЬНА эскалация к куратору"
        
        # Формируем правила возвратов
        refund_text = ""
        for refund in terminal_refund:
            if refund.get("rule"):
                refund_text += f"\n- {refund.get('rule', '')} (ID: {refund.get('id', '')})"
        
        # Формируем правила гиперссылки
        hyperlink_purpose = hyperlink_policy.get("purpose", "")
        hyperlink_rules_text = "\n".join([f"- {rule.get('rule', '')} (ID: {rule.get('id', '')})" for rule in hyperlink_rules])
        hyperlink_restr_text = "\n".join([f"- {restr.get('restriction', '')} (ID: {restr.get('id', '')})" for restr in hyperlink_restrictions])
        
        # Формируем правила возвратов v1.1
        returns_full = returns_policy.get("full_return", {})
        returns_partial = returns_policy.get("partial_return", {})
        returns_text = f"""
ПОЛНЫЙ ВОЗВРАТ: {'Запрещён через терминал' if not returns_full.get('via_terminal') else 'Разрешён'}
ЧАСТИЧНЫЙ ВОЗВРАТ: {'Разрешён' if returns_partial.get('allowed') else 'Запрещён'}
"""
        
        # Формируем структуру ответа
        structure_text = "\n".join([f"{block}:\n[Содержание блока]" for block in mandatory_blocks])
        if conditional_blocks:
            structure_text += f"\n\nУсловные блоки:\n"
            if conditional_blocks.get("tagged"):
                structure_text += f"- Если есть тег: {conditional_blocks.get('tagged')}\n"
            if conditional_blocks.get("not_tagged"):
                structure_text += f"- Если нет тега: {conditional_blocks.get('not_tagged')}\n"
        
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

ОСНОВНЫЕ ПРАВИЛА ДОСТАВКИ:
{rules_text}

ЗАПРЕЩЕНО:
{prohibitions_text}

СТРУКТУРА ОТВЕТА (обязательный шаблон):
Отвечай строго по следующему шаблону:

{structure_text}

Если информации в базе знаний недостаточно, обязательно скажи:
"В базе знаний нет однозначного правила. Рекомендуется обратиться к куратору."

ФОРМАТ БАЗЫ ЗНАНИЙ:
База знаний содержит структурированные записи с:
- Категорией (Теги обращений, Кодекс доставки, Памятки, Чек-листы)
- Ответственностью (Кто отвечает)
- Важностью (severity)
- Связанными тегами
- Примерами реальных кейсов (Ситуация → Решение → Почему)

Используй примеры кейсов для лучшего объяснения — они показывают, как применяется правило на практике.

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

ПРАВИЛА ОБЩЕНИЯ (КРИТИЧЕСКИ ВАЖНО):
{comm_rules_text}

ПОВЕДЕНИЕ БОТА ПРИ ОБЩЕНИИ:
{bot_behavior_text}

ПРАВИЛА ОПЛАТЫ (КРИТИЧЕСКИ ВАЖНО):
Принцип: {payment_principle}

Базовые правила оплаты:
{payment_rules_text}

Оплата по терминалу / QR-коду:
Шаги:
{terminal_steps_text}

Важно:
{terminal_important_text}

Смешанные типы оплаты (ТОЛЬКО с эскалацией):
{mixed_payment_text}

Возвраты по терминалу:
{refund_text}

ПРАВИЛА ОПЛАТЫ ПО ГИПЕРССЫЛКЕ (КРИТИЧЕСКИ ВАЖНО, РЕЗЕРВНЫЙ СПОСОБ):
Назначение: {hyperlink_purpose}

Базовые правила:
{hyperlink_rules_text}

Ограничения:
{hyperlink_restr_text}

ПРАВИЛА ВОЗВРАТОВ v1.1 (P0):
{returns_text}

КРИТИЧЕСКИ ВАЖНО ПО ОПЛАТЕ:
- Бот НИКОГДА не подтверждает финансовые операции
- Бот НИКОГДА не разрешает возвраты самостоятельно
- Бот НИКОГДА не интерпретирует фрод
- Бот НИКОГДА не обещает компенсации
- Все спорные и нестандартные случаи оплаты → ОБЯЗАТЕЛЬНА эскалация к куратору или поддержке
"""
        return prompt
    except Exception as e:
        logger.error("Ошибка при построении системного промпта: %s", e, exc_info=True)
        # Возвращаем базовый промпт при ошибке
        return """
Ты — виртуальный куратор курьерской доставки ВкусВилл.
Твоя задача — помогать курьерам, отвечая на их вопросы по регламенту и правилам работы.
Используй ТОЛЬКО информацию из базы знаний.
Если в базе знаний нет прямого ответа — скажи: "В базе знаний нет однозначного правила. Рекомендуется обратиться к куратору."
"""


# Базовый системный промпт для AI-куратора (генерируется из конфигурации)
SYSTEM_PROMPT = _build_system_prompt()

# Промпт для замечаний о нарушениях
WARNING_PROMPT = """
Ты — куратор, который делает вежливые замечания курьерам о нарушениях.

Требования к замечанию:
1. Вежливо и конструктивно
2. Указывай на конкретное нарушение
3. Объясняй почему это важно
4. Предлагай решение
5. Не обвиняй, а помогай исправить ситуацию
6. Максимум 150 слов

Тон: поддерживающий, но четкий
"""

# Промпт для информационных рассылок
BROADCAST_PROMPT = """
Ты — куратор, который создает информационные сообщения для рассылки курьерам.

Требования к сообщению:
1. Кратко и по делу (максимум 200 слов)
2. Понятная структура
3. Важная информация в начале
4. Используй эмодзи для выделения ключевых моментов (умеренно)
5. Призыв к действию, если нужно

Тон: официальный, но дружелюбный
"""


# ============================================================================
# КЛАСС AI-КУРАТОРА
# ============================================================================

class AICurator:
    """
    AI-куратор для обработки вопросов курьеров.
    
    Использует:
    - Groq API (LLaMA 3) для генерации ответов
    - PostgreSQL (FAQRepository) для поиска релевантных ответов
    - Redis для хранения истории диалога
    """
    
    def __init__(
        self,
        faq_repo: FAQRepository,
        redis: Redis,
        groq_api_key: Optional[str] = None,
    ) -> None:
        """
        Инициализация AI-куратора.
        
        Args:
            faq_repo: Репозиторий для работы с FAQ
            redis: Клиент Redis для хранения истории
            groq_api_key: API ключ Groq (если не передан, берется из settings)
        """
        self.faq_repo = faq_repo
        self.redis = redis
        
        # Инициализация Groq API
        api_key = groq_api_key or settings.GROQ_API_KEY
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY не найден. Установите его в .env файле или передайте в конструктор."
            )
        
        # Создаем клиент Groq
        self.client = Groq(api_key=api_key)
        # Используем llama-3.1-8b-instant как оптимальную модель для диалогов
        self.model_name = "llama-3.1-8b-instant"
        
        # Настройки для истории диалога
        self.history_max_length = 10  # Последние 10 сообщений
        self.history_key_prefix = "curator_history:"  # Префикс ключа в Redis
    
    def _format_faq_entry(self, faq: Any) -> str:
        """
        Форматировать запись FAQ в структурированный вид для ИИ.
        
        Поддерживает как старый формат (объект с атрибутами), так и новый (словарь из PostgreSQL).
        
        Args:
            faq: Запись FAQ из базы данных (словарь или объект)
        
        Returns:
            Отформатированный текст записи с категорией, тегами
        """
        # Поддержка как словаря (PostgreSQL), так и объекта
        if isinstance(faq, dict):
            question = faq.get('question', '')
            answer = faq.get('answer', '')
            category = faq.get('category', '')
            tag = faq.get('tag', '')
            keywords = faq.get('keywords', [])
        else:
            question = getattr(faq, 'question', '')
            answer = getattr(faq, 'answer', '')
            category = getattr(faq, 'category', '')
            tag = getattr(faq, 'tag', '')
            keywords = getattr(faq, 'keywords', [])
        
        parts = []
        
        # Заголовок
        parts.append(f"=== {question} ===")
        
        # Категория и тег
        if category:
            parts.append(f"Категория: {category}")
        
        if tag:
            parts.append(f"Тег: {tag}")
        
        # Ответ/Описание
        parts.append(f"Ответ: {answer}")
        
        # Ключевые слова (для отладки, можно убрать в продакшене)
        if keywords and len(keywords) > 0:
            parts.append(f"Ключевые слова: {', '.join(keywords[:5])}")
        
        return "\n".join(parts)
    
    async def get_relevant_faq(self, question: str) -> str:
        """
        Найти релевантные FAQ для вопроса и отформатировать их структурированно.
        
        Использует гибридный поиск (RAG):
        1. Поиск по ключевым словам (быстрый, точный)
        2. Полнотекстовый поиск PostgreSQL (если нужно больше результатов)
        
        Args:
            question: Вопрос курьера
        
        Returns:
            Текст с релевантными FAQ в структурированном формате
        """
        try:
            # Используем гибридный поиск (RAG)
            faqs = await self.faq_repo.search_hybrid(question, limit=5)
            
            if not faqs:
                return "База знаний пока не содержит информации по данному вопросу."
            
            # Формируем структурированный текст с FAQ
            faq_texts = []
            for faq in faqs:
                faq_texts.append(self._format_faq_entry(faq))
            
            return "\n\n" + "="*60 + "\n\n".join(faq_texts)
        
        except Exception as e:
            logger.error("Ошибка при поиске FAQ: %s", e, exc_info=True)
            return "Ошибка при поиске в базе знаний."
    
    async def get_history(self, user_id: int) -> List[Dict[str, str]]:
        """
        Получить историю диалога пользователя из Redis.
        
        Args:
            user_id: ID пользователя в Telegram
        
        Returns:
            Список сообщений в формате [{"role": "user|assistant", "text": "..."}]
        """
        try:
            key = f"{self.history_key_prefix}{user_id}"
            history_json = await self.redis.lrange(key, 0, -1)
            
            if not history_json:
                return []
            
            history = []
            for item in history_json:
                try:
                    history.append(json.loads(item))
                except json.JSONDecodeError:
                    logger.warning("Ошибка декодирования истории для пользователя %s", user_id)
                    continue
            
            return history
        
        except Exception as e:
            logger.error("Ошибка при получении истории для пользователя %s: %s", user_id, e, exc_info=True)
            return []
    
    async def save_to_history(self, user_id: int, role: str, text: str) -> None:
        """
        Сохранить сообщение в историю диалога пользователя.
        
        Args:
            user_id: ID пользователя в Telegram
            role: Роль сообщения ("user" или "assistant")
            text: Текст сообщения
        """
        try:
            key = f"{self.history_key_prefix}{user_id}"
            
            # Получаем текущую историю
            history = await self.get_history(user_id)
            
            # Добавляем новое сообщение
            history.append({"role": role, "text": text})
            
            # Ограничиваем длину истории
            if len(history) > self.history_max_length:
                history = history[-self.history_max_length:]
            
            # Удаляем старую историю и сохраняем новую
            await self.redis.delete(key)
            if history:
                # Сохраняем каждый элемент истории как JSON строку
                for item in history:
                    await self.redis.rpush(key, json.dumps(item))
                
                # Устанавливаем TTL 7 дней (604800 секунд)
                await self.redis.expire(key, 604800)
        
        except Exception as e:
            logger.error("Ошибка при сохранении истории для пользователя %s: %s", user_id, e, exc_info=True)
    
    async def generate_response(
        self,
        user_id: int,
        question: str,
        prompt_type: str = "question",
    ) -> str:
        """
        Сгенерировать ответ на вопрос курьера.
        
        Использует must-match кейсы и confidence routing для определения маршрута.
        
        Args:
            user_id: ID пользователя в Telegram
            question: Вопрос курьера
            prompt_type: Тип промпта ("question", "warning", "broadcast")
        
        Returns:
            Ответ AI-куратора или сообщение об эскалации
        """
        try:
            # Для рассылок и замечаний не применяем must-match и confidence routing
            if prompt_type in ("warning", "broadcast"):
                return await self._generate_response_without_routing(
                    user_id, question, prompt_type
                )
            
            # Проверяем must-match кейсы в первую очередь
            must_match_case = check_must_match_case(question)
            if must_match_case:
                logger.info(
                    "✅ Найден must-match кейс %s для пользователя %s: %s",
                    must_match_case.get("id"),
                    user_id,
                    question[:50] if len(question) > 50 else question,
                )
                # Если найден must-match кейс, можно отвечать автоматически
                faqs = await self._get_faqs_for_question(question)
                return await self._generate_response_with_must_match(
                    user_id, question, must_match_case, faqs
                )
            
            # Получаем релевантные FAQ для проверки confidence
            faqs = await self._get_faqs_for_question(question)
            
            # Простая проверка confidence: если есть релевантные FAQ, отвечаем
            # В будущем можно добавить более сложную логику
            if not faqs or len(faqs) == 0:
                logger.info(
                    "⚠️  Эскалация для пользователя %s: нет релевантных FAQ (вопрос: %s)",
                    user_id,
                    question[:50] if len(question) > 50 else question,
                )
                escalation_message = get_escalation_message()
                await self.save_to_history(user_id, "user", question)
                await self.save_to_history(user_id, "assistant", escalation_message)
                return escalation_message
            
            # Если есть FAQ, генерируем ответ
            return await self._generate_response_without_routing(
                user_id, question, prompt_type
            )
        
        except Exception as e:
            logger.error(
                "Ошибка при генерации ответа для пользователя %s: %s",
                user_id,
                e,
                exc_info=True,
            )
            return get_escalation_message()
    
    async def _get_faqs_for_question(self, question: str) -> List[Any]:
        """
        Получить список FAQ для вопроса.
        
        Args:
            question: Вопрос пользователя
        
        Returns:
            Список найденных FAQ
        """
        try:
            # Сначала пробуем поиск по ключевым словам
            faqs = await self.faq_repo.search_by_keywords(question, limit=5)
            
            # Если не нашли, пробуем поиск по тексту
            if not faqs:
                faqs = await self.faq_repo.search_by_text(question, limit=5)
            
            return faqs
        except Exception as e:
            logger.error("Ошибка при поиске FAQ: %s", e, exc_info=True)
            return []
    
    async def _generate_response_with_must_match(
        self,
        user_id: int,
        question: str,
        must_match_case: Dict[str, Any],
        faqs: List[Any],
    ) -> str:
        """
        Сгенерировать ответ на основе must-match кейса.
        
        Args:
            user_id: ID пользователя в Telegram
            question: Вопрос курьера
            must_match_case: Найденный must-match кейс
            faqs: Найденные FAQ записи для контекста
        
        Returns:
            Ответ AI-куратора
        """
        try:
            # Получаем релевантные FAQ для дополнительного контекста
            faq_context = await self.get_relevant_faq(question)
            
            # Получаем историю диалога
            history = await self.get_history(user_id)
            
            # Формируем контекст с must-match кейсом
            must_match_context = f"""
=== MUST-MATCH КЕЙС (ID: {must_match_case.get('id')}) ===
Тег: {must_match_case.get('main_tag')}
Ответственный: {must_match_case.get('responsible')}
Ситуация: {must_match_case.get('situation', '')}
Почему: {must_match_case.get('why', '')}
Действия: {', '.join(must_match_case.get('actions', []))}

Эта ситуация точно соответствует правилу из базы знаний.
Используй этот кейс как основу для ответа.
"""
            
            # Формируем сообщения для Groq API
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
            ]
            
            # Добавляем историю диалога
            if history:
                for msg in history[-5:]:
                    role = "user" if msg["role"] == "user" else "assistant"
                    messages.append({"role": role, "content": msg["text"]})
            
            # Добавляем must-match кейс, базу знаний и текущий вопрос
            messages.append({
                "role": "user",
                "content": f"""--- MUST-MATCH КЕЙС ---\n{must_match_context}\n\n--- БАЗА ЗНАНИЙ ---\n{faq_context}\n\n--- ТЕКУЩИЙ ВОПРОС ---\nКурьер: {question}\n\n--- ТВОЙ ОТВЕТ ---\nКуратор:"""
            })
            
            # Генерируем ответ через Groq API
            try:
                response = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model=self.model_name,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=400,
                )
                
                # Извлекаем текст ответа
                if response and response.choices and len(response.choices) > 0:
                    answer = response.choices[0].message.content.strip()
                    if not answer:
                        answer = "Извините, не удалось сгенерировать ответ. Пожалуйста, обратитесь к живому куратору."
                        logger.warning("Пустой ответ от Groq для пользователя %s", user_id)
                else:
                    answer = "Извините, не удалось сгенерировать ответ. Пожалуйста, обратитесь к живому куратору."
                    logger.warning("Пустой или некорректный ответ от Groq для пользователя %s", user_id)
            except Exception as e:
                logger.error("Ошибка при вызове Groq API: %s", e, exc_info=True)
                answer = "Произошла ошибка при генерации ответа. Пожалуйста, попробуйте позже или обратитесь к живому куратору."
            
            # Сохраняем в историю
            await self.save_to_history(user_id, "user", question)
            await self.save_to_history(user_id, "assistant", answer)
            
            logger.info(
                "✅ Ответ сгенерирован на основе must-match кейса %s для пользователя %s",
                must_match_case.get("id"),
                user_id,
            )
            
            return answer
        
        except Exception as e:
            logger.error(
                "Ошибка при генерации ответа с must-match кейсом для пользователя %s: %s",
                user_id,
                e,
                exc_info=True,
            )
            return get_escalation_message()
    
    async def _generate_response_without_routing(
        self,
        user_id: int,
        question: str,
        prompt_type: str = "question",
    ) -> str:
        """
        Сгенерировать ответ без проверки must-match и confidence-routing.
        
        Используется для рассылок, замечаний или после прохождения проверок.
        
        Args:
            user_id: ID пользователя в Telegram
            question: Вопрос курьера
            prompt_type: Тип промпта ("question", "warning", "broadcast")
        
        Returns:
            Ответ AI-куратора
        """
        try:
            # Выбираем базовый промпт в зависимости от типа
            if prompt_type == "warning":
                base_prompt = WARNING_PROMPT
            elif prompt_type == "broadcast":
                base_prompt = BROADCAST_PROMPT
            else:
                base_prompt = SYSTEM_PROMPT
            
            # Получаем релевантные FAQ
            faq_context = await self.get_relevant_faq(question)
            
            # Получаем историю диалога
            history = await self.get_history(user_id)
            
            # Формируем сообщения для Groq API
            messages = [
                {"role": "system", "content": base_prompt},
            ]
            
            # Добавляем историю диалога
            if history:
                for msg in history[-5:]:  # Берем последние 5 сообщений для контекста
                    role = "user" if msg["role"] == "user" else "assistant"
                    messages.append({"role": role, "content": msg["text"]})
            
            # Добавляем базу знаний и текущий вопрос
            messages.append({
                "role": "user",
                "content": f"""--- БАЗА ЗНАНИЙ ---\n{faq_context}\n\n--- ТЕКУЩИЙ ВОПРОС ---\nКурьер: {question}\n\n--- ТВОЙ ОТВЕТ ---\nКуратор:"""
            })
            
            # Генерируем ответ через Groq API
            try:
                response = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model=self.model_name,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=400,
                )
                
                # Извлекаем текст ответа
                if response and response.choices and len(response.choices) > 0:
                    answer = response.choices[0].message.content.strip()
                    if not answer:
                        answer = "Извините, не удалось сгенерировать ответ. Пожалуйста, обратитесь к живому куратору."
                        logger.warning("Пустой ответ от Groq для пользователя %s", user_id)
                else:
                    answer = "Извините, не удалось сгенерировать ответ. Пожалуйста, обратитесь к живому куратору."
                    logger.warning("Пустой или некорректный ответ от Groq для пользователя %s", user_id)
            except Exception as e:
                logger.error("Ошибка при вызове Groq API: %s", e, exc_info=True)
                answer = "Произошла ошибка при генерации ответа. Пожалуйста, попробуйте позже или обратитесь к живому куратору."
            
            # Сохраняем в историю
            await self.save_to_history(user_id, "user", question)
            await self.save_to_history(user_id, "assistant", answer)
            
            # Логируем запрос
            logger.info(
                "AI-куратор: пользователь %s, тип=%s, вопрос=%s (первые 50 символов)",
                user_id,
                prompt_type,
                question[:50] if len(question) > 50 else question,
            )
            
            return answer
        
        except Exception as e:
            logger.error(
                "Ошибка при генерации ответа для пользователя %s: %s",
                user_id,
                e,
                exc_info=True,
            )
            return (
                "Произошла ошибка при обработке вашего вопроса. "
                "Пожалуйста, попробуйте позже или обратитесь к живому куратору."
            )
    
    async def generate_warning(
        self,
        user_id: int,
        violation_description: str,
    ) -> str:
        """
        Сгенерировать замечание о нарушении.
        
        Args:
            user_id: ID пользователя в Telegram
            violation_description: Описание нарушения
        
        Returns:
            Текст замечания
        """
        return await self.generate_response(
            user_id=user_id,
            question=violation_description,
            prompt_type="warning",
        )
    
    async def generate_broadcast(
        self,
        topic: str,
        details: Optional[str] = None,
    ) -> str:
        """
        Сгенерировать информационное сообщение для рассылки.
        
        Args:
            topic: Тема сообщения
            details: Дополнительные детали (опционально)
        
        Returns:
            Текст сообщения для рассылки
        """
        question = f"Тема: {topic}"
        if details:
            question += f"\nДетали: {details}"
        
        # Используем фиктивный user_id для рассылок (0)
        return await self.generate_response(
            user_id=0,
            question=question,
            prompt_type="broadcast",
        )
    
    async def clear_history(self, user_id: int) -> None:
        """
        Очистить историю диалога пользователя.
        
        Args:
            user_id: ID пользователя в Telegram
        """
        try:
            key = f"{self.history_key_prefix}{user_id}"
            await self.redis.delete(key)
            logger.info("История пользователя %s очищена", user_id)
        except Exception as e:
            logger.error("Ошибка при очистке истории для пользователя %s: %s", user_id, e, exc_info=True)
