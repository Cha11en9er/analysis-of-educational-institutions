#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scmed.xlsx → price/prices.json

Если школа встречается в нескольких строках / с разными классами —
берётся медиана цен (цена строки относится ко всем школам в ячейке).

Запуск: python price/prepare_price.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from statistics import median

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "school_data"))

from compare_schools_ans_final import extract_signature, sig_label  # noqa: E402

XLSX = Path(__file__).resolve().parent / "scmed.xlsx"
FINAL_JSON = ROOT / "school_data" / "final_school_data.json"
OUT_JSON = Path(__file__).resolve().parent / "prices.json"


def split_segments(cell: str) -> list[str]:
    return [p.strip() for p in re.split(r"[,;]", cell) if p.strip()]


def load_prices_by_signature() -> dict[tuple, list[float]]:
    df = pd.read_excel(XLSX)
    by_sig: dict[tuple, list[float]] = {}
    for _, row in df.iterrows():
        price = float(row["Цена"])
        for part in split_segments(str(row["Школа"])):
            sig = extract_signature(part)
            if sig:
                by_sig.setdefault(sig, []).append(price)
    return by_sig


def load_final_by_signature() -> dict[tuple, list[dict]]:
    with open(FINAL_JSON, encoding="utf-8") as f:
        schools = json.load(f)
    by_sig: dict[tuple, list[dict]] = {}
    for s in schools:
        sig = extract_signature(s.get("short_name") or "") or extract_signature(
            s.get("name_2gis") or ""
        )
        if not sig:
            continue
        by_sig.setdefault(sig, []).append(s)
    return by_sig


def main() -> None:
    prices_by_sig = load_prices_by_signature()
    final_by_sig = load_final_by_signature()

    result: list[dict] = []
    unmatched_excel: list[str] = []
    unmatched_final: list[str] = []

    for sig, prices in sorted(prices_by_sig.items(), key=lambda x: sig_label(x[0])):
        med = int(round(median(prices)))
        finals = final_by_sig.get(sig)
        if not finals:
            unmatched_excel.append(sig_label(sig))
            continue
        for s in finals:
            result.append(
                {
                    "school": s.get("short_name") or s.get("name_2gis"),
                    "id": s["id"],
                    "price": med,
                }
            )

    priced_sigs = set(prices_by_sig.keys())
    for sig in final_by_sig:
        if sig not in priced_sigs:
            unmatched_final.append(sig_label(sig))

    result.sort(key=lambda x: x["id"])

    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] {OUT_JSON}")
    print(f"  записей: {len(result)} (школ с ценой: {len(priced_sigs)})")
    if unmatched_excel:
        print(f"  из Excel без id в final ({len(unmatched_excel)}): {', '.join(unmatched_excel[:8])}")
        if len(unmatched_excel) > 8:
            print(f"    … ещё {len(unmatched_excel) - 8}")
    if unmatched_final:
        print(f"  в final без цены ({len(unmatched_final)}): {', '.join(unmatched_final[:8])}")
        if len(unmatched_final) > 8:
            print(f"    … ещё {len(unmatched_final) - 8}")

    s54 = [r for r in result if r.get("school") == "Школа №54"]
    if s54:
        print(f"  пример СОШ №54: {s54[0]}")


if __name__ == "__main__":
    main()
