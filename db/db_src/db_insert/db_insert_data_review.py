#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для заполнения таблицы sa.review на основе файлов
`review_data/rd_3_stage/rd_3_stage_data/school_review_separately_{school_id}_final.json`.

Учитывает новую структуру таблицы sa.review:
    review_id, school_id, review_date, review_text,
    likes_count, dislikes_count, review_rating, topics, overall.
"""

import json
import os
from typing import Any, Dict, Iterable, List, Tuple

from psycopg2.extras import execute_batch, Json

from db_config_sa import get_connection

# Пути к данным
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
PROJECT_ROOT = os.path.dirname(DB_ROOT)
REVIEWS_DIR = os.path.join(
    PROJECT_ROOT,
    "review_data",
    "rd_3_stage",
    "rd_3_stage_data",
)


def iter_review_files(directory: str) -> Iterable[str]:
    """
    Перебираем все файлы school_review_separately_*_final.json в папке.
    """
    for name in os.listdir(directory):
        if not name.endswith("_final.json"):
            continue
        if not name.startswith("school_review_separately_"):
            continue
        yield os.path.join(directory, name)


def load_reviews_from_file(path: str) -> List[Dict[str, Any]]:
    """
    Загружаем список отзывов из одного файла.
    Каждый файл содержит массив объектов.
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_empty_review(review: Dict[str, Any]) -> bool:
    """
    Проверяем "пустой" отзыв для ограничения review_not_empty:
    в таблице sa.review есть CHECK:
        review_text IS NOT NULL OR review_date IS NOT NULL
    """
    date_value = review.get("date")
    text_value = review.get("text")

    def _empty_str(v: Any) -> bool:
        return isinstance(v, str) and v.strip() == ""

    is_date_empty = date_value is None or _empty_str(date_value)
    is_text_empty = text_value is None or _empty_str(text_value)

    return is_date_empty and is_text_empty


def prepare_review_row(review: Dict[str, Any]) -> Tuple:
    """
    Преобразуем один отзыв к формату строки для sa.review.

    JSON пример:
        {
          "review_id": "1",
          "school_id": "1",
          "date": "2024-04-09",
          "text": "...",
          "likes_count": 1,
          "dislikes_count": 0,
          "rating": 5,
          "topics": {...},
          "overall": "pos"
        }

    sa.review (
        review_id INTEGER PRIMARY KEY,
        school_id INTEGER NOT NULL,
        review_date DATE,
        review_text TEXT,
        likes_count INTEGER,
        dislikes_count INTEGER,
        review_rating INTEGER,
        topics JSONB,
        overall TEXT
    )
    """
    # id-шники из JSON приходят строками, приводим к int
    review_id = int(review.get("review_id"))
    school_id = int(review.get("school_id"))

    # Даты режем как строку формата YYYY-MM-DD - PostgreSQL сам приведёт к DATE
    date_value = review.get("date") or None
    if isinstance(date_value, str) and date_value.strip() == "":
        date_value = None

    text_value = review.get("text") or None
    if isinstance(text_value, str) and text_value.strip() == "":
        text_value = None

    # Лайки/дизлайки и рейтинг
    likes_count = review.get("likes_count")
    dislikes_count = review.get("dislikes_count")
    rating = review.get("rating")

    # topics — словарь -> JSONB
    topics_value = review.get("topics") or {}

    # overall, при пустом значении можно оставить NULL,
    # чтобы не подменять семантику 'pos' по умолчанию
    overall_value = review.get("overall")
    if isinstance(overall_value, str) and overall_value.strip() == "":
        overall_value = None

    return (
        review_id,
        school_id,
        date_value,
        text_value,
        likes_count,
        dislikes_count,
        rating,
        Json(topics_value),
        overall_value,
    )


def insert_reviews(rows: List[Tuple], batch_size: int = 1000) -> None:
    """
    Батч-вставка отзывов в sa.review.
    """
    if not rows:
        print("[INFO] Нет отзывов для вставки")
        return

    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            sql = """
                INSERT INTO sa.review (
                    review_id,
                    school_id,
                    review_date,
                    review_text,
                    likes_count,
                    dislikes_count,
                    review_rating,
                    topics,
                    overall
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (review_id) DO UPDATE SET
                    school_id = EXCLUDED.school_id,
                    review_date = EXCLUDED.review_date,
                    review_text = EXCLUDED.review_text,
                    likes_count = EXCLUDED.likes_count,
                    dislikes_count = EXCLUDED.dislikes_count,
                    review_rating = EXCLUDED.review_rating,
                    topics = EXCLUDED.topics,
                    overall = EXCLUDED.overall,
                    updated_at = CURRENT_TIMESTAMP;
            """
            execute_batch(cur, sql, rows, page_size=batch_size)
        conn.commit()
        print(f"[OK] Вставлено/обновлено отзывов: {len(rows)}")
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def main() -> None:
    """
    Точка входа:
    1. Проходим по всем *_final.json.
    2. Собираем все отзывы в один список.
    3. Отфильтровываем полностью пустые (нет даты и текста).
    4. Вставляем в sa.review с UPSERT по review_id.
    """
    all_rows: List[Tuple] = []

    for path in iter_review_files(REVIEWS_DIR):
        reviews = load_reviews_from_file(path)
        if not reviews:
            continue

        for r in reviews:
            if is_empty_review(r):
                # Такие записи завалят CHECK (review_not_empty), пропускаем
                continue
            row = prepare_review_row(r)
            all_rows.append(row)

    insert_reviews(all_rows)


if __name__ == "__main__":
    main()

