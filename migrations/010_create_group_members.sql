-- Реестр сотрудников по группам ЗИЗ

CREATE TABLE IF NOT EXISTS group_members (
    id SERIAL PRIMARY KEY,
    group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    full_name VARCHAR(255) NOT NULL,
    telegram_user_id BIGINT,
    username VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (group_id, full_name)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_group_members_group_telegram_unique
    ON group_members (group_id, telegram_user_id)
    WHERE telegram_user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_group_members_group_id ON group_members (group_id);

CREATE OR REPLACE FUNCTION update_group_members_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_group_members_updated_at ON group_members;

CREATE TRIGGER trigger_update_group_members_updated_at
    BEFORE UPDATE ON group_members
    FOR EACH ROW
    EXECUTE FUNCTION update_group_members_updated_at();
