-- Исправление типа колонок рейтинга: NUMERIC(1,1) допускает только 0.0–0.9,
-- а рейтинги 2ГИС/Яндекс — от 0 до 5 (например 4.7, 5.0).
-- Выполнить один раз, если таблица sa.rating уже была создана со старым типом.
ALTER TABLE sa.rating
    ALTER COLUMN rating_2gis TYPE NUMERIC(3,1),
    ALTER COLUMN rating_yandex TYPE NUMERIC(3,1);
