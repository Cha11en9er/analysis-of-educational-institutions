-- Создание схемы
CREATE SCHEMA IF NOT EXISTS sa;

CREATE EXTENSION IF NOT EXISTS postgis;

-- Таблица школ
CREATE TABLE sa.school (
    school_id INTEGER PRIMARY KEY,
    name_2gis TEXT,
    name_ym TEXT,
    -- short_name из JSON
    school_address TEXT NOT NULL,
    building_type TEXT,
    floors INTEGER NOT NULL,
    floor_under INTEGER,
    -- underground_floors
    material TEXT,
    reconstruction_year INTEGER,
    year_built INTEGER NOT NULL,
    capacity INTEGER,
    building_info JSONB NOT NULL,
    -- area_sqm, cadastral_number
    has_sports_complex BOOLEAN,
    has_pool BOOLEAN,
    has_stadium BOOLEAN,
    has_sports_ground BOOLEAN,
    LOCATION GEOGRAPHY(Point, 4326) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица рейтингов (динамичная, отдельно)
-- Рейтинги 2ГИС/Яндекс: шкала 0–5 с одним знаком после запятой (например 4.7).
-- NUMERIC(3,1): до 99.9 (3 цифры всего, 1 после запятой).
CREATE TABLE sa.rating (
    rating_id SERIAL PRIMARY KEY,
    school_id INTEGER NOT NULL UNIQUE REFERENCES sa.school(school_id),
    rating_2gis NUMERIC(3,1),
    rating_yandex NUMERIC(3,1),
    review_date_score NUMERIC,
    -- расчётный показатель
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- Таблица ссылок (могут меняться)
CREATE TABLE sa.link (
    link_id SERIAL PRIMARY KEY,
    school_id INTEGER NOT NULL UNIQUE REFERENCES sa.school(school_id),
    link_yandex TEXT,
    review_link_ym TEXT,
    link_2gis TEXT,
    review_link_2gis TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица отзывов с защитой от пустых записей
CREATE TABLE sa.review (
    review_id INTEGER PRIMARY KEY,
    school_id INTEGER NOT NULL REFERENCES sa.school(school_id),
    review_date DATE,
    review_text TEXT,
    likes_count INTEGER DEFAULT 0,
    dislikes_count INTEGER DEFAULT 0,
    review_rating INTEGER CHECK (review_rating BETWEEN 1 AND 5),
    topics JSONB,
    -- {"учителя": "neg", "питание": "pos"}
    overall TEXT,
    -- Защита от полностью пустых отзывов
    CONSTRAINT review_not_empty CHECK (
        review_text IS NOT NULL
        OR review_date IS NOT NULL
    ),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_review_school ON
sa.review(school_id);

CREATE INDEX idx_review_topics ON
sa.review
    USING GIN(topics);