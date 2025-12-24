import re
import logging
from datetime import datetime

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.enums import ChatType

from src.states.setup_states import SetupStates
from src.services.group_service import GroupService


logger = logging.getLogger(__name__)
router = Router()

SLOT_PATTERN = r"^(\d{1,2}:\d{2})-(\d{1,2}:\d{2}):(\d+)$"


@router.message(StateFilter(SetupStates.waiting_for_group_name))
async def process_group_name(
    message: Message,
    state: FSMContext,
    group_service: GroupService,
) -> None:
    """Обработка ввода названия группы для настройки слотов."""
    # Обрабатываем только личные сообщения
    if message.chat.type != ChatType.PRIVATE:
        return
    
    # Проверяем, что сообщение содержит текст
    if not message.text:
        await message.answer(
            "❌ Пожалуйста, отправьте текстовое сообщение с названием группы\n\n"
            "Для отмены введите: <code>отмена</code>"
        )
        return
    
    # Проверяем на отмену
    if message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Отменено")
        return
    
    group_name = message.text.strip()
    group = await group_service.get_group_by_name(group_name)

    if not group:
        await message.answer(
            f"❌ Группа {group_name} не найдена\n\n"
            "Введите название группы еще раз:"
        )
        return

    await state.set_state(SetupStates.waiting_for_slots)
    await state.update_data(group_id=group.id, group_name=group_name)

    # Показываем текущие настройки, если они есть
    current_slots = group.get_slots_config()
    current_slots_text = ""
    if current_slots:
        current_slots_text = (
            f"\n📋 <b>Текущие настройки слотов для {group_name}:</b>\n" +
            "\n".join(
                f"• {s['start']}-{s['end']} (лимит: {s['limit']})"
                for s in current_slots
            ) + "\n\n"
        )
    else:
        current_slots_text = "⚠️ <b>Слоты еще не настроены для этой группы.</b>\n\n"
    
    await message.answer(
        f"⚙️ <b>Настройка группы {group_name}</b>\n\n"
        f"{current_slots_text}"
        "💡 <b>Важно:</b> Каждая группа имеет свои <b>индивидуальные настройки</b> слотов.\n"
        f"Настройки для <b>{group_name}</b> не влияют на другие группы.\n\n"
        "Введите слоты в формате:\n"
        "<code>время_начала-время_конца:лимит</code>\n\n"
        "<b>Примеры:</b>\n"
        "• <code>07:30-19:30:3</code> - с 07:30 до 19:30, лимит 3 человека\n"
        "• <code>08:00-20:00:2</code> - с 08:00 до 20:00, лимит 2 человека\n"
        "• <code>10:00-22:00:1</code> - с 10:00 до 22:00, лимит 1 человек\n\n"
        "Можно вводить несколько слотов сразу (каждый с новой строки).\n"
        "Когда закончите, отправьте: <b>готово</b>"
    )


@router.message(StateFilter(SetupStates.waiting_for_slots))
async def process_slots_input(
    message: Message,
    state: FSMContext,
    group_service: GroupService,
) -> None:
    """Обработка ввода слотов."""
    # Обрабатываем только личные сообщения
    if message.chat.type != ChatType.PRIVATE:
        return
    
    logger.info("Processing slots input: %s", message.text)
    
    # Проверяем, что сообщение содержит текст
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте текстовое сообщение")
        return
    
    text = message.text.strip()

    # Проверяем на "готово" (без учета регистра)
    if text.lower() == "готово":
        data = await state.get_data()
        slots = data.get("slots", [])

        if not slots:
            await message.answer("❌ Не добавлено ни одного слота")
            return

        # Сохраняем настройки
        success = await group_service.update_group_slots(
            data["group_id"],
            slots,
        )

        if success:
            slots_text = "\n".join(
                f"{i + 1}. {s['start']}-{s['end']} (лимит: {s['limit']})"
                for i, s in enumerate(slots)
            )

            await message.answer(
                f"✅ <b>Настройки группы {data['group_name']} сохранены!</b>\n\n"
                f"⏰ Время закрытия опроса: 19:00\n"
                f"📋 Слоты:\n{slots_text}\n\n"
                f"💡 <b>Важно:</b> Эти настройки применяются только к группе <b>{data['group_name']}</b>.\n"
                f"Другие группы имеют свои индивидуальные настройки слотов."
            )
        else:
            await message.answer("❌ Ошибка при сохранении настроек")

        await state.clear()
        return

    # Обрабатываем многострочный ввод
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    processed_count = 0
    errors = []
    data = await state.get_data()
    slots = data.get("slots", [])

    for line in lines:
        line_lower = line.lower()
        if line_lower == "готово":
            # Если встретили "готово" в середине, обрабатываем накопленные слоты
            if slots:
                success = await group_service.update_group_slots(
                    data["group_id"],
                    slots,
                )
                if success:
                    slots_text = "\n".join(
                        f"{i + 1}. {s['start']}-{s['end']} (лимит: {s['limit']})"
                        for i, s in enumerate(slots)
                    )
                    await message.answer(
                        f"✅ <b>Настройки группы {data['group_name']} сохранены!</b>\n\n"
                        f"⏰ Время закрытия опроса: 19:00\n"
                        f"📋 Слоты:\n{slots_text}\n\n"
                        f"💡 <b>Важно:</b> Эти настройки применяются только к группе <b>{data['group_name']}</b>.\n"
                        f"Другие группы имеют свои индивидуальные настройки слотов."
                    )
                else:
                    await message.answer("❌ Ошибка при сохранении настроек")
                await state.clear()
                return
            continue

        # Проверяем формат слота
        match = re.match(SLOT_PATTERN, line)
        if not match:
            errors.append(f"❌ Неверный формат: {line}")
            continue

        start_time, end_time, limit = match.groups()

        # Валидация времени
        try:
            datetime.strptime(start_time, "%H:%M")
            datetime.strptime(end_time, "%H:%M")
        except ValueError:
            errors.append(f"❌ Неверный формат времени в строке: {line}")
            continue

        # Валидация лимита
        try:
            limit_int = int(limit)
            if not 1 <= limit_int <= 20:
                raise ValueError
        except ValueError:
            errors.append(f"❌ Лимит должен быть числом от 1 до 20 в строке: {line}")
            continue

        # Добавляем слот
        slot_data = {
            "start": start_time,
            "end": end_time,
            "limit": limit_int,
        }

        slots.append(slot_data)
        processed_count += 1

    # Обновляем состояние с новыми слотами
    await state.update_data(slots=slots)

    # Формируем ответ
    response_parts = []
    if processed_count > 0:
        response_parts.append(
            f"✅ Добавлено слотов: {processed_count}\n"
            f"Всего слотов: {len(slots)}"
        )
    if errors:
        response_parts.append("\n".join(errors))
    if not processed_count and not errors:
        response_parts.append(
            "❌ Неверный формат. Используйте:\n"
            "время_начала-время_конца:лимит\n"
            "Пример: 07:30-19:30:3"
        )
    else:
        response_parts.append("\n\nДобавьте следующий слот или отправьте <b>готово</b>")

    await message.answer("\n".join(response_parts))


