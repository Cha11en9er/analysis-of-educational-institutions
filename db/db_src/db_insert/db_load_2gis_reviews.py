#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Загрузка сырых отзывов 2ГИС школ Энгельса в sa.review (сырьё, LLM-разметка тем позже).

Вход:  roadmap/08.11.26/engels/2gis_reviews_engels.json  (батч-сбор 2gis_batch_engels.py)
       ключи — коды ОО; school_id = 100000 + код ОО (как в db_load_city_schools.py).
Отзывы: review_id = 2ГИС-идентификатор (INT, не пересекается с саратовскими),
        review_text + review_rating + review_date; topics/overall NULL до LLM-разметки.

Запуск из корня репозитория (на сервере — в venv):
  python db/db_src/db_insert/db_load_2gis_reviews.py
Идемпотентен: upsert по review_id.
"""

from __future__ import annotations

import json
from pathlib import Path

from psycopg2.extras import execute_batch

from db_config_sa import get_connection

SCRIPT_DIR = Path(__file__).resolve().parent
INPUT = SCRIPT_DIR.parent.parent.parent / "roadmap" / "08.11.26" / "2gis_reviews_engels.json"


def main() -> None:
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    batch = []
    ratings = []
    for code, rec in data.items():
        sid = 100000 + int(code)
        rated = [rv["rating"] for rv in rec.get("reviews", []) if rv.get("rating")]
        if rated:
            ratings.append((sid, round(sum(rated) / len(rated), 1)))
        for rv in rec.get("reviews", []):
            if not rv.get("text"):
                continue
            review_id = rv.get("review_id")
            if not review_id or not str(review_id).isdigit():
                continue
            batch.append((
                int(review_id),
                sid,
                rv.get("date"),
                rv["text"],
                rv.get("rating"),
            ))
    print(f"К загрузке: {len(batch)} отзывов 2ГИС, рейтингов {len(ratings)}")

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                execute_batch(
                    cur,
                    """
                    INSERT INTO sa.review (
                        review_id, school_id, review_date, review_text,
                        review_rating, topics, overall
                    ) VALUES (%s,%s,%s,%s,%s,NULL,NULL)
                    ON CONFLICT (review_id) DO UPDATE SET
                        review_text=EXCLUDED.review_text, review_rating=EXCLUDED.review_rating,
                        review_date=EXCLUDED.review_date, updated_at=CURRENT_TIMESTAMP
                    """,
                    batch,
                )
                execute_batch(
                    cur,
                    """
                    INSERT INTO sa.rating (school_id, rating_2gis)
                    VALUES (%s,%s)
                    ON CONFLICT (school_id) DO UPDATE SET
                        rating_2gis=EXCLUDED.rating_2gis, updated_at=CURRENT_TIMESTAMP
                    """,
                    ratings,
                )
        print("Загрузка 2ГИС-отзывов завершена.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
