#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Загрузка медианных цен жилья в прикреплённых домах: price/prices.json -> sa.school.price_median.

Запуск из корня репозитория (на сервере — в venv):
  python db/db_src/db_insert/db_load_prices.py
Идемпотентен: UPDATE по school_id. Школы, отсутствующие в sa.school, пропускаются.
"""

from __future__ import annotations

import json
from pathlib import Path

from db_config_sa import get_connection

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
INPUT = PROJECT_ROOT / "price" / "prices.json"


def main() -> None:
    rows = json.loads(INPUT.read_text(encoding="utf-8"))
    print(f"Записей с ценами: {len(rows)}")

    conn = get_connection()
    updated = skipped = 0
    try:
        with conn, conn.cursor() as cur:
            for r in rows:
                sid, price = r.get("id"), r.get("price")
                if sid is None or price is None:
                    skipped += 1
                    continue
                cur.execute(
                    "UPDATE sa.school SET price_median=%s, updated_at=CURRENT_TIMESTAMP "
                    "WHERE school_id=%s",
                    (int(price), int(sid)),
                )
                if cur.rowcount:
                    updated += 1
                else:
                    skipped += 1
        print(f"Обновлено школ: {updated}, пропущено (нет в sa.school): {skipped}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
