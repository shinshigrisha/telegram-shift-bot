"""
Обработчики сотрудников групп.
"""
import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.services.group_member_service import GroupMemberService
from src.services.group_service import GroupService
from src.states.admin_panel_states import AdminPanelStates
from src.utils.admin_keyboards import get_back_keyboard
from src.utils.auth import require_admin_callback
from src.utils.group_formatters import clean_group_name_for_display
from src.utils.telegram_helpers import safe_answer_callback, safe_edit_message

logger = logging.getLogger(__name__)
router = Router()


def _build_groups_keyboard(groups: list[dict], action: str) -> InlineKeyboardMarkup:
    keyboard = []
    for group in groups:
        name = clean_group_name_for_display(group.get("name", f"Группа {group.get('id', '?')}"))
        keyboard.append([
            InlineKeyboardButton(
                text=name,
                callback_data=f"admin:employees:group:{action}:{group['id']}",
            )
        ])
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin:employees_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def _build_members_keyboard(members: list[dict], group_id: int) -> InlineKeyboardMarkup:
    keyboard = []
    for member in members:
        title = member.get("full_name", f"Сотрудник {member['id']}")
        keyboard.append([
            InlineKeyboardButton(
                text=title,
                callback_data=f"admin:employees:delete_member:{group_id}:{member['id']}",
            )
        ])
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin:employees_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def _build_members_action_keyboard(members: list[dict], action: str) -> InlineKeyboardMarkup:
    keyboard = []
    for member in members:
        title = member.get("full_name", f"Сотрудник {member['id']}")
        keyboard.append([
            InlineKeyboardButton(
                text=title,
                callback_data=f"admin:employees:{action}_member:{member['id']}",
            )
        ])
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin:employees_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def _format_bindings_text(group_name: str, members: list[dict]) -> str:
    if not members:
        return f"🔗 <b>{group_name}</b>\n\nСписок сотрудников пуст."

    linked = [member for member in members if member.get("telegram_user_id")]
    unlinked = [member for member in members if not member.get("telegram_user_id")]

    lines = [
        f"🔗 <b>{group_name}</b>",
        "",
        f"Всего сотрудников: <b>{len(members)}</b>",
        f"Привязаны к Telegram: <b>{len(linked)}</b>",
        f"Не привязаны: <b>{len(unlinked)}</b>",
        "",
    ]

    if linked:
        lines.append("<b>Привязаны:</b>")
        for member in linked[:25]:
            username = member.get("username") or "без username"
            lines.append(
                f"• {member.get('full_name', 'Без имени')} — "
                f"<code>{member.get('telegram_user_id')}</code> ({username})"
            )
        if len(linked) > 25:
            lines.append(f"... и еще {len(linked) - 25}")
        lines.append("")

    if unlinked:
        lines.append("<b>Не привязаны:</b>")
        for member in unlinked[:25]:
            lines.append(f"• {member.get('full_name', 'Без имени')}")
        if len(unlinked) > 25:
            lines.append(f"... и еще {len(unlinked) - 25}")
        lines.append("")

    lines.append(
        "💡 Привязка появляется после голосования сотрудника в опросе "
        "или если запись уже была связана ранее."
    )
    return "\n".join(lines)


