-- Создание таблицы review в схеме ca
-- Таблица для хранения отзывов о школах

CREATE SCHEMA IF NOT EXISTS ca;

CREATE TABLE IF NOT EXISTS ca.review (
    review_id VARCHAR(255) PRIMARY KEY,
    school_id VARCHAR(255) NOT NULL,
    date DATE NULL,  -- NULL разрешён для случаев, когда у школы нет отзывов
    text TEXT NULL,  -- NULL разрешён для случаев, когда у школы нет отзывов
    topics JSONB NOT NULL DEFAULT '{}'::jsonb,
    overall VARCHAR(10) NOT NULL DEFAULT 'pos' CHECK (overall IN ('pos', 'neg')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для улучшения производительности запросов
CREATE INDEX IF NOT EXISTS idx_review_school_id ON ca.review(school_id);
CREATE INDEX IF NOT EXISTS idx_review_date ON ca.review(date);
CREATE INDEX IF NOT EXISTS idx_review_overall ON ca.review(overall);

-- GIN индекс для JSONB поля topics (позволяет эффективно искать по ключам в JSON)
CREATE INDEX IF NOT EXISTS idx_review_topics ON ca.review USING GIN (topics);

-- Комментарии к таблице и полям
COMMENT ON TABLE ca.review IS 'Таблица для хранения отзывов о школах';
COMMENT ON COLUMN ca.review.review_id IS 'Уникальный идентификатор отзыва';
COMMENT ON COLUMN ca.review.school_id IS 'Идентификатор школы';
COMMENT ON COLUMN ca.review.date IS 'Дата отзыва (NULL если у школы нет отзывов)';
COMMENT ON COLUMN ca.review.text IS 'Текст отзыва (NULL если у школы нет отзывов)';
COMMENT ON COLUMN ca.review.topics IS 'Словарь тем отзыва в формате JSON (например: {"учителя": "pos", "еда": "neg"})';
COMMENT ON COLUMN ca.review.overall IS 'Общая тональность отзыва: pos (положительный) или neg (отрицательный)';
COMMENT ON COLUMN ca.review.created_at IS 'Дата и время создания записи';

