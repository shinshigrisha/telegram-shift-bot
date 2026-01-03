"""
Улучшенный AI-куратор с живым общением.

Добавляет к базовому SimpleCuratorService:
1. Память стиля общения пользователя (через Redis)
2. Понимание контекста вопроса
3. "Человеческие" переходные фразы
4. Разделение ролей (курьер / куратор)
5. Уточняющий вопрос, если есть риск ошибки

ВАЖНО: Этот класс НЕ вызывается автоматически.
Используйте его явно, если нужны улучшенные ответы.
"""
import json
import logging
import random
import re
from typing import Optional, List, Dict, Any, Literal
from enum import Enum

from groq import Groq  # pyright: ignore[reportMissingImports]
from redis.asyncio import Redis  # pyright: ignore[reportMissingImports]

from config.settings import settings
from src.repositories.faq_repository import FAQRepository
from src.services.simple_curator_service import SimpleCuratorService

logger = logging.getLogger(__name__)


class QuestionContext(Enum):
    """Тип контекста вопроса."""
    CAN_CANNOT = "can_cannot"  # Вопрос про "можно / нельзя"
    WHAT_TO_DO = "what_to_do"  # Вопрос про "что делать в ситуации"
    ERROR_COMPLAINT = "error_complaint"  # Вопрос про "ошибку / жалобу"
    GENERAL = "general"  # Общий вопрос


class UserRole(Enum):
    """Роль пользователя."""
    COURIER = "courier"  # Курьер
    CURATOR = "curator"  # Куратор
    UNKNOWN = "unknown"  # Не определена


class CommunicationStyle(Enum):
    """Стиль общения пользователя."""
    SHORT = "short"  # Короткие сообщения
    DETAILED = "detailed"  # Развернутые сообщения
    FREQUENT = "frequent"  # Частые вопросы
    UNKNOWN = "unknown"  # Не определен


