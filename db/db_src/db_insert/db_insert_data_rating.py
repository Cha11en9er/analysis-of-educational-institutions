#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для заполнения таблицы sa.rating на основе
`school_data/sd_2_stage/sd_2_stage_schools.json`.

rating — отдельная динамическая сущность, завязанная на school_id.
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from psycopg2.extras import execute_batch

from db_config_sa import get_connection

# Пути к файлам
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
PROJECT_ROOT = os.path.dirname(DB_ROOT)

SCHOOLS_JSON_PATH = os.path.join(
    PROJECT_ROOT,
    "school_data",
    "sd_2_stage",
    "sd_2_stage_schools.json",
)


def load_schools(path: str) -> List[Dict[str, Any]]:
    """Загружаем школы из JSON."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def to_numeric_rating(value: Any) -> Optional[float]:
    """
    Привести рейтинг к числу для полей NUMERIC(3,1) в БД (значения 0–5, например 4.7).
    """
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def prepare_rating_row(s: Dict[str, Any]) -> Optional[Tuple]:
    """
    Готовим строку для sa.rating.

    sa.rating (
        rating_id SERIAL PRIMARY KEY,
        school_id INTEGER NOT NULL UNIQUE,
        rating_2gis NUMERIC(3,1),   -- рейтинг 0–5 (например 4.7)
        rating_yandex NUMERIC(3,1),
        review_date_score NUMERIC
    )
    """
    school_id = s.get("id")
    if school_id is None:
        return None

    rating_2gis = to_numeric_rating(s.get("rating_2gis"))
    rating_yandex = to_numeric_rating(s.get("rating_yandex"))

    # review_date_score — расчётный показатель, сейчас его нет в данных,
    # поэтому оставляем NULL (можно будет заполнить отдельным скриптом).
    review_date_score = None

    # Если вообще нет полезных данных, нет смысла создавать строку
    if rating_2gis is None and rating_yandex is None and review_date_score is None:
        return None

    return (school_id, rating_2gis, rating_yandex, review_date_score)


def insert_ratings(data: List[Tuple], batch_size: int = 500) -> None:
    """
    Вставляем/обновляем данные в sa.rating.
    """
    if not data:
        print("[INFO] Нет рейтингов для вставки")
        return

    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            sql = """
                INSERT INTO sa.rating (
                    school_id,
                    rating_2gis,
                    rating_yandex,
                    review_date_score
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (school_id) DO UPDATE SET
                    rating_2gis = EXCLUDED.rating_2gis,
                    rating_yandex = EXCLUDED.rating_yandex,
                    review_date_score = EXCLUDED.review_date_score,
                    updated_at = CURRENT_TIMESTAMP;
            """
            execute_batch(cur, sql, data, page_size=batch_size)
        conn.commit()
        print(f"[OK] Вставлено/обновлено записей rating: {len(data)}")
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
    1. Читаем JSON со школами.
    2. Готовим строки для sa.rating.
    3. Вставляем батчами.
    """
    schools = load_schools(SCHOOLS_JSON_PATH)
    rows: List[Tuple] = []
    for s in schools:
        row = prepare_rating_row(s)
        if row is not None:
            rows.append(row)

    insert_ratings(rows)


if __name__ == "__main__":
    main()

