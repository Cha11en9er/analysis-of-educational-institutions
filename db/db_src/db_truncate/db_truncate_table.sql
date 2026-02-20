-- Очистка таблицы отзывов и сброс счетчика review_id
TRUNCATE TABLE sa.review RESTART IDENTITY CASCADE;

-- Очистка таблицы школ и сброс счетчика school_id
TRUNCATE TABLE sa.school RESTART IDENTITY CASCADE;

TRUNCATE TABLE sa.rating RESTART IDENTITY CASCADE;

TRUNCATE TABLE sa.link RESTART IDENTITY CASCADE;
