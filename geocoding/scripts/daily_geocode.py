#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ежедневный геокод адресов прикрепления: sa.address (pending) -> координаты.

Правила (см. .cursor/rules/geocoding.mdc):
  - запрос всегда с городом/областью/районом (иначе найдёт не тот город);
  - Referer https://uchgrad.ru/ (ключ ограничен по referrer);
  - дневной лимит Яндекса ~1000, скрипт берёт --limit (по умолчанию 900);
  - ok не трогаем; ambiguous/fail можно перебрать --retry-failed.

Запуск на сервере из /opt/uchgrad:
  .venv/bin/python geocoding/scripts/daily_geocode.py            # обычная пачка
  .venv/bin/python geocoding/scripts/daily_geocode.py --limit 400 --retry-failed
Крон (пример, 04:10 МСК):
  10 4 * * * cd /opt/uchgrad && .venv/bin/python geocoding/scripts/daily_geocode.py >> geocoding/daily.log 2>&1
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
YANDEX_HEADERS = {"Referer": "https://uchgrad.ru/"}

DAILY_LIMIT_CAP = 850   # потолок за прогон с запасом (лимит Яндекса 1000/сутки)
# Расхождение суток Яндекса и наших логов может стоить блокировки ключа —
# поэтому бюджет всегда = min(--limit, CAP, 1000 - потрачено сегодня по sa.geocode_log).


def normalize_query(city: str, district: str | None, street: str, house: str) -> str:
    """Полный адрес с городом/областью — без этого геокодер найдёт не тот город."""
    parts = ["Россия", "Саратовская область", city]
    if district:
        parts.append(f"{district} район")
    parts.append(f"{street} {house}")
    return ", ".join(parts)


def geocode_once(api_key: str, query: str) -> tuple[str, float | None, float | None, str | None]:
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
    members = d.get("response", {}).get("GeoObjectCollection", {}).get("featureMember", [])
    if not members:
        return "fail", None, None, None
    obj = members[0]["GeoObject"]
    pos = obj["Point"]["pos"].split()
    precision = obj.get("metaDataProperty", {}).get("GeocoderMetaData", {}).get("precision", "other")
    status = "ok" if precision in ("exact", "number") else "ambiguous"
    resolved = obj.get("metaDataProperty", {}).get("GeocoderMetaData", {}).get("text")
    return status, float(pos[1]), float(pos[0]), resolved


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=900)
    parser.add_argument("--retry-failed", action="store_true")
    args = parser.parse_args()
    limit = min(args.limit, DAILY_LIMIT_CAP)

    api_key = (os.getenv("YANDEX_API_KEY") or "").strip()
    if not api_key:
        raise SystemExit("YANDEX_API_KEY не найден в .env")

    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )
    done = ok = ambiguous = fail = 0
    try:
        with conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT COALESCE(SUM(requests), 0) FROM sa.geocode_log WHERE run_date = CURRENT_DATE"
            )
            spent_today = cur.fetchone()[0]
            budget = max(0, min(limit, DAILY_LIMIT_CAP, 1000 - spent_today))
            print(f"[daily] потрачено сегодня по журналу: {spent_today}/1000 -> бюджет пачки: {budget}")
            if budget == 0:
                print("[daily] дневной лимит исчерпан по журналу — выходим (ключ не трогаем)")
                return

            if args.retry_failed:
                cur.execute(
                    """
                    UPDATE sa.address SET geocode_status='pending'
                    WHERE geocode_status IN ('fail', 'ambiguous')
                    """
                )
                conn.commit()

            # только НУЖНЫЕ адреса: прикреплённые к школам
            cur.execute(
                """
                SELECT a.address_id, a.city, a.district, a.street_norm, a.house_norm
                FROM sa.address a
                WHERE a.geocode_status = 'pending' AND a.latitude IS NULL
                  AND EXISTS (SELECT 1 FROM sa.school_address s WHERE s.address_id = a.address_id)
                ORDER BY a.address_id
                LIMIT %s
                """,
                (budget,),
            )
            rows = cur.fetchall()
            print(f"[daily] к геокодированию в этой пачке: {len(rows)} (бюджет {budget})")

            for row in rows:
                if done >= budget:
                    break
                query = normalize_query(row["city"], row["district"], row["street_norm"], row["house_norm"])
                try:
                    status, lat, lon, resolved = geocode_once(api_key, query)
                except Exception as e:
                    print("ERROR", row["address_id"], str(e)[:80])
                    time.sleep(1)
                    continue
                cur.execute(
                    """
                    UPDATE sa.address
                    SET latitude=%s, longitude=%s, geocode_status=%s,
                        resolved=COALESCE(%s, resolved), geocoded_at=CURRENT_TIMESTAMP
                    WHERE address_id=%s
                    """,
                    (lat, lon, status, resolved, row["address_id"]),
                )
                conn.commit()
                done += 1
                if status == "ok":
                    ok += 1
                elif status == "ambiguous":
                    ambiguous += 1
                else:
                    fail += 1
                time.sleep(0.12)

            cur.execute(
                "SELECT count(*) FROM sa.address WHERE geocode_status='pending'"
            )
            pending_left = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO sa.geocode_log (provider, requests, ok_count, ambiguous_count,
                                            fail_count, pending_left)
                VALUES ('yandex', %s, %s, %s, %s, %s)
                """,
                (done, ok, ambiguous, fail, pending_left),
            )
            cur.execute(
                """
                SELECT COALESCE(SUM(requests), 0) FROM sa.geocode_log
                WHERE run_date = CURRENT_DATE
                """
            )
            spent_after = cur.fetchone()[0]
    finally:
        conn.close()

    print(
        f"[daily] прогон: {done} (ok {ok} / ambiguous {ambiguous} / fail {fail}) | "
        f"осталось pending: {pending_left} | потрачено сегодня: {spent_after}/1000"
    )


if __name__ == "__main__":
    main()
