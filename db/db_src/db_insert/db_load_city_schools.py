#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Загрузка школ городов (сейчас — Энгельс) в sa.school как полноправные записи
с city <> 'Саратов'. Рейтинговые поля пустые — заполнятся парсерами Госуслуг/карт.

Вход:  roadmap/01.11.26/engels/city_schools.json (код ОО, координаты из sa.institution,
       ссылка Яндекс, сайт Госуслуг, ownership)
Запуск из корня репозитория (на сервере — в venv):
  python db/db_src/db_insert/db_load_city_schools.py
Идемпотентен: upsert по school_id (= 100000 + код ОО, чтобы не пересекаться с Саратовом).
"""

from __future__ import annotations

import json
from pathlib import Path

from psycopg2.extras import Json, execute_batch

from db_config_sa import get_connection

SCRIPT_DIR = Path(__file__).resolve().parent
INPUT = SCRIPT_DIR.parent.parent.parent / "roadmap" / "01.11.26" / "engels" / "city_schools.json"


def main() -> None:
    rows = json.loads(INPUT.read_text(encoding="utf-8"))
    batch = []
    for s in rows:
        building_info = Json({"code_oo": s["code_oo"]})
        batch.append(
            (
                s["school_id"],
                s.get("name_short"),            # name_ym
                s.get("address"),
                building_info,
                s.get("ownership") or "public",
                s.get("city") or "Энгельс",
                s.get("link_yandex"),
                s.get("site"),
                f"SRID=4326;POINT({s['longitude']} {s['latitude']})",
            )
        )
    print(f"К загрузке: {len(batch)} школ городов")

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                execute_batch(
                    cur,
                    """
                    INSERT INTO sa.school (
                        school_id, name_ym, school_address, building_info,
                        ownership, city, location
                    ) VALUES (%s,%s,%s,%s,%s,%s,ST_GeogFromText(%s))
                    ON CONFLICT (school_id) DO UPDATE SET
                        name_ym=EXCLUDED.name_ym, school_address=EXCLUDED.school_address,
                        building_info=EXCLUDED.building_info, ownership=EXCLUDED.ownership,
                        city=EXCLUDED.city, location=EXCLUDED.location,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    [(b[0], b[1], b[2], b[3], b[4], b[5], b[8]) for b in batch],
                )
                link_rows = [
                    (b[0], b[6], b[7])  # school_id, link_yandex, link_gosuslugi (site)
                    for b in batch
                ]
                execute_batch(
                    cur,
                    """
                    INSERT INTO sa.link (
                        school_id, link_yandex, link_gosuslugi
                    ) VALUES (%s,%s,%s)
                    ON CONFLICT (school_id) DO UPDATE SET
                        link_yandex=EXCLUDED.link_yandex,
                        link_gosuslugi=EXCLUDED.link_gosuslugi,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    link_rows,
                )
        print("Загрузка школ городов завершена.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
