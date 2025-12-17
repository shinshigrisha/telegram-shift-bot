import re
import logging
from datetime import datetime

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.states.setup_states import SetupStates
from src.services.group_service import GroupService  # type: ignore


logger = logging.getLogger(__name__)
router = Router()

SLOT_PATTERN = r"^(\d{1,2}:\d{2})-(\d{1,2}:\d{2}):(\d+)$"


@router.message(StateFilter(SetupStates.waiting_for_slots))
async def process_slots_input(
    message: Message,
    state: FSMContext,
    group_service: GroupService,
) -> None:
    """Обработка ввода слотов."""
    logger.info("Processing slots input: %s", message.text)
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
                f"✅ Настройки группы <b>{data['group_name']}</b> сохранены!\n\n"
                f"⏰ Время закрытия опроса: 19:00\n"
                f"📋 Слоты:\n{slots_text}"
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
                        f"✅ Настройки группы <b>{data['group_name']}</b> сохранены!\n\n"
                        f"⏰ Время закрытия опроса: 19:00\n"
                        f"📋 Слоты:\n{slots_text}"
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


