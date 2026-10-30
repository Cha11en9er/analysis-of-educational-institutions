#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Импорт зон прикрепления (школа <-> адрес дома) в sa.address / sa.school_address
из данных пайплайна geocoding/: gc_input/addresses.json + gc_output/_cache.json.
0 API-запросов: берутся только уже геокодированные адреса (status=ok).

Запуск из корня репозитория (на сервере — в venv):
  python db/db_src/db_insert/db_load_catchment.py
Идемпотентен: ON CONFLICT по address_key и (school_id, address_id).
"""

from __future__ import annotations

import json
from pathlib import Path

from psycopg2.extras import execute_batch

from db_config_sa import get_connection

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
ADDRESSES_JSON = PROJECT_ROOT / "geocoding" / "gc_data" / "gc_input" / "addresses.json"
CACHE_JSON = PROJECT_ROOT / "geocoding" / "gc_data" / "gc_output" / "_cache.json"

SOURCE_YEAR = 2026  # перечень, по которому собран addresses.json


def main() -> None:
    addresses = json.loads(ADDRESSES_JSON.read_text(encoding="utf-8"))
    cache = json.loads(CACHE_JSON.read_text(encoding="utf-8"))["points"]

    # address_key -> row; school_id -> {address_key}
    addr_rows: dict[str, dict] = {}
    links: dict[int, set[str]] = {}
    unresolved = 0

    for rec in addresses:
        sid = rec.get("school_id")
        district, street = rec.get("district"), rec.get("street")
        if not sid or not district or not street:
            continue
        for house in str(rec.get("houses") or "").split(","):
            house = house.strip()
            if not house:
                continue
            key = f"{district}|{street}|{house}"
            links.setdefault(int(sid), set()).add(key)
            if key in addr_rows:
                continue
            geo = cache.get(key)
            if geo and geo.get("lat") and geo.get("lon"):
                addr_rows[key] = {
                    "district": district,
                    "street_norm": street,
                    "house_norm": house,
                    "resolved": geo.get("resolved"),
                    "lat": geo["lat"],
                    "lon": geo["lon"],
                    "status": "ok",
                }
            else:
                unresolved += 1

    print(f"Связей школа×улица×дом: {sum(len(v) for v in links.values())}")
    print(f"Уникальных адресов: {len(addr_rows) + unresolved} (готовых с координатами: {len(addr_rows)}, pending: {unresolved})")

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                execute_batch(
                    cur,
                    """
                    INSERT INTO sa.address (
                        city, district, street_norm, house_norm, address_key,
                        resolved, latitude, longitude, geocode_status, geocoded_at
                    ) VALUES ('Саратов', %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (address_key) DO UPDATE SET
                        district=EXCLUDED.district, resolved=EXCLUDED.resolved,
                        latitude=COALESCE(EXCLUDED.latitude, sa.address.latitude),
                        longitude=COALESCE(EXCLUDED.longitude, sa.address.longitude),
                        geocode_status=CASE
                            WHEN EXCLUDED.geocode_status='ok' THEN 'ok'
                            ELSE sa.address.geocode_status END,
                        geocoded_at=COALESCE(sa.address.geocoded_at, CURRENT_TIMESTAMP)
                    """,
                    [
                        (
                            a["district"], a["street_norm"], a["house_norm"],
                            key, a["resolved"], a["lat"], a["lon"], a["status"],
                        )
                        for key, a in addr_rows.items()
                    ],
                )
                cur.execute("SELECT address_id, address_key FROM sa.address")
                key_to_id = {k: i for i, k in cur.fetchall()}

                link_rows = [
                    (sid, key_to_id[key], SOURCE_YEAR)
                    for sid, keys in links.items()
                    for key in keys
                    if key in key_to_id
                ]
                execute_batch(
                    cur,
                    """
                    INSERT INTO sa.school_address (school_id, address_id, source_year)
                    VALUES (%s,%s,%s)
                    ON CONFLICT (school_id, address_id) DO NOTHING
                    """,
                    link_rows,
                )
        print(f"Загружено адресов: {len(addr_rows)}, связей: {len(link_rows)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
