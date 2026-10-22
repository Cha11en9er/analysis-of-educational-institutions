#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Геокодирование адресов из ans_stage1_adres_near_school.csv для выбранных школ,
сборка UI/src/data/geocoded_addresses_by_school.json (включая sosh6 из готового файла).

Требуется YANDEX_API_KEY в .env в корне репозитория (или в geocoding/).

Запуск из корня репозитория:
  python geocoding/scripts/geocode_ans_stage1_bundle.py
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = REPO_ROOT / "adreses_nears_school" / "ans_data" / "ans_stage1_adres_near_school.csv"
SOSH6_PATH = REPO_ROOT / "UI" / "src" / "data" / "geocoded_addresses_sosh6.json"
OUT_PATH = REPO_ROOT / "UI" / "src" / "data" / "geocoded_addresses_by_school.json"
CACHE_PATH = REPO_ROOT / "geocoding" / "scripts" / "_geocode_bundle_cache.json"

SARATOV_CENTER = "51.53, 46.00"
SEARCH_RADIUS = "1.5, 1.5"
BASE_URL = "https://geocode-maps.yandex.ru/1.x/"
REGION = "Саратовская область"
CITY = "Саратов"

# Вставка пути к gc_near_school_find_house_number (все дома)
_GC_SRC = REPO_ROOT / "geocoding" / "gc_find_adreses_near_school" / "gc_near_school_src"
if _GC_SRC.is_dir():
    sys.path.insert(0, str(_GC_SRC))


def load_env() -> str | None:
    for p in (REPO_ROOT / ".env", REPO_ROOT / "geocoding" / ".env"):
        if p.is_file():
            load_dotenv(p)
    return os.getenv("YANDEX_API_KEY")


def school_bundle_key(school_cell: str) -> str | None:
    """Ключ должен совпадать с getSchoolAttachmentKey в UI."""
    if not school_cell:
        return None
    if "Лицей № 62" in school_cell or "Лицей №62" in school_cell:
        return "lyceum62"
    if re.search(r"Гимназия\s*№\s*1(?!\d)", school_cell, re.I):
        return "gymnasium1"
    if re.search(r"СОШ\s*№\s*95", school_cell, re.I):
        return "sosh95"
    if re.search(r"СОШ\s*№\s*45(?!\d)", school_cell, re.I):
        return "sosh45"
    return None


def street_from_cell(street_cell: str) -> str:
    if not street_cell or not street_cell.strip():
        return ""
    first = street_cell.split(",")[0].strip()
    first = re.sub(
        r"\s+\d+[а-яА-ЯёЁa-zA-Z0-9/\-]*$",
        "",
        first,
    ).strip()
    return first


def expand_house_token(token: str) -> list[str]:
    t = token.strip()
    if not t or t.lower() in ("все дома", "все"):
        return []
    t_compact = t.replace(" ", "")
    m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", t_compact)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if a <= b and b - a <= 100:
            return [str(i) for i in range(a, b + 1)]
    return [t]


def iter_house_tokens(houses_raw: str):
    if not houses_raw:
        return
    for part in re.split(r"[;,]", houses_raw):
        t = part.strip()
        if not t:
            continue
        for ex in expand_house_token(t):
            if ex:
                yield ex


def normalize_street_cell(street: str) -> str:
    """Убираем хвостовые «:» и лишние пробелы из названия улицы в CSV."""
    return street.strip().rstrip(":").strip()


