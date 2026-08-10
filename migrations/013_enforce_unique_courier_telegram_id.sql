-- Telegram-аккаунт курьера должен быть привязан только к одной карточке.
-- При старых дублях сохраняем все карточки и отвязываем менее актуальные.

WITH ranked_bindings AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY telegram_user_id
            ORDER BY is_active DESC, updated_at DESC NULLS LAST, id DESC
        ) AS binding_rank
    FROM group_members
    WHERE telegram_user_id IS NOT NULL
)
UPDATE group_members AS member
SET telegram_user_id = NULL,
    username = NULL,
    updated_at = CURRENT_TIMESTAMP
FROM ranked_bindings AS binding
WHERE member.id = binding.id
  AND binding.binding_rank > 1;

DROP INDEX IF EXISTS idx_group_members_group_telegram_unique;

CREATE UNIQUE INDEX IF NOT EXISTS idx_group_members_telegram_user_unique
    ON group_members (telegram_user_id)
    WHERE telegram_user_id IS NOT NULL;
