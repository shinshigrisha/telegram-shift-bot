DO $$
BEGIN
    IF to_regclass('public.group_members') IS NOT NULL THEN
        EXECUTE 'TRUNCATE TABLE group_members RESTART IDENTITY CASCADE';
    END IF;
    IF to_regclass('public.poll_options') IS NOT NULL THEN
        EXECUTE 'TRUNCATE TABLE poll_options RESTART IDENTITY CASCADE';
    END IF;
    IF to_regclass('public.user_votes') IS NOT NULL THEN
        EXECUTE 'TRUNCATE TABLE user_votes RESTART IDENTITY CASCADE';
    END IF;
    IF to_regclass('public.daily_polls') IS NOT NULL THEN
        EXECUTE 'TRUNCATE TABLE daily_polls RESTART IDENTITY CASCADE';
    END IF;
    IF to_regclass('public.users') IS NOT NULL THEN
        EXECUTE 'TRUNCATE TABLE users RESTART IDENTITY CASCADE';
    END IF;
    IF to_regclass('public.groups') IS NOT NULL THEN
        EXECUTE 'TRUNCATE TABLE groups RESTART IDENTITY CASCADE';
    END IF;
END $$;

DROP TABLE IF EXISTS faq_ai CASCADE;
DROP TABLE IF EXISTS knowledge_base CASCADE;
DROP TABLE IF EXISTS unified_knowledge_base CASCADE;
DROP TABLE IF EXISTS ml_cases CASCADE;
