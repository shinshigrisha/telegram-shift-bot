"""
Шаблоны замечаний для курьеров.

Этот модуль содержит различные варианты текстов замечаний,
которые бот отправляет курьерам при проверке слотов и опросов.
"""

import random
from typing import List, Dict, Optional
from datetime import date


class WarningTemplates:
    """Класс с шаблонами замечаний для разных ситуаций."""
    
    # Заголовки замечаний
    HEADERS = [
        "⚠️ <b>Замечания по опросу {group_name} на {date}</b>",
        "📋 <b>Проверка записи на смену {group_name} ({date})</b>",
        "🔔 <b>Напоминание: опрос {group_name} на {date}</b>",
        "⚡ <b>Требуется внимание: {group_name} на {date}</b>",
        "📢 <b>Важно: запись на смену {group_name} ({date})</b>",
    ]
    
    # Замечания для незаполненных слотов
    UNDERFILLED_SLOTS_INTROS = [
        "\n📉 <b>Незаполненные слоты:</b>",
        "\n⏰ <b>Слоты, требующие внимания:</b>",
        "\n📊 <b>Слоты с нехваткой курьеров:</b>",
        "\n⚠️ <b>Слоты, которые нужно заполнить:</b>",
    ]
    
    # Варианты текста для незаполненных слотов (без информации о количестве)
    UNDERFILLED_SLOT_TEMPLATES = [
        "• {start_time}-{end_time}",
        "• {start_time} до {end_time}",
        "• С {start_time} до {end_time}",
    ]
    
    # Замечания для неотметившихся курьеров
    NON_VOTERS_INTROS = [
        "\n👥 <b>Не отметились:</b>",
        "\n❌ <b>Курьеры, которые еще не проголосовали:</b>",
        "\n⏳ <b>Ожидаем отметку от:</b>",
        "\n📝 <b>Требуется отметка от следующих курьеров:</b>",
        "\n🔔 <b>Напоминание для курьеров:</b>",
    ]
    
    # Дополнительные сообщения после списка неотметившихся
    NON_VOTERS_FOOTERS = [
        "\n\n💬 Пожалуйста, отметьтесь в опросе до закрытия записи!",
        "\n\n⏰ Не забудьте проголосовать до окончания записи!",
        "\n\n📌 Важно: отметьтесь в опросе, чтобы мы могли правильно распределить смены.",
        "\n\n✅ Пожалуйста, выберите удобный для вас слот в опросе.",
        "\n\n🚨 Внимание: запись закрывается в 19:00, не забудьте отметить свой слот!",
    ]
    
    # Финальные напоминания (для 18:30)
    FINAL_REMINDERS = [
        "\n\n⏰ <b>До закрытия записи осталось 30 минут!</b>",
        "\n\n🚨 <b>ФИНАЛЬНОЕ НАПОМИНАНИЕ: до конца записи 30 минут!</b>",
        "\n\n⏳ <b>Последний шанс: запись закрывается через 30 минут!</b>",
        "\n\n🔔 <b>Срочно: до закрытия опроса осталось 30 минут!</b>",
    ]
    
    # Общие напоминания о времени
    TIME_REMINDERS = {
        15: [
            "\n\n⏰ До закрытия записи осталось 4 часа. Пожалуйста, отметьтесь!",
            "\n\n📅 Напоминание: до закрытия опроса осталось 4 часа.",
        ],
        17: [
            "\n\n⏰ До закрытия записи осталось 2 часа. Не забудьте отметить свой слот!",
            "\n\n📅 Напоминание: до закрытия опроса осталось 2 часа.",
        ],
        18: [
            "\n\n⏰ До закрытия записи остался 1 час. Срочно отметьтесь!",
            "\n\n📅 Напоминание: до закрытия опроса остался 1 час.",
        ],
    }
    
    # Сообщения когда все хорошо (для финального напоминания)
    ALL_GOOD_MESSAGES = [
        "\n\n✅ Все слоты заполнены, все курьеры отметились! Отлично!",
        "\n\n✅ Все в порядке: все слоты заполнены, все отметились.",
        "\n\n✅ Статус: все слоты заполнены корректно, все курьеры отметились.",
    ]
    
    @staticmethod
    def get_random_header(group_name: str, poll_date: date) -> str:
        """Получить случайный заголовок замечания."""
        template = random.choice(WarningTemplates.HEADERS)
        return template.format(
            group_name=group_name,
            date=poll_date.strftime('%d.%m.%Y')
        )
    
    @staticmethod
    def get_underfilled_slots_intro() -> str:
        """Получить вступление для незаполненных слотов."""
        return random.choice(WarningTemplates.UNDERFILLED_SLOTS_INTROS)
    
    @staticmethod
    def format_underfilled_slot(
        start_time: str,
        end_time: str,
        needed: int,
        current: int,
        max_users: int,
        courier_word: str
    ) -> str:
        """Отформатировать информацию о незаполненном слоте (только время, без количества)."""
        template = random.choice(WarningTemplates.UNDERFILLED_SLOT_TEMPLATES)
        return template.format(
            start_time=start_time,
            end_time=end_time
        )
    
    @staticmethod
    def get_non_voters_intro() -> str:
        """Получить вступление для неотметившихся курьеров."""
        return random.choice(WarningTemplates.NON_VOTERS_INTROS)
    
    @staticmethod
    def get_non_voters_footer() -> str:
        """Получить дополнительное сообщение после списка неотметившихся."""
        return random.choice(WarningTemplates.NON_VOTERS_FOOTERS)
    
    @staticmethod
    def get_final_reminder() -> str:
        """Получить финальное напоминание (для 18:30)."""
        return random.choice(WarningTemplates.FINAL_REMINDERS)
    
    @staticmethod
    def get_time_reminder(hour: int) -> Optional[str]:
        """Получить напоминание о времени в зависимости от часа."""
        if hour in WarningTemplates.TIME_REMINDERS:
            return random.choice(WarningTemplates.TIME_REMINDERS[hour])
        return None
    
    @staticmethod
    def build_warning_message(
        group_name: str,
        poll_date: date,
        underfilled_slots: List[Dict],
        non_voters_mentions: List[str],
        current_hour: Optional[int] = None,
        is_final: bool = False,
        pluralize_courier_func=None
    ) -> str:
        """
        Построить полное сообщение с замечаниями.
        
        Args:
            group_name: Название группы
            poll_date: Дата опроса
            underfilled_slots: Список словарей с информацией о незаполненных слотах
            non_voters_mentions: Список HTML-тэгов для неотметившихся курьеров
            current_hour: Текущий час (для добавления напоминания о времени)
            is_final: Флаг финального напоминания (18:30)
            pluralize_courier_func: Функция для правильного склонения слова "курьер"
        
        Returns:
            Полное сообщение с замечаниями
        """
        parts = [WarningTemplates.get_random_header(group_name, poll_date)]
        
        # Проверяем, есть ли проблемы
        has_problems = bool(underfilled_slots or non_voters_mentions)
        
        # Добавляем информацию о незаполненных слотах
        if underfilled_slots:
            parts.append(WarningTemplates.get_underfilled_slots_intro())
            for slot_info in underfilled_slots:
                slot = slot_info['slot']
                needed = slot_info['needed']
                start_time = slot.start_time.strftime('%H:%M') if hasattr(slot.start_time, 'strftime') else str(slot.start_time)
                end_time = slot.end_time.strftime('%H:%M') if hasattr(slot.end_time, 'strftime') else str(slot.end_time)
                
                courier_word = "курьера" if needed == 1 else "курьеров"
                if pluralize_courier_func:
                    courier_word = pluralize_courier_func(needed)
                
                slot_text = WarningTemplates.format_underfilled_slot(
                    start_time=start_time,
                    end_time=end_time,
                    needed=needed,
                    current=slot.current_users,
                    max_users=slot.max_users,
                    courier_word=courier_word
                )
                parts.append(slot_text)
        
        # Добавляем информацию о неотметившихся курьерах
        if non_voters_mentions:
            parts.append(WarningTemplates.get_non_voters_intro())
            parts.append(" ".join(non_voters_mentions))
            parts.append(WarningTemplates.get_non_voters_footer())
        
        # Если нет проблем, но это финальное напоминание - добавляем сообщение что все хорошо
        if not has_problems and is_final:
            parts.append(random.choice(WarningTemplates.ALL_GOOD_MESSAGES))
        
        # Добавляем финальное напоминание или напоминание о времени
        if is_final:
            parts.append(WarningTemplates.get_final_reminder())
        elif current_hour:
            time_reminder = WarningTemplates.get_time_reminder(current_hour)
            if time_reminder:
                parts.append(time_reminder)
        
        return "\n".join(parts)

