#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Загрузка сырых отзывов школ ЭНГЕЛЬСА (2ГИС + Яндекс) в sa.review.

Идентификаторы отзывов детерминированные, т.к. и 2ГИС, и Яндекс используют
свои локальные номера, которые пересекаются между организациями:
    2ГИС:  2_000_000_000 + (code_oo - 200_000) * 10_000 + idx
    Яндекс: 3_000_000_000 + (code_oo - 200_000) * 10_000 + idx
Темы (topics/overall) заполняются позже LLM-разметкой (анализ-файлы).

Входы:
  roadmap/08.11.26/engels/2gis_reviews_engels.json
  roadmap/08.11.26/engels/ym_reviews_engels.json

Запуск из корня репозитория (на сервере — в venv):
  python db/db_src/db_insert/db_load_engels_reviews.py
"""

from __future__ import annotations

import json
from pathlib import Path

from psycopg2.extras import execute_batch

from db_config_sa import get_connection

PROJECT = Path(__file__).resolve().parent.parent.parent.parent
EN_DIR = PROJECT / "roadmap" / "08.11.26" / "engels"

BASE_2GIS = 2_000_000_000
BASE_YM = 3_000_000_000


def review_id(base: int, code_oo: int, idx: int) -> int:
    return base + (code_oo - 200_000) * 10_000 + idx


def main() -> None:
    gis = json.loads((EN_DIR / "2gis_reviews_engels.json").read_text(encoding="utf-8"))
    ym = json.loads((EN_DIR / "ym_reviews_engels.json").read_text(encoding="utf-8"))

    rows = []
    ratings_2gis = []
    ratings_ym = []
    for code, rec in gis.items():
        code = int(code)
        sid = 100000 + code
        rated = [r['rating'] for r in rec.get('reviews', []) if r.get('rating')]
        if rated:
            ratings_2gis.append((sid, round(sum(rated) / len(rated), 1)))
        for idx, r in enumerate(rec.get('reviews', [])):
            if not r.get('text'):
                continue
            rows.append((
                review_id(BASE_2GIS, code, idx), sid, r.get('date'), r['text'], r.get('rating'),
            ))
    for code, rec in ym.items():
        code = int(code)
        sid = 100000 + code
        rated = [r['rating'] for r in rec.get('reviews', []) if r.get('rating')]
        if rated:
            ratings_ym.append((sid, round(sum(rated) / len(rated), 1)))
        for idx, r in enumerate(rec.get('reviews', [])):
            if not r.get('text'):
                continue
            rows.append((
                review_id(BASE_YM, code, idx), sid, r.get('date'), r['text'], r.get('rating'),
            ))

    print(f"Отзывов к загрузке: {len(rows)} (2ГИС {len(ratings_2gis)} школ, Яндекс {len(ratings_ym)} школ)")

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                execute_batch(
                    cur,
                    """
                    INSERT INTO sa.review (
                        review_id, school_id, review_date, review_text, review_rating
                    ) VALUES (%s,%s,%s,%s,%s)
                    ON CONFLICT (review_id) DO UPDATE SET
                        review_date=EXCLUDED.review_date, review_text=EXCLUDED.review_text,
                        review_rating=EXCLUDED.review_rating, updated_at=CURRENT_TIMESTAMP
                    """,
                    rows,
                )
                execute_batch(
                    cur,
                    """
                    INSERT INTO sa.rating (school_id, rating_2gis) VALUES (%s,%s)
                    ON CONFLICT (school_id) DO UPDATE SET
                        rating_2gis=EXCLUDED.rating_2gis, updated_at=CURRENT_TIMESTAMP
                    """,
                    ratings_2gis,
                )
                execute_batch(
                    cur,
                    """
                    INSERT INTO sa.rating (school_id, rating_yandex) VALUES (%s,%s)
                    ON CONFLICT (school_id) DO UPDATE SET
                        rating_yandex=EXCLUDED.rating_yandex, updated_at=CURRENT_TIMESTAMP
                    """,
                    ratings_ym,
                )
        print("Отзывы Энгельса загружены.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
