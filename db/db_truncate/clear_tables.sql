-- Очистка таблиц и сброс счетчиков ID

-- Очистка таблицы отзывов и сброс счетчика review_id
TRUNCATE TABLE ca.review RESTART IDENTITY CASCADE;

-- Очистка таблицы школ и сброс счетчика school_id
TRUNCATE TABLE ca.school RESTART IDENTITY CASCADE;

