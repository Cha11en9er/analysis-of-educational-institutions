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
    -- Города: проект растёт на всю Россию, Саратов — первый город
    city TEXT NOT NULL DEFAULT 'Саратов',
    -- Итоговый рейтинг и образовательные метрики (из final_school_data.json)
    rating_total NUMERIC(6,1),
    ege_average_score NUMERIC(4,1),
    ege_year INTEGER,
    university_admission_percent NUMERIC(5,1),
    university_admission_year INTEGER,
    olympiad_winners_count INTEGER,
    top_tags JSONB,
    administrative_district TEXT,
    rating_ege NUMERIC,
    rating_olympiads NUMERIC,
    rating_teachers NUMERIC,
    rating_mto NUMERIC,
    rating_psychological_climate NUMERIC,
    rating_sports_infrastructure NUMERIC,
    rating_profiles NUMERIC,
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
    link_gosuslugi TEXT,
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
-- ============================================================
-- Миграция существующих баз (можно выполнять повторно).
-- Новые поля UI v2: города, итоговый рейтинг, ЕГЭ, олимпиады и др.
-- ============================================================
ALTER TABLE sa.school ADD COLUMN IF NOT EXISTS city TEXT NOT NULL DEFAULT 'Саратов';
ALTER TABLE sa.school ADD COLUMN IF NOT EXISTS rating_total NUMERIC(6,1);
ALTER TABLE sa.school ADD COLUMN IF NOT EXISTS ege_average_score NUMERIC(4,1);
ALTER TABLE sa.school ADD COLUMN IF NOT EXISTS ege_year INTEGER;
ALTER TABLE sa.school ADD COLUMN IF NOT EXISTS university_admission_percent NUMERIC(5,1);
ALTER TABLE sa.school ADD COLUMN IF NOT EXISTS university_admission_year INTEGER;
ALTER TABLE sa.school ADD COLUMN IF NOT EXISTS olympiad_winners_count INTEGER;
ALTER TABLE sa.school ADD COLUMN IF NOT EXISTS top_tags JSONB;
ALTER TABLE sa.school ADD COLUMN IF NOT EXISTS administrative_district TEXT;
ALTER TABLE sa.school ADD COLUMN IF NOT EXISTS rating_ege NUMERIC;
ALTER TABLE sa.school ADD COLUMN IF NOT EXISTS rating_olympiads NUMERIC;
ALTER TABLE sa.school ADD COLUMN IF NOT EXISTS rating_teachers NUMERIC;
ALTER TABLE sa.school ADD COLUMN IF NOT EXISTS rating_mto NUMERIC;
ALTER TABLE sa.school ADD COLUMN IF NOT EXISTS rating_psychological_climate NUMERIC;
ALTER TABLE sa.school ADD COLUMN IF NOT EXISTS rating_sports_infrastructure NUMERIC;
ALTER TABLE sa.school ADD COLUMN IF NOT EXISTS rating_profiles NUMERIC;

-- ============================================================
-- Миграция 30.10.26: слои учреждений (Задача B) и зоны прикрепления (Задача C)
-- ============================================================

-- Учреждения вне школьного рейтинга: спорт/творческие ДО, садики, вузы, СПО, интернаты
CREATE TABLE IF NOT EXISTS sa.institution (
    institution_id SERIAL PRIMARY KEY,
    code_oo INTEGER UNIQUE,                -- код ОО из реестра РЦОКО (если есть)
    kind TEXT NOT NULL,                    -- sport_do | arts_do | preschool | internat_cadet | spo | vuz | other
    name TEXT NOT NULL,
    name_full TEXT,
    address TEXT,
    phone TEXT,
    site TEXT,
    city TEXT NOT NULL DEFAULT 'Саратов',
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    geocode_status TEXT DEFAULT 'pending', -- pending | ok | fail | ambiguous
    geocoded_at TIMESTAMP,
    source TEXT NOT NULL DEFAULT 'rcoko_catalog',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_institution_kind ON sa.institution(kind);
CREATE INDEX IF NOT EXISTS idx_institution_city ON sa.institution(city);

-- Нормализованный адрес дома (задел на все города)
CREATE TABLE IF NOT EXISTS sa.address (
    address_id SERIAL PRIMARY KEY,
    city TEXT NOT NULL DEFAULT 'Саратов',
    district TEXT,
    street_norm TEXT NOT NULL,
    house_norm TEXT NOT NULL,
    address_key TEXT NOT NULL UNIQUE,      -- district|street|house (hash-free, читаемый)
    resolved TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    geocode_status TEXT NOT NULL DEFAULT 'pending',
    geocoded_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_address_status ON sa.address(geocode_status);

-- M:N школа <-> адрес прикрепления (пересечения = несколько связей на адрес)
CREATE TABLE IF NOT EXISTS sa.school_address (
    school_id INTEGER NOT NULL REFERENCES sa.school(school_id),
    address_id INTEGER NOT NULL REFERENCES sa.address(address_id),
    source_year INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (school_id, address_id)
);
CREATE INDEX IF NOT EXISTS idx_school_address_school ON sa.school_address(school_id);

-- Миграция 30.10.26 (вечер): группы заведений + общие/частные + город
ALTER TABLE sa.institution ADD COLUMN IF NOT EXISTS ownership TEXT NOT NULL DEFAULT 'public';
ALTER TABLE sa.school ADD COLUMN IF NOT EXISTS ownership TEXT NOT NULL DEFAULT 'public';

-- Миграция 30.10.26 (вечер, 2): группы селектора и связь с нашими школами
ALTER TABLE sa.institution ADD COLUMN IF NOT EXISTS inst_group TEXT; -- school|preschool|vuz|other
ALTER TABLE sa.institution ADD COLUMN IF NOT EXISTS our_school_id INTEGER REFERENCES sa.school(school_id);
CREATE INDEX IF NOT EXISTS idx_institution_group ON sa.institution(inst_group);

-- Миграция 31.10.26: institution не должен каскадно очищаться при TRUNCATE sa.school
ALTER TABLE sa.institution DROP CONSTRAINT IF EXISTS institution_our_school_id_fkey;

-- Миграция 31.10.26 (2): журнал геокодирования (лимиты Яндекса ~1000/сутки)
CREATE TABLE IF NOT EXISTS sa.geocode_log (
    log_id SERIAL PRIMARY KEY,
    run_date DATE NOT NULL DEFAULT CURRENT_DATE,
    provider TEXT NOT NULL DEFAULT 'yandex',
    requests INTEGER NOT NULL DEFAULT 0,
    ok_count INTEGER NOT NULL DEFAULT 0,
    ambiguous_count INTEGER NOT NULL DEFAULT 0,
    fail_count INTEGER NOT NULL DEFAULT 0,
    pending_left INTEGER,
    note TEXT
);
CREATE INDEX IF NOT EXISTS idx_geocode_log_date ON sa.geocode_log(run_date);

-- Миграция 01.11.26: школы других городов (Энгельс) — паспорт здания необязателен
ALTER TABLE sa.school ALTER COLUMN floors DROP NOT NULL;
ALTER TABLE sa.school ALTER COLUMN year_built DROP NOT NULL;
ALTER TABLE sa.school ALTER COLUMN school_address DROP NOT NULL;
ALTER TABLE sa.school ALTER COLUMN building_info DROP NOT NULL;