class EnhancedCuratorService:
    """
    Улучшенный AI-куратор с живым общением.
    
    Обёртка над SimpleCuratorService, добавляющая:
    - Анализ контекста вопроса
    - Определение роли пользователя
    - Память стиля общения
    - Улучшенные промпты
    - Переходные фразы
    - Уточняющие вопросы
    """
    
    def __init__(
        self,
        faq_repo: FAQRepository,
        redis: Optional[Redis] = None,
        groq_api_key: Optional[str] = None,
    ) -> None:
        """
        Инициализация улучшенного куратора.
        
        Args:
            faq_repo: Репозиторий для работы с FAQ
            redis: Клиент Redis для чтения стиля общения (опционально)
            groq_api_key: API ключ Groq (если не передан, берется из settings)
        """
        # Базовый сервис для поиска FAQ
        self.base_service = SimpleCuratorService(faq_repo=faq_repo, groq_api_key=groq_api_key)
        self.faq_repo = faq_repo
        self.redis = redis
        
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
        
        # Префикс для ключей Redis (только чтение, без изменения существующих)
        self.style_key_prefix = "curator_style:"  # Отдельный префикс, не конфликтует с историей
    
    def analyze_question_context(self, question: str) -> QuestionContext:
        """
        Анализировать контекст вопроса.
        
        Определяет тип вопроса:
        - можно/нельзя
        - что делать
        - ошибка/жалоба
        - общий
        
        Args:
            question: Вопрос пользователя
            
        Returns:
            Тип контекста вопроса
        """
        question_lower = question.lower()
        
        # Вопрос про "можно / нельзя"
        can_cannot_patterns = [
            r'\b(можно|нельзя|разрешено|запрещено|допустимо|недопустимо)\b',
            r'\b(можно ли|нельзя ли|разрешено ли|запрещено ли)\b',
            r'\b(можно\?|нельзя\?|разрешено\?|запрещено\?)\b',
        ]
        for pattern in can_cannot_patterns:
            if re.search(pattern, question_lower):
                return QuestionContext.CAN_CANNOT
        
        # Вопрос про "что делать"
        what_to_do_patterns = [
            r'\b(что делать|как быть|что предпринять|как поступить)\b',
            r'\b(что делать если|что делать когда|как быть если)\b',
            r'\b(как действовать|какие действия|что нужно)\b',
        ]
        for pattern in what_to_do_patterns:
            if re.search(pattern, question_lower):
                return QuestionContext.WHAT_TO_DO
        
        # Вопрос про ошибку/жалобу
        error_patterns = [
            r'\b(ошибка|ошиблись|неправильно|не так|проблема)\b',
            r'\b(жалоба|жалуется|недоволен|недовольны)\b',
            r'\b(плохо|плохой|некачественно|неаккуратно)\b',
        ]
        for pattern in error_patterns:
            if re.search(pattern, question_lower):
                return QuestionContext.ERROR_COMPLAINT
        
        # Общий вопрос
        return QuestionContext.GENERAL
    
    def detect_user_role(self, question: str) -> UserRole:
        """
        Определить роль пользователя по вопросу.
        
        Не спрашивает напрямую, определяет по контексту.
        
        Args:
            question: Вопрос пользователя
            
        Returns:
            Роль пользователя
        """
        question_lower = question.lower()
        
        # Признаки курьера
        courier_patterns = [
            r'\b(я курьер|я доставляю|у меня заказ|мой заказ)\b',
            r'\b(клиент|покупатель|получатель)\b',
            r'\b(доставка|доставить|привезти|привез)\b',
            r'\b(адрес|адреса|по адресу)\b',
        ]
        for pattern in courier_patterns:
            if re.search(pattern, question_lower):
                return UserRole.COURIER
        
        # Признаки куратора
        curator_patterns = [
            r'\b(обращение|обращения|тег|теги|разбор)\b',
            r'\b(куратор|кураторы|кураторство)\b',
            r'\b(классификация|классифицировать|разметить)\b',
        ]
        for pattern in curator_patterns:
            if re.search(pattern, question_lower):
                return UserRole.CURATOR
        
        # Роль не определена
        return UserRole.UNKNOWN
    
    async def get_communication_style(self, user_id: int) -> CommunicationStyle:
        """
        Получить стиль общения пользователя из Redis.
        
        ТОЛЬКО чтение, без изменения существующих ключей.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Стиль общения пользователя
        """
        if not self.redis:
            return CommunicationStyle.UNKNOWN
        
        try:
            # Читаем стиль из Redis (отдельный ключ, не конфликтует с историей)
            style_key = f"{self.style_key_prefix}{user_id}"
            style_data = await self.redis.get(style_key)
            
            if style_data:
                # Если есть сохраненный стиль, возвращаем его
                try:
                    return CommunicationStyle(style_data.decode() if isinstance(style_data, bytes) else style_data)
                except ValueError:
                    return CommunicationStyle.UNKNOWN
            
            # Если стиля нет, пытаемся определить из истории (только чтение)
            history_key = f"curator_history:{user_id}"
            history_json = await self.redis.lrange(history_key, 0, -1)
            
            if history_json:
                # Анализируем последние сообщения пользователя
                user_messages = []
                for item in history_json[-5:]:  # Последние 5 сообщений
                    try:
                        msg = json.loads(item)
                        if msg.get("role") == "user":
                            user_messages.append(msg.get("text", ""))
                    except (json.JSONDecodeError, KeyError):
                        continue
                
                if user_messages:
                    # Определяем стиль по длине сообщений
                    avg_length = sum(len(msg) for msg in user_messages) / len(user_messages)
                    if avg_length < 30:
                        return CommunicationStyle.SHORT
                    elif avg_length > 100:
                        return CommunicationStyle.DETAILED
                    elif len(user_messages) >= 3:
                        return CommunicationStyle.FREQUENT
            
            return CommunicationStyle.UNKNOWN
        
        except Exception as e:
            logger.debug("Ошибка при получении стиля общения: %s", e)
            return CommunicationStyle.UNKNOWN
    
    def _is_greeting(self, question: str) -> bool:
        """
        Проверить, является ли вопрос простым приветствием.
        
        Args:
            question: Вопрос пользователя
            
        Returns:
            True, если это приветствие
        """
        question_lower = question.lower().strip()
        greetings = [
            "привет", "здравствуй", "здравствуйте", "добрый день",
            "добрый вечер", "доброе утро", "hi", "hello", "hey",
            "салют", "здарова", "доброго времени суток"
        ]
        return question_lower in greetings or any(
            question_lower.startswith(g) or question_lower == g
            for g in greetings
        )
    
    def _build_enhanced_system_prompt(
        self,
        context: QuestionContext,
        role: UserRole,
        style: CommunicationStyle,
        has_faqs: bool = True,
        is_greeting: bool = False,
    ) -> str:
        """
        Построить улучшенный системный промпт.
        
        Args:
            context: Контекст вопроса
            role: Роль пользователя
            style: Стиль общения
            
        Returns:
            Улучшенный системный промпт
        """
        # Базовый промпт (как в требованиях)
        if is_greeting:
            base_prompt = """Ты — живой AI-куратор доставки.

Пользователь поздоровался. Ответь дружелюбно и коротко, как живой человек.
Спроси, чем можешь помочь.

СТИЛЬ:
- 1–2 предложения
- дружелюбно, но без панибратства
- по делу
- без официоза"""
        elif has_faqs:
            base_prompt = """Ты — живой AI-куратор доставки.

Ты помогаешь курьерам и кураторам разобраться в правилах и ситуациях.
Ты говоришь как человек, спокойно и по делу.

ОГРАНИЧЕНИЯ:
- Отвечай ТОЛЬКО на основе предоставленного контекста
- НЕ выдумывай правил
- НЕ додумывай
- Если информации нет — честно скажи об этом

СТИЛЬ:
- 2–6 предложений
- сначала суть
- потом короткое объяснение
- при необходимости — рекомендация
- без официоза
- без морализаторства

ЕСЛИ ЕСТЬ РИСК ОШИБКИ:
- задай ОДИН уточняющий вопрос"""
        else:
            base_prompt = """Ты — живой AI-куратор доставки.

В базе знаний нет точного ответа на вопрос пользователя.
Ответь честно и по-человечески, что информации нет, и предложи обратиться к куратору.

СТИЛЬ:
- 2–3 предложения
- честно, без извинений
- предложи помощь куратора
- без официоза"""
        
        # Добавляем контекст вопроса
        context_hints = {
            QuestionContext.CAN_CANNOT: "Пользователь спрашивает про 'можно/нельзя'. Отвечай четко: можно или нельзя, и почему.",
            QuestionContext.WHAT_TO_DO: "Пользователь спрашивает 'что делать'. Дай конкретные шаги действий.",
            QuestionContext.ERROR_COMPLAINT: "Пользователь сообщает об ошибке или жалобе. Будь внимателен и конструктивен.",
            QuestionContext.GENERAL: "Общий вопрос. Отвечай по существу, но не слишком подробно.",
        }
        context_hint = context_hints.get(context, "")
        
        # Добавляем роль пользователя
        role_hints = {
            UserRole.COURIER: "Пользователь — курьер. Отвечай проще, практичнее, с примерами из работы.",
            UserRole.CURATOR: "Пользователь — куратор. Отвечай чуть системнее, но без канцелярита.",
            UserRole.UNKNOWN: "Роль пользователя не определена. Отвечай универсально.",
        }
        role_hint = role_hints.get(role, "")
        
        # Добавляем стиль общения
        style_hints = {
            CommunicationStyle.SHORT: "Пользователь пишет коротко. Отвечай тоже коротко, по делу.",
            CommunicationStyle.DETAILED: "Пользователь пишет развернуто. Можно отвечать чуть подробнее.",
            CommunicationStyle.FREQUENT: "Пользователь часто задает вопросы. Тон — спокойный помощник.",
            CommunicationStyle.UNKNOWN: "",
        }
        style_hint = style_hints.get(style, "")
        
        # Собираем улучшенный промпт
        enhanced_prompt = base_prompt
        
        if context_hint:
            enhanced_prompt += f"\n\nКОНТЕКСТ ВОПРОСА:\n{context_hint}"
        
        if role_hint:
            enhanced_prompt += f"\n\nРОЛЬ ПОЛЬЗОВАТЕЛЯ:\n{role_hint}"
        
        if style_hint:
            enhanced_prompt += f"\n\nСТИЛЬ ОБЩЕНИЯ:\n{style_hint}"
        
        return enhanced_prompt
    
    def _add_transition_phrases(self, answer: str, context: QuestionContext) -> str:
        """
        Добавить переходные фразы к ответу (если нужно).
        
        Добавляет ТОЛЬКО короткие фразы, не всегда.
        
        Args:
            answer: Базовый ответ
            context: Контекст вопроса
            
        Returns:
            Ответ с переходными фразами (если нужно)
        """
        # Переходные фразы (используются не всегда, только при необходимости)
        transition_phrases = [
            "Смотри, тут важно вот что:",
            "Коротко объясню:",
            "Тут есть нюанс:",
            "Лучше не рисковать:",
        ]
        
        # Определяем, нужна ли переходная фраза
        # Добавляем только если ответ длинный или сложный
        if len(answer) > 150 and context in (QuestionContext.CAN_CANNOT, QuestionContext.ERROR_COMPLAINT):
            phrase = random.choice(transition_phrases)
            # Добавляем фразу только если её ещё нет в ответе
            if phrase.lower() not in answer.lower():
                return f"{phrase}\n\n{answer}"
        
        return answer
    
    def _check_if_clarification_needed(
        self,
        question: str,
        answer: str,
        context: QuestionContext,
    ) -> Optional[str]:
        """
        Проверить, нужен ли уточняющий вопрос.
        
        Уточняющий вопрос задаётся ТОЛЬКО если:
        - ошибка может привести к жалобе
        - есть несколько трактовок правил
        - контекста недостаточно
        
        Args:
            question: Вопрос пользователя
            answer: Ответ бота
            context: Контекст вопроса
            
        Returns:
            Уточняющий вопрос или None
        """
        # Уточняющий вопрос нужен только в критических случаях
        if context != QuestionContext.CAN_CANNOT and context != QuestionContext.ERROR_COMPLAINT:
            return None
        
        # Проверяем, есть ли в ответе неопределенность
        uncertainty_keywords = [
            "возможно",
            "вероятно",
            "может быть",
            "скорее всего",
            "не уверен",
            "не знаю",
        ]
        
        answer_lower = answer.lower()
        has_uncertainty = any(keyword in answer_lower for keyword in uncertainty_keywords)
        
        # Проверяем, есть ли риск ошибки
        risk_keywords = [
            "жалоба",
            "нарушение",
            "штраф",
            "ответственность",
            "проблема",
        ]
        has_risk = any(keyword in question.lower() for keyword in risk_keywords)
        
        # Если есть неопределенность И риск — задаём уточняющий вопрос
        if has_uncertainty and has_risk:
            # Формируем уточняющий вопрос на основе контекста
            if "оставить" in question.lower() or "дверь" in question.lower():
                return "Подскажи, покупатель выбирал настройку 'оставить у двери'?"
            elif "звонок" in question.lower() or "дозвониться" in question.lower():
                return "Сколько попыток дозвона ты уже сделал?"
            elif "температур" in question.lower() or "холод" in question.lower():
                return "Товар был в термобоксе или без?"
        
        return None
    
    async def get_answer(
        self,
        question: str,
        user_id: Optional[int] = None,
    ) -> str:
        """
        Получить улучшенный ответ на вопрос.
        
        Использует все улучшения:
        - Анализ контекста
        - Определение роли
        - Память стиля
        - Улучшенный промпт
        - Переходные фразы
        - Уточняющие вопросы
        
        Args:
            question: Вопрос пользователя
            user_id: ID пользователя (опционально, для стиля и истории)
            
        Returns:
            Улучшенный ответ
        """
        try:
            # 1. Анализируем контекст вопроса
            context = self.analyze_question_context(question)
            
            # 2. Определяем роль пользователя
            role = self.detect_user_role(question)
            
            # 3. Получаем стиль общения (если user_id указан)
            style = CommunicationStyle.UNKNOWN
            if user_id:
                style = await self.get_communication_style(user_id)
            
            # 4. Получаем FAQ для контекста (если есть)
            try:
                faqs = await self.faq_repo.search_hybrid(question, limit=3)
            except Exception as e:
                logger.warning("Ошибка при поиске FAQ: %s. Продолжаем без FAQ.", e)
                faqs = []
            
            # 5. Если Groq доступен — генерируем улучшенный ответ
            if self.groq_enabled:
                try:
                    # Проверяем, является ли вопрос простым приветствием или общим вопросом
                    is_greeting = self._is_greeting(question)
                    has_faqs = faqs and len(faqs) > 0
                    
                    # Строим улучшенный промпт
                    system_prompt = self._build_enhanced_system_prompt(context, role, style, has_faqs=has_faqs, is_greeting=is_greeting)
                    
                    # Формируем контекст из FAQ (если есть)
                    if has_faqs:
                        context_text = "\n\n".join([
                            f"Вопрос: {faq.get('question', '')}\nОтвет: {faq.get('answer', '')}"
                            for faq in faqs[:2]
                        ])
                        user_prompt = f"""Контекст из базы знаний:
{context_text}

Вопрос пользователя:
{question}"""
                    else:
                        # Если FAQ нет, но это приветствие — отвечаем дружелюбно
                        if is_greeting:
                            user_prompt = f"""Пользователь написал: {question}

Ответь дружелюбно и коротко, как живой куратор. Спроси, чем можешь помочь."""
                        else:
                            # Если FAQ нет и это не приветствие — честно скажи об этом
                            user_prompt = f"""Вопрос пользователя:
{question}

В базе знаний нет точного ответа на этот вопрос. Ответь честно, что информации нет, и предложи обратиться к куратору, если нужна помощь."""
                    
                    # Генерируем ответ через Groq API
                    response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=0.7,
                        max_tokens=500,
                    )
                    
                    enhanced_answer = response.choices[0].message.content.strip()
                    
                    # 6. Добавляем переходные фразы (если нужно)
                    enhanced_answer = self._add_transition_phrases(enhanced_answer, context)
                    
                    # 7. Проверяем, нужен ли уточняющий вопрос
                    clarification = self._check_if_clarification_needed(question, enhanced_answer, context)
                    
                    if clarification:
                        # Добавляем уточняющий вопрос после краткого пояснения
                        return f"{enhanced_answer}\n\n{clarification}"
                    
                    return enhanced_answer
                
                except Exception as e:
                    logger.warning("Ошибка при форматировании через Groq: %s. Генерируем fallback ответ.", e)
                    # Fallback: генерируем простой ответ на основе контекста
                    is_greeting = self._is_greeting(question)
                    logger.info("Fallback: is_greeting=%s, faqs_count=%d", is_greeting, len(faqs) if faqs else 0)
                    if is_greeting:
                        logger.info("Fallback: возвращаем приветствие")
                        return "Привет! Чем могу помочь?"
                    elif faqs and len(faqs) > 0:
                        # Если есть FAQ, используем первый ответ
                        logger.info("Fallback: возвращаем ответ из FAQ")
                        return faqs[0].get('answer', 'Извините, не могу помочь с этим вопросом.')
                    else:
                        # Если FAQ нет, честно говорим об этом
                        logger.info("Fallback: возвращаем сообщение об отсутствии ответа")
                        return "В базе знаний нет точного ответа на этот вопрос. Обратитесь к куратору для помощи."
            
            # Если Groq недоступен — генерируем простой ответ
            is_greeting = self._is_greeting(question)
            if is_greeting:
                return "Привет! Чем могу помочь?"
            elif faqs and len(faqs) > 0:
                # Если есть FAQ, используем первый ответ
                return faqs[0].get('answer', 'Извините, не могу помочь с этим вопросом.')
            else:
                # Если FAQ нет, честно говорим об этом
                return "В базе знаний нет точного ответа на этот вопрос. Обратитесь к куратору для помощи."
        
        except Exception as e:
            logger.error("Ошибка при получении улучшенного ответа: %s", e, exc_info=True)
            # В случае ошибки возвращаем базовый ответ
            try:
                return await self.base_service.get_answer(question)
            except Exception:
                return "Произошла ошибка. Попробуйте переформулировать вопрос."