def geocode_address(api_key: str, full_address: str) -> dict | None:
    params = {
        "format": "json",
        "geocode": full_address,
        "apikey": api_key,
        "results": 1,
        "ll": SARATOV_CENTER,
        "spn": SEARCH_RADIUS,
    }
    if re.search(r"(\bд\.\s*\d|,?\s*\d+[а-яА-Яa-zA-Z/]*\s*)$", full_address, re.I):
        params["kind"] = "house"
    try:
        r = requests.get(BASE_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        coll = data["response"]["GeoObjectCollection"]
        found = int(coll["metaDataProperty"]["GeocoderResponseMetaData"]["found"])
        if found < 1:
            return None
        geo = coll["featureMember"][0]["GeoObject"]
        lon, lat = map(float, geo["Point"]["pos"].split())
        meta = geo.get("metaDataProperty", {}).get("GeocoderMetaData", {})
        env = geo.get("boundedBy", {}).get("Envelope", {})
        out = {
            "lat": lat,
            "lon": lon,
            "address": full_address,
            "region": REGION,
            "city": CITY,
            "resolved": meta.get("text"),
        }
        if env:
            lc = env.get("lowerCorner")
            uc = env.get("upperCorner")
            if lc and uc:
                out["bounded_by"] = {"lowerCorner": lc, "upperCorner": uc}
        return out
    except Exception:
        return None


_SETTLEMENT_STREET_RE = re.compile(
    r"^(д|с|п|ст)\.?\s+(.+?)\s+ул\.\s+(.+)$",
    re.IGNORECASE,
)
_SETTLEMENT_LABEL = {
    "д": "деревня",
    "с": "село",
    "п": "посёлок",
    "ст": "станция",
}


def parse_settlement_street(street_cell: str) -> tuple[str, str, str] | None:
    """
    «д Расловка ул. Песчанная» → (деревня, Расловка, Песчанная).
    Для посёлков/сёл/деревьев вне черты Саратова.
    """
    m = _SETTLEMENT_STREET_RE.match(street_cell.strip())
    if not m:
        return None
    kind, place, street_name = m.group(1).lower(), m.group(2).strip(), m.group(3).strip()
    return _SETTLEMENT_LABEL.get(kind, kind), place, street_name


def _street_in_query(street: str) -> str:
    """Не добавляем «ул.» для взвозов, проездов и т.п."""
    low = street.lower()
    if any(
        m in low
        for m in (
            "взвоз",
            "проезд",
            "переулок",
            "тупик",
            "набережная",
            "площадь",
            "шоссе",
            "бульвар",
            "аллея",
            "тракт",
        )
    ):
        return street
    return f"ул. {street}"


def city_address_variants(district: str, street: str, house: str) -> list[str]:
    """Варианты запроса для адресов в черте г. Саратова (всегда с областью и городом)."""
    street = normalize_street_cell(street)
    street_q = _street_in_query(street)
    d = district.strip()
    h = house.strip()
    return [
        f"Россия, {REGION}, {CITY}, {d} район, {street_q}, д. {h}",
        f"{REGION}, {CITY}, {d} район, {street_q}, д. {h}",
        f"{REGION}, {CITY}, {d} район, {street}, д. {h}",
        f"{REGION}, г. {CITY}, {d} район, {street_q}, д. {h}",
        f"{CITY}, {d} район, {street_q}, д. {h}",
    ]


def settlement_address_variants(
    district: str, stype: str, place: str, street_name: str, house: str
) -> list[str]:
    h = house.strip()
    d = district.strip()
    return [
        f"Россия, {REGION}, {d} район, {stype} {place}, ул. {street_name}, {h}",
        f"{REGION}, {d} район, {stype} {place}, ул. {street_name}, {h}",
        f"{REGION}, {stype} {place}, ул. {street_name}, {h}",
        f"{stype} {place}, ул. {street_name}, {h}, {REGION}",
    ]


def try_geocode_house(district: str, street: str, house: str, api_key: str) -> dict | None:
    street = normalize_street_cell(street)
    variants: list[str] = []
    settlement = parse_settlement_street(street)
    if settlement:
        stype, place, street_name = settlement
        variants.extend(settlement_address_variants(district, stype, place, street_name, house))
    variants.extend(city_address_variants(district, street, house))
    seen: set[str] = set()
    for addr in variants:
        if addr in seen:
            continue
        seen.add(addr)
        res = geocode_address(api_key, addr)
        if res:
            return res
    return None


def street_all_houses(district: str, street: str, api_key: str) -> list[dict]:
    try:
        from gc_near_school_find_house_number import get_points_for_street
    except ImportError:
        return []
    pts = get_points_for_street(street=street, district=district, city="Саратов", max_results=250)
    out = []
    for p in pts:
        out.append(
            {
                "lat": p["latitude"],
                "lon": p["longitude"],
                "address": p.get("address", ""),
            }
        )
    return out


def process_csv_rows(api_key: str, cache: dict) -> dict[str, list[dict]]:
    """Ключ -> список уникальных точек {lat, lon, address, bounded_by?}."""
    by_key: dict[str, dict[tuple[float, float], dict]] = {k: {} for k in ("lyceum62", "gymnasium1", "sosh95", "sosh45")}

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            school = (row.get("Краткое наименование ОУ") or "").strip()
            key = school_bundle_key(school)
            if not key:
                continue
            district = (row.get("Район") or "").strip()
            sc = (row.get("Название улицы") or "").strip()
            houses_raw = (row.get("Номера домов") or "").strip()

            street = street_from_cell(sc)
            if "все дома" in houses_raw.lower() and street:
                for item in street_all_houses(district, street, api_key):
                    lk = (round(item["lat"], 6), round(item["lon"], 6))
                    by_key[key][lk] = item
                time.sleep(0.2)
                continue

            if not street and houses_raw:
                # Попытка: вся строка номеров как хвост адреса (один запрос на сегмент)
                addr = f"{REGION}, {CITY}, {district} район, {houses_raw[:120]}"
                ck = cache.get("addr", {}).get(addr)
                if ck is not None:
                    res = ck
                else:
                    res = geocode_address(api_key, addr)
                    cache.setdefault("addr", {})[addr] = res
                    time.sleep(0.12)
                if res:
                    lk = (round(res["lat"], 6), round(res["lon"], 6))
                    by_key[key][lk] = res
                continue

            if not street:
                continue

            for house in iter_house_tokens(houses_raw):
                addr_try = f"{REGION}, {CITY}, {district} район, ул. {street}, д. {house}"
                ck = cache.get("addr", {}).get(addr_try)
                if ck is not None:
                    res = ck
                else:
                    res = try_geocode_house(district, street, house, api_key)
                    cache.setdefault("addr", {})[addr_try] = res
                    time.sleep(0.12)
                if res:
                    lk = (round(res["lat"], 6), round(res["lon"], 6))
                    by_key[key][lk] = res

    return {k: list(v.values()) for k, v in by_key.items()}


def main() -> None:
    api_key = load_env()
    if not api_key:
        print("Нет YANDEX_API_KEY — задайте ключ в .env в корне репозитория.")
        sys.exit(1)

    cache: dict = {}
    if CACHE_PATH.is_file():
        try:
            cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cache = {}

    print("Чтение CSV и геокодирование (долго при первом запуске)...", flush=True)
    fresh = process_csv_rows(api_key, cache)

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    sosh6: list = []
    if SOSH6_PATH.is_file():
        sosh6 = json.loads(SOSH6_PATH.read_text(encoding="utf-8"))

    bundle = {
        "sosh6": sosh6,
        **fresh,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")

    for k, v in bundle.items():
        print(f"  {k}: {len(v)} точек", flush=True)
    print(f"\n[OK] -> {OUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
