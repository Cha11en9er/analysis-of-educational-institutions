#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Загрузка sa.institution из выгрузки каталога РЦОКО (слой не-школ: спорт/творческие/
садики/вузы/СПО/интернаты). Школьный рейтинг sa.school не затрагивается.

Вход:  db/db_data/db_input_institutions/institutions_rcoko.json
Запуск из корня репозитория (на сервере — в venv):
  python db/db_src/db_insert/db_load_institutions.py [--city-strict]
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

# Слои, которые выкладываем на карту (general — уже на карте как школы)
KINDS_TO_LOAD = ("sport_do", "arts_do", "preschool", "internat_cadet", "spo", "vuz")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--city-strict", action="store_true",
        help="Только адреса с 'г. Саратов' (иначе город/пригороды по полю city)",
    )
    args = parser.parse_args()

    rows = json.loads(INPUT.read_text(encoding="utf-8"))
    batch = []
    for r in rows:
        if r["kind"] not in KINDS_TO_LOAD:
            continue
        addr = r.get("address") or ""
        if args.city_strict and "г. саратов" not in addr.lower():
            continue
        if not r.get("name"):
            continue
        batch.append(
            (
                r["code_oo"],
                r["kind"],
                r["name"],
                r.get("name_full"),
                addr or None,
                r.get("phone"),
                r.get("site"),
            )
        )
    print(f"К загрузке: {len(batch)} учреждений (kinds: {sorted({b[1] for b in batch})})")

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                execute_batch(
                    cur,
                    """
                    INSERT INTO sa.institution (
                        code_oo, kind, name, name_full, address, phone, site
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (code_oo) DO UPDATE SET
                        kind=EXCLUDED.kind, name=EXCLUDED.name, name_full=EXCLUDED.name_full,
                        address=EXCLUDED.address, phone=EXCLUDED.phone, site=EXCLUDED.site,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    batch,
                )
        print("Загрузка учреждений завершена.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
