#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Геокодирование sa.institution через Яндекс HTTP-геокодер.
Кэш — сама таблица: обрабатываются только geocode_status='pending'; ok не трогаем.
Запуск из корня репозитория НА СЕРВЕРЕ (ключ YANDEX_API_KEY в .env):
  python geocoding/scripts/geocode_institutions.py [--limit 300]
Дневной лимит Яндекс ≈ 1000 запросов; скрипт не превышает --limit.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.parse
import urllib.request

from dotenv import load_dotenv

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(REPO_ROOT, ".env"))

import psycopg2  # noqa: E402
import psycopg2.extras  # noqa: E402

API = "https://geocode-maps.yandex.ru/1.x/"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
UA_NOMINATIM = {"User-Agent": "uchgrad.ru/1.0 (schools map; contact: rcoko@sarrcoko.ru)"}
# Ключ ограничен Referrer https://uchgrad.ru/* — запросы от имени сайта обязаны его нести.
YANDEX_HEADERS = {"Referer": "https://uchgrad.ru/"}


def geocode_nominatim(query: str) -> tuple[str, float | None, float | None]:
    """OSM Nominatim: без ключа, лимит 1 запрос/сек. Точность грубее Яндекса."""
    params = {"q": query, "format": "json", "limit": 1, "addressdetails": 0, "countrycodes": "ru"}
    req = urllib.request.Request(NOMINATIM + "?" + urllib.parse.urlencode(params), headers=UA_NOMINATIM)
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode("utf-8"))
    if not d:
        return "fail", None, None
    return "ok", float(d[0]["lat"]), float(d[0]["lon"])


def geocode_once(api_key: str, query: str) -> tuple[str, float | None, float | None]:
    params = {
        "apikey": api_key,
        "geocode": query,
        "format": "json",
        "results": 1,
        "lang": "ru_RU",
    }
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(params), headers=YANDEX_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode("utf-8"))
    members = (
        d.get("response", {})
        .get("GeoObjectCollection", {})
        .get("featureMember", [])
    )
    if not members:
        return "fail", None, None
    pos = members[0]["GeoObject"]["Point"]["pos"].split()  # [lon, lat]
    precision = members[0]["GeoObject"].get("metaDataProperty", {}).get(
        "GeocoderMetaData", {}
    ).get("precision", "other")
    status = "ok" if precision in ("exact", "number") else "ambiguous"
    return status, float(pos[1]), float(pos[0])


def normalize_query(addr: str) -> str:
    """Nominatim любит улицы словами, не любит индексы и сокращения 'д.'."""
    q = addr.strip()
    q = re.sub(r"^\d{6},?\s*", "", q)            # почтовый индекс
    q = re.sub(r"\bд\.\s*", "", q)               # 'д. 138' -> '138'
    q = re.sub(r"\bул\.\s*", "улица ", q)
    q = re.sub(r"\bпр-кт\b", "проспект", q)
    q = re.sub(r"\bпр-д\b", "проезд", q)
    q = re.sub(r"\bб-р\b", "бульвар", q)
    return q


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument(
        "--retry-failed", action="store_true",
        help="Сбросить status=fail в pending перед прогоном",
    )
    parser.add_argument(
        "--provider", choices=["yandex", "nominatim"], default="nominatim",
        help="nominatim — без ключа (1 req/s); yandex — требует ключ с правом HTTP-геокодера",
    )
    args = parser.parse_args()

    api_key = (os.getenv("YANDEX_API_KEY") or "").strip()
    if args.provider == "yandex" and not api_key:
        raise SystemExit("YANDEX_API_KEY не найден в .env")

    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )
    done = ok = fail = ambiguous = 0
    try:
        with conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            if args.retry_failed:
                cur.execute("UPDATE sa.institution SET geocode_status='pending' WHERE geocode_status='fail'")
                conn.commit()
                print("fail -> pending сброшен")
            cur.execute(
                """
                SELECT institution_id, name, address FROM sa.institution
                WHERE geocode_status = 'pending' AND address IS NOT NULL
                  AND latitude IS NULL
                ORDER BY institution_id
                LIMIT %s
                """,
                (args.limit,),
            )
            rows = cur.fetchall()
            print(f"К геокодированию: {len(rows)}")
            for row in rows:
                if done >= args.limit:
                    break
                query = f"Россия, {normalize_query(row['address'])}"
                try:
                    if args.provider == "nominatim":
                        status, lat, lon = geocode_nominatim(query)
                    else:
                        status, lat, lon = geocode_once(api_key, query)
                except Exception as e:
                    print("ERROR", row["institution_id"], str(e)[:80])
                    time.sleep(1)
                    continue
                cur.execute(
                    """
                    UPDATE sa.institution
                    SET latitude=%s, longitude=%s, geocode_status=%s,
                        geocoded_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
                    WHERE institution_id=%s
                    """,
                    (lat, lon, status, row["institution_id"]),
                )
                conn.commit()
                done += 1
                if status == "ok":
                    ok += 1
                elif status == "ambiguous":
                    ambiguous += 1
                else:
                    fail += 1
                time.sleep(0.12 if args.provider == "yandex" else 1.1)
    finally:
        conn.close()
    print(f"Итог: обработано {done} | ok {ok} | ambiguous {ambiguous} | fail {fail}")


if __name__ == "__main__":
    main()
