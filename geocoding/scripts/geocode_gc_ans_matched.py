#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Геокодирование addresses.json → кэш → geocoded.json (до 8 точек на улицу).

  python geocoding/scripts/geocode_gc_ans_matched.py
  python geocoding/scripts/geocode_gc_ans_matched.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO_ROOT / "geocoding" / "gc_data"))

from geocode_ans_stage1_bundle import (  # noqa: E402
    expand_house_token,
    geocode_address,
    load_env,
    normalize_street_cell,
    street_all_houses,
    try_geocode_house,
)
from paths import ADDRESSES_JSON, CACHE_JSON, LEGACY_ADDRESSES, LEGACY_CACHE  # noqa: E402

MAX_POINTS = 8
REQUEST_DELAY_SEC = 0.15


def list_house_tokens(houses_raw: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    if not houses_raw:
        return out
    for part in re.split(r"[;,]", houses_raw):
        t = part.strip()
        if not t:
            continue
        for ex in expand_house_token(t):
            if ex and ex not in seen:
                seen.add(ex)
                out.append(ex)
    return out


def sample_evenly(items: list, max_n: int = MAX_POINTS) -> list:
    n = len(items)
    if n <= max_n:
        return list(items)
    if max_n <= 1:
        return [items[0]]
    picked: list = []
    used_idx: set[int] = set()
    for i in range(max_n):
        idx = min(n - 1, max(0, int(round(i * (n - 1) / (max_n - 1)))))
        if idx in used_idx:
            continue
        used_idx.add(idx)
        picked.append(items[idx])
    if len(picked) < max_n:
        for j in range(n):
            if j not in used_idx:
                used_idx.add(j)
                picked.append(items[j])
            if len(picked) >= max_n:
                break
    return picked[:max_n]


def cache_key(district: str, street: str, house: str) -> str:
    return f"{district}|{normalize_street_cell(street)}|{house}"


def load_rows() -> list[dict]:
    path = ADDRESSES_JSON if ADDRESSES_JSON.is_file() else LEGACY_ADDRESSES
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("data", [])


def load_cache() -> dict:
    for path in (CACHE_JSON, LEGACY_CACHE):
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
    return {"points": {}}


def save_cache(cache: dict) -> None:
    CACHE_JSON.parent.mkdir(parents=True, exist_ok=True)
    CACHE_JSON.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def geocode_house_cached(api_key: str, district: str, street: str, house: str, cache: dict) -> bool:
    ck = cache_key(district, street, house)
    if ck in cache["points"]:
        return False
    res = try_geocode_house(district, street, house, api_key)
    if res:
        cache["points"][ck] = {"lat": res["lat"], "lon": res["lon"]}
        return True
    return True


def points_from_street(api_key: str, district: str, street: str, cache: dict, delay: float) -> int:
    sk = f"__street__|{district}|{normalize_street_cell(street)}"
    if sk in cache["points"]:
        return 0
    pts = street_all_houses(district, normalize_street_cell(street), api_key)
    time.sleep(delay)
    cache["points"][sk] = [
        {"lat": p["latitude"], "lon": p["longitude"]}
        for p in pts
        if p.get("latitude") is not None
    ]
    return 2


def estimate_requests(rows: list[dict]) -> tuple[int, int]:
    total = 0
    for row in rows:
        houses_raw = (row.get("houses") or "").strip()
        if "все дома" in houses_raw.lower():
            total += 2
            continue
        tokens = list_house_tokens(houses_raw)
        total += len(sample_evenly(tokens, MAX_POINTS)) if tokens else 1
    return total, len(rows)


def process_row(api_key: str, row: dict, cache: dict, stats: dict, delay: float) -> int:
    district = (row.get("district") or "").strip()
    street = normalize_street_cell((row.get("street") or "").strip())
    houses_raw = (row.get("houses") or "").strip()
    n_pts = 0

    if "все дома" in houses_raw.lower():
        stats["api_calls"] += points_from_street(api_key, district, street, cache, delay)
        sk = f"__street__|{district}|{street}"
        arr = cache["points"].get(sk, [])
        n_pts = len(sample_evenly(arr, MAX_POINTS)) if isinstance(arr, list) else 0
        return n_pts

    tokens = list_house_tokens(houses_raw)
    if not tokens:
        stats["api_calls"] += 1
        res = geocode_address(api_key, f"Россия, Саратовская область, Саратов, {district} район, {street}")
        time.sleep(delay)
        return 1 if res else 0

    for house in sample_evenly(tokens, MAX_POINTS):
        ck = cache_key(district, street, house)
        if ck not in cache["points"]:
            stats["api_calls"] += 1
            geocode_house_cached(api_key, district, street, house, cache)
            if ck not in cache["points"]:
                stats["failed"] += 1
        time.sleep(delay)
        if ck in cache["points"]:
            n_pts += 1
    return n_pts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY_SEC)
    args = parser.parse_args()

    rows = load_rows()
    if args.limit > 0:
        rows = rows[: args.limit]

    if args.dry_run:
        req, n = estimate_requests(rows)
        print(f"Строк: {n}, запросов ~{req}, дней при 1000/сутки: ~{max(1, (req + 999) // 1000)}")
        return

    api_key = load_env()
    if not api_key:
        print("Нет YANDEX_API_KEY", file=sys.stderr)
        sys.exit(1)

    cache = load_cache()
    stats = {"api_calls": 0, "failed": 0}
    t0 = time.time()

    for i, row in enumerate(rows, start=1):
        n_pts = process_row(api_key, row, cache, stats, args.delay)
        if i % 25 == 0:
            save_cache(cache)
            print(f"  [{i}/{len(rows)}] +{n_pts} т. | ~{stats['api_calls']} запр. | {time.time()-t0:.0f} с", flush=True)

    save_cache(cache)

    from build_geocoded import main as build_out  # noqa: E402

    build_out()
    print(f"  неудач: {stats['failed']}, запросов: ~{stats['api_calls']}, {(time.time()-t0)/60:.1f} мин")


if __name__ == "__main__":
    main()
