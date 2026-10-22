#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Входной файл: gc_data/gc_input/addresses.json
(совпавшие школы из CSV + id из final_school_data)

Запуск: python geocoding/scripts/build_gc_matched_input.py
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "school_data"))
sys.path.insert(0, str(REPO / "geocoding" / "gc_data"))

from compare_schools_ans_final import (  # noqa: E402
    extract_signature,
    load_csv_schools,
    load_json_schools,
    match_key,
    sig_label,
)
from paths import ADDRESSES_JSON, GC_INPUT  # noqa: E402

CSV_PATH = REPO / "adreses_nears_school" / "ans_data" / "ans_stage1_adres_near_school_2.csv"
JSON_PATH = REPO / "school_data" / "final_school_data.json"


def main() -> None:
    json_by = load_json_schools()
    csv_by = load_csv_schools()
    matched_keys = set(json_by.keys()) & set(csv_by.keys())

    # (district, label) -> primary school id
    school_id_map: dict[tuple[str, str], int] = {}
    for key in matched_keys:
        sig, district = key
        label = sig_label(sig)
        ids = [x["id"] for x in json_by[key] if x.get("id") is not None]
        if ids:
            school_id_map[(district, label)] = min(ids)

    rows: list[dict] = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter=";"):
            name = (row.get("Краткое наименование ОУ") or "").strip()
            district = (row.get("Район") or "").strip()
            sig = extract_signature(name)
            if not sig or match_key(sig, district) not in matched_keys:
                continue
            label = sig_label(sig)
            sid = school_id_map.get((district, label))
            rows.append(
                {
                    "school_id": sid,
                    "label": label,
                    "district": district,
                    "street": (row.get("Название улицы") or "").strip(),
                    "houses": (row.get("Номера домов") or "").strip(),
                }
            )

    GC_INPUT.mkdir(parents=True, exist_ok=True)
    ADDRESSES_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] {len(rows)} строк → {ADDRESSES_JSON}")


if __name__ == "__main__":
    main()
