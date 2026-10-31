#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Загрузка sa.institution из выгрузки каталога РЦОКО.
Группы для селектора сайта: school (школы вне рейтинга — Энгельс и др.) / preschool /
vuz / other (спорт + творческие + СПО + интернаты/кадеты + прочие).

Вход:  db/db_data/db_input_institutions/institutions_rcoko.json (city/ownership внутри)
Запуск из корня репозитория (на сервере — в venv):
  python db/db_src/db_insert/db_load_institutions.py [--cities "Саратов,Энгельс"]
Идемпотентен: upsert по code_oo.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from psycopg2.extras import execute_batch

from db_config_sa import get_connection

SCRIPT_DIR = Path(__file__).resolve().parent
INPUT = SCRIPT_DIR.parent.parent / "db_data" / "db_input_institutions" / "institutions_rcoko.json"

# kind -> группа селектора сайта
KIND_TO_GROUP = {
    "general": "school",
    "preschool": "preschool",
    "vuz": "vuz",
    "sport_do": "other",
    "arts_do": "other",
    "spo": "other",
    "internat_cadet": "other",
    "other": "other",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cities", default="Саратов,Энгельс",
        help="Города для загрузки (через запятую)",
    )
    args = parser.parse_args()
    cities = [c.strip() for c in args.cities.split(",") if c.strip()]

    rows = json.loads(INPUT.read_text(encoding="utf-8"))
    batch = []
    seen_codes = set()
    for r in rows:
        if r.get("city") not in cities:
            continue
        if r["kind"] not in KIND_TO_GROUP:
            continue
        code = r.get("code_oo")
        if code in seen_codes:
            continue
        seen_codes.add(code)
        if not r.get("name"):
            continue
        batch.append(
            (
                code,
                r["kind"],
                KIND_TO_GROUP[r["kind"]],
                r.get("ownership") or "public",
                r.get("city"),
                r["name"],
                r.get("name_full"),
                r.get("address") or None,
                r.get("phone"),
                r.get("site"),
                r.get("in_uchgrad_school_id"),
            )
        )
    print(f"К загрузке: {len(batch)} учреждений (города: {cities})")

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                execute_batch(
                    cur,
                    """
                    INSERT INTO sa.institution (
                        code_oo, kind, inst_group, ownership, city, name, name_full,
                        address, phone, site, our_school_id
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (code_oo) DO UPDATE SET
                        kind=EXCLUDED.kind, inst_group=EXCLUDED.inst_group,
                        ownership=EXCLUDED.ownership, city=EXCLUDED.city,
                        name=EXCLUDED.name, name_full=EXCLUDED.name_full,
                        address=EXCLUDED.address, phone=EXCLUDED.phone, site=EXCLUDED.site,
                        our_school_id=EXCLUDED.our_school_id,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    batch,
                )
        print("Загрузка учреждений завершена.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
