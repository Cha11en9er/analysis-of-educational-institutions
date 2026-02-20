"""
Скрипт для заполнения таблицы sa.link на основе
`school_data/sd_2_stage/sd_2_stage_schools.json`.

Каждая запись в sa.link соответствует одной школе (1:1 по school_id).
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


def prepare_link_row(s: Dict[str, Any]) -> Optional[Tuple]:
    """
    Готовим строку для sa.link.

    sa.link (
        link_id SERIAL PRIMARY KEY,
        school_id INTEGER NOT NULL UNIQUE,
        link_yandex TEXT,
        review_link_ym TEXT,
        link_2gis TEXT,
        review_link_2gis TEXT
    )
    """
    school_id = s.get("id")
    if school_id is None:
        return None

    link_yandex = s.get("link_yandex")
    review_link_ym = s.get("reviews_link_yandex")  # из JSON reviews_link_yandex -> в БД review_link_ym
    link_2gis = s.get("link_2gis")
    review_link_2gis = s.get("reviews_link_2gis")

    # Если вообще нет ссылок, можно не создавать строку
    if not any([link_yandex, review_link_ym, link_2gis, review_link_2gis]):
        return None

    return (school_id, link_yandex, review_link_ym, link_2gis, review_link_2gis)


def insert_links(data: List[Tuple], batch_size: int = 500) -> None:
    """
    Вставляем/обновляем данные в sa.link.
    """
    if not data:
        print("[INFO] Нет ссылок для вставки")
        return

    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            sql = """
                INSERT INTO sa.link (
                    school_id,
                    link_yandex,
                    review_link_ym,
                    link_2gis,
                    review_link_2gis
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (school_id) DO UPDATE SET
                    link_yandex = EXCLUDED.link_yandex,
                    review_link_ym = EXCLUDED.review_link_ym,
                    link_2gis = EXCLUDED.link_2gis,
                    review_link_2gis = EXCLUDED.review_link_2gis,
                    updated_at = CURRENT_TIMESTAMP;
            """
            execute_batch(cur, sql, data, page_size=batch_size)
        conn.commit()
        print(f"[OK] Вставлено/обновлено записей link: {len(data)}")
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
    2. Готовим строки для sa.link.
    3. Вставляем батчами.
    """
    schools = load_schools(SCHOOLS_JSON_PATH)
    rows: List[Tuple] = []
    for s in schools:
        row = prepare_link_row(s)
        if row is not None:
            rows.append(row)

    insert_links(rows)


if __name__ == "__main__":
    main()

