#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Загрузка разметки тем по отзывам:
  - раскладывает анализ-файлы в review_data/rd_2_stage_analys/rd_separately_analyzed/
    (того же формата, что у саратовских школ: [{review_id, topics, overall}]);
    API по этим файлам определяет флаг «есть анализ отзывов» у школы;
  - проставляет topics/overall в sa.review по review_id.

Вход:  roadmap/22.11.26/reviews_analyzed/school_<id>.json
Запуск из корня репозитория (на сервере — в venv):
  python db/db_src/db_insert/db_load_review_topics.py
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from psycopg2.extras import Json, execute_batch

from db_config_sa import get_connection

PROJECT = Path(__file__).resolve().parent.parent.parent.parent
SRC_DIR = PROJECT / "roadmap" / "22.11.26" / "reviews_analyzed"
DST_DIR = PROJECT / "review_data" / "rd_2_stage_analys" / "rd_separately_analyzed"


def main() -> None:
    DST_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(SRC_DIR.glob("school_*.json"))
    updates = []
    for f in files:
        sid = f.stem.replace("school_", "")
        data = json.loads(f.read_text(encoding="utf-8"))
        dst = DST_DIR / f"school_reviews_separately_{sid}_analyz.json"
        dst.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        for item in data:
            updates.append((
                int(item["review_id"]),
                Json(item.get("topics") or {}),
                item.get("overall"),
            ))
    print(f"Анализ-файлов: {len(files)}, отзывов с разметкой: {len(updates)}")

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                execute_batch(
                    cur,
                    """
                    UPDATE sa.review
                    SET topics = %s, overall = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE review_id = %s
                    """,
                    [(t, o, rid) for rid, t, o in updates],
                )
        print("Темы загружены в sa.review.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