@router.callback_query(lambda c: c.data == "admin:employees:add")
@require_admin_callback
async def callback_employee_add_start(
    callback: CallbackQuery,
    state: FSMContext,
    group_service: GroupService,
) -> None:
    groups = await group_service.get_all_groups()
    if not groups:
        await safe_edit_message(
            callback.message,
            "❌ Нет зарегистрированных групп.",
            reply_markup=get_back_keyboard("admin:employees_menu"),
        )
        await safe_answer_callback(callback)
        return

    await state.update_data(employee_action="add")
    await state.set_state(AdminPanelStates.waiting_for_employee_group)
    await safe_edit_message(
        callback.message,
        "👥 <b>Добавление сотрудника</b>\n\nВыберите группу ЗИЗ:",
        reply_markup=_build_groups_keyboard(groups, "add"),
    )
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data == "admin:employees:list")
@require_admin_callback
async def callback_employee_list_start(
    callback: CallbackQuery,
    state: FSMContext,
    group_service: GroupService,
) -> None:
    groups = await group_service.get_all_groups()
    if not groups:
        await safe_edit_message(
            callback.message,
            "❌ Нет зарегистрированных групп.",
            reply_markup=get_back_keyboard("admin:employees_menu"),
        )
        await safe_answer_callback(callback)
        return

    await state.update_data(employee_action="list")
    await state.set_state(AdminPanelStates.waiting_for_employee_group)
    await safe_edit_message(
        callback.message,
        "👥 <b>Список сотрудников</b>\n\nВыберите группу ЗИЗ:",
        reply_markup=_build_groups_keyboard(groups, "list"),
    )
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data == "admin:employees:bindings")
@require_admin_callback
async def callback_employee_bindings_start(
    callback: CallbackQuery,
    state: FSMContext,
    group_service: GroupService,
) -> None:
    groups = await group_service.get_all_groups()
    if not groups:
        await safe_edit_message(
            callback.message,
            "❌ Нет зарегистрированных групп.",
            reply_markup=get_back_keyboard("admin:employees_menu"),
        )
        await safe_answer_callback(callback)
        return

    await state.update_data(employee_action="bindings")
    await state.set_state(AdminPanelStates.waiting_for_employee_group)
    await safe_edit_message(
        callback.message,
        "🔗 <b>Статус привязки Telegram</b>\n\nВыберите группу ЗИЗ:",
        reply_markup=_build_groups_keyboard(groups, "bindings"),
    )
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data == "admin:employees:rename")
@require_admin_callback
async def callback_employee_rename_start(
    callback: CallbackQuery,
    state: FSMContext,
    group_service: GroupService,
) -> None:
    groups = await group_service.get_all_groups()
    if not groups:
        await safe_edit_message(
            callback.message,
            "❌ Нет зарегистрированных групп.",
            reply_markup=get_back_keyboard("admin:employees_menu"),
        )
        await safe_answer_callback(callback)
        return

    await state.update_data(employee_action="rename")
    await state.set_state(AdminPanelStates.waiting_for_employee_group)
    await safe_edit_message(
        callback.message,
        "✏️ <b>Переименование сотрудника</b>\n\nВыберите группу ЗИЗ:",
        reply_markup=_build_groups_keyboard(groups, "rename"),
    )
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data == "admin:employees:move")
@require_admin_callback
async def callback_employee_move_start(
    callback: CallbackQuery,
    state: FSMContext,
    group_service: GroupService,
) -> None:
    groups = await group_service.get_all_groups()
    if not groups:
        await safe_edit_message(
            callback.message,
            "❌ Нет зарегистрированных групп.",
            reply_markup=get_back_keyboard("admin:employees_menu"),
        )
        await safe_answer_callback(callback)
        return

    await state.update_data(employee_action="move")
    await state.set_state(AdminPanelStates.waiting_for_employee_group)
    await safe_edit_message(
        callback.message,
        "🔄 <b>Перенос сотрудника</b>\n\nСначала выберите текущую группу ЗИЗ:",
        reply_markup=_build_groups_keyboard(groups, "move"),
    )
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data == "admin:employees:delete")
@require_admin_callback
async def callback_employee_delete_start(
    callback: CallbackQuery,
    state: FSMContext,
    group_service: GroupService,
) -> None:
    groups = await group_service.get_all_groups()
    if not groups:
        await safe_edit_message(
            callback.message,
            "❌ Нет зарегистрированных групп.",
            reply_markup=get_back_keyboard("admin:employees_menu"),
        )
        await safe_answer_callback(callback)
        return

    await state.update_data(employee_action="delete")
    await state.set_state(AdminPanelStates.waiting_for_employee_group)
    await safe_edit_message(
        callback.message,
        "🗑️ <b>Удаление сотрудника</b>\n\nВыберите группу ЗИЗ:",
        reply_markup=_build_groups_keyboard(groups, "delete"),
    )
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:employees:group:"))
@require_admin_callback
async def callback_employee_group_action(
    callback: CallbackQuery,
    state: FSMContext,
    group_service: GroupService,
    group_member_service: GroupMemberService,
) -> None:
    _, _, _, action, group_id_text = callback.data.split(":")
    group_id = int(group_id_text)
    group = await group_service.get_group_by_id(group_id)
    if not group:
        await safe_edit_message(
            callback.message,
            "❌ Группа не найдена.",
            reply_markup=get_back_keyboard("admin:employees_menu"),
        )
        await safe_answer_callback(callback)
        return

    await state.update_data(group_id=group_id)

    if action == "transfer_to":
        data = await state.get_data()
        member_id = data.get("member_id")
        member = await group_member_service.repository.get_by_id(member_id)
        if not member:
            await state.clear()
            await safe_edit_message(
                callback.message,
                "❌ Сотрудник не найден.",
                reply_markup=get_back_keyboard("admin:employees_menu"),
            )
        else:
            success = await group_member_service.move_member(member_id=member_id, group_id=group_id)
            text = (
                f"✅ Сотрудник <b>{member.get('full_name')}</b> перенесен в группу <b>{group.get('name')}</b>."
                if success else "❌ Не удалось перенести сотрудника."
            )
            await state.clear()
            await safe_edit_message(
                callback.message,
                text,
                reply_markup=get_back_keyboard("admin:employees_menu"),
            )
    elif action == "add":
        await state.set_state(AdminPanelStates.waiting_for_employee_name)
        await safe_edit_message(
            callback.message,
            f"👥 <b>Добавление сотрудника</b>\n\nГруппа: <b>{group['name']}</b>\n\n"
            "Введите Фамилию и Имя одним сообщением.\n"
            "Пример: <code>Иванов Иван</code>",
            reply_markup=get_back_keyboard("admin:employees_menu"),
        )
    elif action == "list":
        active_members = await group_member_service.get_group_members(group_id, active_only=True)
        inactive_members = await group_member_service.get_group_members(group_id, active_only=False)
        inactive_members = [member for member in inactive_members if not member.get("is_active", True)]
        if not active_members and not inactive_members:
            text = f"📋 <b>{group['name']}</b>\n\nСписок сотрудников пуст."
        else:
            lines = [f"📋 <b>{group['name']}</b>", ""]
            if active_members:
                lines.append("<b>Активные:</b>")
                lines.extend(f"• {member['full_name']}" for member in active_members)
                lines.append("")
            if inactive_members:
                lines.append("<b>Удалены из группы:</b>")
                lines.extend(f"• {member['full_name']}" for member in inactive_members)
            text = "\n".join(lines)
        await state.clear()
        await safe_edit_message(
            callback.message,
            text,
            reply_markup=get_back_keyboard("admin:employees_menu"),
        )
    elif action == "bindings":
        members = await group_member_service.get_group_members(group_id)
        text = _format_bindings_text(group["name"], members)
        await state.clear()
        await safe_edit_message(
            callback.message,
            text,
            reply_markup=get_back_keyboard("admin:employees_menu"),
        )
    elif action == "rename":
        members = await group_member_service.get_group_members(group_id)
        if not members:
            await state.clear()
            await safe_edit_message(
                callback.message,
                f"📋 <b>{group['name']}</b>\n\nСписок сотрудников пуст.",
                reply_markup=get_back_keyboard("admin:employees_menu"),
            )
        else:
            await safe_edit_message(
                callback.message,
                f"✏️ <b>{group['name']}</b>\n\nВыберите сотрудника для переименования:",
                reply_markup=_build_members_action_keyboard(members, "rename"),
            )
    elif action == "move":
        members = await group_member_service.get_group_members(group_id)
        if not members:
            await state.clear()
            await safe_edit_message(
                callback.message,
                f"📋 <b>{group['name']}</b>\n\nСписок сотрудников пуст.",
                reply_markup=get_back_keyboard("admin:employees_menu"),
            )
        else:
            await safe_edit_message(
                callback.message,
                f"🔄 <b>{group['name']}</b>\n\nВыберите сотрудника для переноса:",
                reply_markup=_build_members_action_keyboard(members, "move"),
            )
    else:
        members = await group_member_service.get_group_members(group_id)
        if not members:
            await state.clear()
            await safe_edit_message(
                callback.message,
                f"📋 <b>{group['name']}</b>\n\nСписок сотрудников пуст.",
                reply_markup=get_back_keyboard("admin:employees_menu"),
            )
        else:
            await safe_edit_message(
                callback.message,
                f"🗑️ <b>{group['name']}</b>\n\nВыберите сотрудника для удаления:",
                reply_markup=_build_members_keyboard(members, group_id),
            )

    await safe_answer_callback(callback)


