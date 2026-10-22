#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Геокодирование одной строки ans_stage1 (формат CSV через «;»).

Пример:
  python geocoding/scripts/geocode_ans_line.py "Волжский;МОУ «РПКГ»;Троицкий взвоз;3, 5"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from geocode_ans_stage1_bundle import iter_house_tokens, load_env, try_geocode_house


def geocode_line(line: str, api_key: str) -> list[dict]:
    parts = [p.strip() for p in line.strip().split(";")]
    if len(parts) < 4:
        raise ValueError(f"Нужно минимум 4 поля через «;», получено: {line!r}")

    district, school, street, houses_raw = parts[0], parts[1], parts[2], parts[3]
    out: list[dict] = []

    for house in iter_house_tokens(houses_raw):
        res = try_geocode_house(district, street, house, api_key)
        out.append(
            {
                "region": "Саратовская область",
                "city": "Саратов",
                "district": district,
                "school": school,
                "street": street,
                "house": house,
                "lat": res["lat"] if res else None,
                "lon": res["lon"] if res else None,
                "query": res.get("address") if res else None,
                "resolved": res.get("resolved") if res else None,
                "bounded_by": res.get("bounded_by") if res else None,
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Геокодирование строки ans_stage1")
    parser.add_argument("line", nargs="?", help="Район;Школа;Улица;Дома")
    args = parser.parse_args()

    line = args.line
    if not line:
        line = sys.stdin.read().strip()
    if not line:
        parser.error("Укажите строку аргументом или через stdin")

    api_key = load_env()
    if not api_key:
        print("Нет YANDEX_API_KEY в .env", file=sys.stderr)
        sys.exit(1)

    results = geocode_line(line, api_key)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    found = sum(1 for r in results if r["lat"] is not None)
    print(f"\n[OK] {found}/{len(results)} точек", file=sys.stderr)


if __name__ == "__main__":
    main()
