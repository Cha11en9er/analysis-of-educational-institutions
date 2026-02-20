-- Вставка школ
INSERT INTO sa.school (school_id, name_2gis, name_ym, school_address, building_type, 
                       floors, floor_u, material, reconstruction_year, capacity,
                       building_info, has_sports_complex, has_pool, has_stadium, 
                       has_sports_ground, location)
VALUES 
(1, 'НОУ Прогимназия Идеал', 'Прогимназия Идеал', 'ул Чернышевского, зд 16',
 'Основное здание', 2, NULL, 'смеш', NULL, NULL,
 '{"area_sqm": 1139.8, "year_built": 1980, "cadastral_number": "64:48:000000:15467"}'::jsonb,
 NULL, NULL, NULL, true,
 ST_SetSRID(ST_MakePoint(45.987625, 51.509919), 4326)::geography),

(10, 'МАОУ Гимназия №2', 'Гимназия №2', 'ул Чернышевского, д 138',
 'Основное здание', 4, 1, 'кирп', NULL, NULL,
 '{"area_sqm": 3733.6, "year_built": 1954, "cadastral_number": "64:48:000000:22688"}'::jsonb,
 NULL, NULL, NULL, true,
 ST_SetSRID(ST_MakePoint(46.04023, 51.524715), 4326)::geography);

-- Вставка рейтингов
INSERT INTO sa.rating (school_id, rating_2gis, rating_yandex)
VALUES 
(1, NULL, 4.7),
(10, 5.0, 4.1);

-- Вставка ссылок
INSERT INTO sa.link (school_id, link_yandex, review_link_ym, link_2gis, review_link_2gis)
VALUES 
(1, 'https://yandex.com/maps/org/progimnaziya_ideal/1003889825/',
    'https://yandex.com/maps/org/progimnaziya_ideal/1003889825/reviews/', NULL, NULL),
(10, 'https://yandex.com/maps/org/mou_gymnasium_2_of_the_city_of_saratov/1044083499/',
     'https://yandex.com/maps/org/mou_gymnasium_2_of_the_city_of_saratov/1044083499/reviews/',
     'https://2gis.ru/saratov/firm/6052240280257229',
     'https://2gis.ru/saratov/firm/6052240280257229/tab/reviews');

-- Вставка отзывов (валидных)
INSERT INTO sa.review (review_id, school_id, review_date, text, likes_count, 
                       dislikes_count, rating, topics, overall)
VALUES 
(6737, 124, '2023-12-24', 'Тут учился - супер!', 0, NULL, 5, NULL, NULL),
(254, 5, '2017-01-21', 
 'Знания даются на нулевом уровне,дети ничего не знают по предметам...', 
 19, 2, NULL, '{"учителя": "neg"}'::jsonb, 'neg');

-- Этот INSERT будет отклонён (пустой отзыв):
-- INSERT INTO sa.review (review_id, school_id, review_date, text, likes_count, rating, topics, overall)
-- VALUES (5302, 153, NULL, NULL, NULL, NULL, '{}'::jsonb, 'neutral');
-- ERROR: new row violates check constraint "review_not_empty"