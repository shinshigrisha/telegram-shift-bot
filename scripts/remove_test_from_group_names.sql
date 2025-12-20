-- Скрипт для переименования группы "тест & ziz_bot" в "ЗИЗ-6"
-- ВНИМАНИЕ: Этот скрипт удалит существующую группу "ЗИЗ-6" если она есть!

-- Сначала удаляем существующую группу "ЗИЗ-6" (если есть)
DELETE FROM groups WHERE name = 'ЗИЗ-6';

-- Переименовываем группу "тест & ziz_bot" в "ЗИЗ-6"
UPDATE groups
SET name = 'ЗИЗ-6'
WHERE name = 'тест & ziz_bot';

-- Показываем обновленные названия
SELECT id, name, telegram_chat_id 
FROM groups 
ORDER BY id;

