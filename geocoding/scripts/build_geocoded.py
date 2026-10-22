#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сборка gc_data/gc_output/geocoded.json из addresses.json + _cache.json.

Формат: школа один раз (id, label, district) + улицы с points [[lat, lon], ...]

Запуск: python geocoding/scripts/build_geocoded.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gc_data"))

from geocode_gc_ans_matched import (  # noqa: E402
    MAX_POINTS,
    cache_key,
    list_house_tokens,
    normalize_street_cell,
    sample_evenly,
)
from paths import ADDRESSES_JSON, CACHE_JSON, GEOCODED_JSON, LEGACY_ADDRESSES, LEGACY_CACHE  # noqa: E402


def load_addresses() -> list[dict]:
    path = ADDRESSES_JSON if ADDRESSES_JSON.is_file() else LEGACY_ADDRESSES
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("data", [])


def load_cache_points() -> dict:
    for path in (CACHE_JSON, LEGACY_CACHE):
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8")).get("points", {})
    return {}


def street_cache_key(district: str, street: str) -> str:
    return f"__street__|{district}|{normalize_street_cell(street)}"


def points_for_row(district: str, street: str, houses: str, cache: dict) -> list[list[float]]:
    street_n = normalize_street_cell(street)
    out: list[list[float]] = []

    if "все дома" in (houses or "").lower():
        arr = cache.get(street_cache_key(district, street_n))
        if isinstance(arr, list):
            for p in sample_evenly(arr, MAX_POINTS):
                lat, lon = p.get("lat"), p.get("lon")
                if lat is not None and lon is not None:
                    out.append([lat, lon])
        return out

    tokens = list_house_tokens(houses)
    if not tokens:
        return out

    for house in sample_evenly(tokens, MAX_POINTS):
        c = cache.get(cache_key(district, street_n, house))
        if c and isinstance(c, dict) and c.get("lat") is not None:
            out.append([c["lat"], c["lon"]])
    return out


def main() -> None:
    rows = load_addresses()
    cache = load_cache_points()

    # school_id -> aggregated
    by_school: dict[int, dict] = {}

    for row in rows:
        sid = row.get("school_id")
        if sid is None:
            continue
        if sid not in by_school:
            by_school[sid] = {
                "id": sid,
                "label": row.get("label") or "",
                "district": (row.get("district") or "").strip(),
                "streets": [],
            }
        pts = points_for_row(
            by_school[sid]["district"],
            row.get("street") or "",
            row.get("houses") or "",
            cache,
        )
        by_school[sid]["streets"].append(
            {
                "name": normalize_street_cell(row.get("street") or ""),
                "points": pts,
            }
        )

    result = sorted(by_school.values(), key=lambda s: (s["district"], s["label"]))

    GEOCODED_JSON.parent.mkdir(parents=True, exist_ok=True)
    GEOCODED_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    n_pts = sum(len(st["points"]) for s in result for st in s["streets"])
    print(f"[OK] {len(result)} школ, {n_pts} точек → {GEOCODED_JSON}")


if __name__ == "__main__":
    main()
