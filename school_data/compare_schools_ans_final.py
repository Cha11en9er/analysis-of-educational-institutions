#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сопоставление школ: final_school_data.json ↔ ans_stage1 CSV.

Ключ сопоставления: тип ОУ (СОШ/лицей/гимназия/…) + номер + район.
Точное совпадение названий не используется.
"""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
JSON_PATH = REPO / "school_data" / "final_school_data.json"
CSV_PATH = REPO / "adreses_nears_school" / "ans_data" / "ans_stage1_adres_near_school_2.csv"

DISTRICT_KEYWORDS = {
    "волжск": "Волжский",
    "гагарин": "Гагаринский",
    "заводск": "Заводской",
    "кировск": "Кировский",
    "ленинск": "Ленинский",
    "октябр": "Октябрьский",
    "фрунз": "Фрунзенский",
}

TYPE_RULES: list[tuple[str, str]] = [
    (r"рпкг", "rpkg"),
    (r"иволг", "ivolg"),
    (r"гэл|гэ\s*л", "gel"),
    (r"гимназ", "gym"),
    (r"лице", "lyc"),
    (r"сош|оош|нош|школ", "sosh"),
    (r"колл", "col"),
]


def norm_district(raw: str) -> str:
    if not raw:
        return ""
    low = raw.lower().strip()
    for key, label in DISTRICT_KEYWORDS.items():
        if key in low:
            return label
    return raw.strip()


def extract_signature(name: str) -> tuple | None:
    if not name:
        return None
    n = name.lower()
    n = re.sub(r"[«»\"'()]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()

    stype = "other"
    for pat, code in TYPE_RULES:
        if re.search(pat, n):
            stype = code
            break

    num: int | None = None
    m = re.search(r"№\s*(\d+)", name, re.I)
    if m:
        num = int(m.group(1))
    else:
        m = re.search(r"(?:школа|сош|лицей|гимназия)\s*№?\s*(\d+)", n, re.I)
        if m:
            num = int(m.group(1))

    if stype in ("rpkg", "ivolg", "gel"):
        return (stype, 0)

    if num is not None:
        return (stype, num)

    if re.search(r"\bс\.|село|деревн|р\.п\.|п\.|станц|поселок|посёлок", n):
        slug = re.sub(r"[^a-zа-яё0-9]", "", n)[:50]
        return ("rural", slug)

    slug = re.sub(r"[^a-zа-яё0-9]", "", n)[:50]
    return ("named", slug)


def match_key(sig: tuple, district: str) -> tuple:
    return (sig, norm_district(district))


def street_token(street: str) -> str:
    s = street.lower().strip().rstrip(":")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"^(ул\.?|улица)\s+", "", s)
    return s[:60]


def load_json_schools() -> dict[tuple, list[dict]]:
    with open(JSON_PATH, encoding="utf-8") as f:
        rows = json.load(f)

    by_key: dict[tuple, list[dict]] = defaultdict(list)
    for s in rows:
        sig = extract_signature(s.get("short_name") or "") or extract_signature(
            s.get("name_2gis") or ""
        )
        if not sig:
            continue
        dist = norm_district(s.get("administrative_district") or "")
        by_key[match_key(sig, dist)].append(
            {
                "id": s.get("id"),
                "short_name": s.get("short_name"),
                "name_2gis": s.get("name_2gis"),
                "district": dist,
                "address": s.get("address"),
                "sig": sig,
            }
        )
    return by_key


def load_csv_schools() -> dict[tuple, dict]:
    """Один ключ (sig, district) -> агрегат по CSV."""
    raw: dict[tuple, dict] = {}
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter=";"):
            district = (row.get("Район") or "").strip()
            name = (row.get("Краткое наименование ОУ") or "").strip()
            street = (row.get("Название улицы") or "").strip()
            sig = extract_signature(name)
            if not sig:
                continue
            key = match_key(sig, district)
            if key not in raw:
                raw[key] = {
                    "csv_names": set(),
                    "district": norm_district(district),
                    "sig": sig,
                    "streets": set(),
                    "row_count": 0,
                }
            raw[key]["csv_names"].add(name)
            raw[key]["streets"].add(street_token(street))
            raw[key]["row_count"] += 1
    return raw


def sig_label(sig: tuple) -> str:
    stype, val = sig
    labels = {
        "sosh": "СОШ",
        "lyc": "Лицей",
        "gym": "Гимназия",
        "rpkg": "РПКГ",
        "ivolg": "Иволгино",
        "gel": "ГЭЛ",
        "col": "Колледж",
        "rural": "Сельская",
        "named": "Именная",
        "other": "Прочее",
    }
    t = labels.get(stype, stype)
    if isinstance(val, int) and val:
        return f"{t} №{val}"
    if isinstance(val, str) and val:
        return f"{t} ({val[:25]}…)" if len(val) > 25 else f"{t} ({val})"
    return t


def main() -> None:
    json_by = load_json_schools()
    csv_by = load_csv_schools()

    json_keys = set(json_by)
    csv_keys = set(csv_by)

    matched = json_keys & csv_keys
    only_json = json_keys - csv_keys
    only_csv = csv_keys - json_keys

    # Fallback: match by sig only (ignore district) for unmatched
    json_by_sig: dict[tuple, list[tuple]] = defaultdict(list)
    for k in json_keys:
        json_by_sig[k[0]].append(k)

    csv_by_sig: dict[tuple, list[tuple]] = defaultdict(list)
    for k in csv_keys:
        csv_by_sig[k[0]].append(k)

    weak_json: list[tuple] = []
    weak_csv: list[tuple] = []
    for k in only_json:
        sig = k[0]
        if sig in csv_by_sig and len(csv_by_sig[sig]) == 1:
            weak_json.append((k, csv_by_sig[sig][0]))
    for k in only_csv:
        sig = k[0]
        if sig in json_by_sig and len(json_by_sig[sig]) == 1:
            weak_csv.append((k, json_by_sig[sig][0]))

    print("=" * 70)
    print("Метод: тип ОУ + номер (№N) + административный район")
    print(f"JSON: {len(json_by)} уникальных ключей ({sum(len(v) for v in json_by.values())} записей)")
    print(f"CSV:  {len(csv_by)} уникальных ключей")
    print(f"Совпало (тип+№+район): {len(matched)}")
    print(f"Только в JSON: {len(only_json)}")
    print(f"Только в CSV:  {len(only_csv)}")
    print(f"Возможное совпадение при другом районе: JSON→CSV {len(weak_json)}, CSV→JSON {len(weak_csv)}")
    print()

    def fmt_json(k: tuple) -> str:
        items = json_by[k]
        names = "; ".join(
            f"{x['short_name'] or x['name_2gis']} (id={x['id']})" for x in items[:2]
        )
        if len(items) > 2:
            names += f" …+{len(items)-2}"
        return f"{sig_label(k[0])} | {k[1]} | {names}"

    def fmt_csv(k: tuple) -> str:
        info = csv_by[k]
        name = next(iter(info["csv_names"]))[:70]
        extra = f" (+{len(info['csv_names'])-1} вариантов имён)" if len(info["csv_names"]) > 1 else ""
        return f"{sig_label(k[0])} | {k[1]} | {name}{extra} | {info['row_count']} строк"

    print("--- Только в final_school_data.json ---")
    for k in sorted(only_json, key=lambda x: (x[1], str(x[0]))):
        line = fmt_json(k)
        alt = [c for j, c in weak_json if j == k]
        if alt:
            line += f"  → возможно в CSV как: {fmt_csv(alt[0])}"
        print(line)

    print()
    print("--- Только в ans_stage1 CSV ---")
    for k in sorted(only_csv, key=lambda x: (x[1], str(x[0]))):
        line = fmt_csv(k)
        alt = [j for c, j in weak_csv if c == k]
        if alt:
            line += f"  → возможно в JSON как: {fmt_json(alt[0])}"
        print(line)

    print()
    print("--- Совпали (кратко) ---")
    for k in sorted(matched, key=lambda x: (x[1], str(x[0]))):
        j = json_by[k][0]
        c = csv_by[k]
        print(
            f"{sig_label(k[0])} | {k[1]} | JSON: {j.get('short_name')} | CSV: {next(iter(c['csv_names']))[:50]}"
        )


if __name__ == "__main__":
    main()