@router.message(AdminPanelStates.waiting_for_employee_name)
async def process_employee_name(
    message: Message,
    state: FSMContext,
    group_member_service: GroupMemberService,
    group_service: GroupService,
) -> None:
    if message.text and message.text.lower() == "отмена":
        await state.clear()
        await message.answer("❌ Добавление сотрудника отменено", parse_mode="HTML")
        return

    full_name = (message.text or "").strip()
    if not full_name:
        await message.answer("❌ ФИО не может быть пустым.", parse_mode="HTML")
        return

    data = await state.get_data()
    group_id = data.get("group_id")
    group = await group_service.get_group_by_id(group_id)
    if not group:
        await state.clear()
        await message.answer("❌ Группа не найдена.", parse_mode="HTML")
        return

    member = await group_member_service.add_member(group_id=group_id, full_name=full_name)
    await state.clear()
    await message.answer(
        f"✅ Сотрудник <b>{member['full_name']}</b> добавлен в группу <b>{group['name']}</b>.",
        parse_mode="HTML",
        reply_markup=get_back_keyboard("admin:employees_menu"),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("admin:employees:rename_member:"))
@require_admin_callback
async def callback_rename_member_select(
    callback: CallbackQuery,
    state: FSMContext,
    group_member_service: GroupMemberService,
) -> None:
    member_id = int(callback.data.split(":")[-1])
    member = await group_member_service.repository.get_by_id(member_id)
    if not member:
        await safe_edit_message(
            callback.message,
            "❌ Сотрудник не найден.",
            reply_markup=get_back_keyboard("admin:employees_menu"),
        )
        await safe_answer_callback(callback)
        return

    await state.update_data(member_id=member_id)
    await state.set_state(AdminPanelStates.waiting_for_employee_rename)
    await safe_edit_message(
        callback.message,
        f"✏️ <b>Переименование сотрудника</b>\n\n"
        f"Текущее имя: <b>{member.get('full_name')}</b>\n\n"
        f"Введите новое <b>Имя и Фамилию</b> одним сообщением.",
        reply_markup=get_back_keyboard("admin:employees_menu"),
    )
    await safe_answer_callback(callback)


@router.message(AdminPanelStates.waiting_for_employee_rename)
async def process_employee_rename(
    message: Message,
    state: FSMContext,
    group_member_service: GroupMemberService,
) -> None:
    if message.text and message.text.lower() == "отмена":
        await state.clear()
        await message.answer("❌ Переименование сотрудника отменено", parse_mode="HTML")
        return

    full_name = (message.text or "").strip()
    if not full_name:
        await message.answer("❌ ФИО не может быть пустым.", parse_mode="HTML")
        return

    data = await state.get_data()
    member_id = data.get("member_id")
    success = await group_member_service.rename_member(member_id=member_id, full_name=full_name)
    await state.clear()
    text = f"✅ Сотрудник переименован в <b>{full_name}</b>." if success else "❌ Сотрудник не найден."
    await message.answer(text, parse_mode="HTML", reply_markup=get_back_keyboard("admin:employees_menu"))


@router.callback_query(lambda c: c.data and c.data.startswith("admin:employees:move_member:"))
@require_admin_callback
async def callback_move_member_select(
    callback: CallbackQuery,
    state: FSMContext,
    group_service: GroupService,
    group_member_service: GroupMemberService,
) -> None:
    member_id = int(callback.data.split(":")[-1])
    member = await group_member_service.repository.get_by_id(member_id)
    if not member:
        await safe_edit_message(
            callback.message,
            "❌ Сотрудник не найден.",
            reply_markup=get_back_keyboard("admin:employees_menu"),
        )
        await safe_answer_callback(callback)
        return

    groups = await group_service.get_all_groups()
    current_group_id = member.get("group_id")
    target_groups = [group for group in groups if group.get("id") != current_group_id]
    if not target_groups:
        await safe_edit_message(
            callback.message,
            "❌ Нет другой группы для переноса.",
            reply_markup=get_back_keyboard("admin:employees_menu"),
        )
        await safe_answer_callback(callback)
        return

    await state.update_data(member_id=member_id)
    await state.set_state(AdminPanelStates.waiting_for_employee_transfer_group)
    await safe_edit_message(
        callback.message,
        f"🔄 <b>Перенос сотрудника</b>\n\n"
        f"Сотрудник: <b>{member.get('full_name')}</b>\n"
        f"Выберите новую группу:",
        reply_markup=_build_groups_keyboard(target_groups, "transfer_to"),
    )
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:employees:delete_member:"))
@require_admin_callback
async def callback_delete_member(
    callback: CallbackQuery,
    group_member_service: GroupMemberService,
) -> None:
    _, _, _, _, member_id_text = callback.data.split(":")
    member_id = int(member_id_text)
    success = await group_member_service.delete_member(member_id)
    text = "✅ Сотрудник удален из группы и отмечен как неактивный." if success else "❌ Сотрудник не найден."
    await safe_edit_message(
        callback.message,
        text,
        reply_markup=get_back_keyboard("admin:employees_menu"),
    )
    await safe_answer_callback(callback)
