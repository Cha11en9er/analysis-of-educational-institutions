#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Добавляет поле link_gosuslugi в JSON школ на основе Excel-листа со ссылками.

Вход:
- school_data/sd_2_stage/Здания школ.xlsx (лист "ссылка_госуслуги")
- school_data/sd_2_stage/sd_2_stage_schools.json

Выход:
- school_data/sd_2_stage_gosuslugi/sd_2_stage_gosuslugi.json
"""

from __future__ import annotations

import json
from pathlib import Path

from openpyxl import load_workbook

BASE_DIR = Path(__file__).resolve().parents[2]
EXCEL_PATH = BASE_DIR / "school_data" / "sd_2_stage" / "Здания школ.xlsx"
INPUT_JSON_PATH = BASE_DIR / "school_data" / "sd_2_stage" / "sd_2_stage_schools.json"
OUTPUT_JSON_PATH = BASE_DIR / "school_data" / "sd_2_stage_gosuslugi" / "sd_2_stage_gosuslugi.json"


def normalize_link(raw) -> str | None:
    """Пустые/нет-значения -> None, иначе строка ссылки."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text.lower() in {"нет", "нету", "none", "null", "-", "—"}:
        return None
    return text


def pick_links_sheet(workbook):
    """
    Ищет лист со ссылками:
    1) точное имя "ссылка_госуслуги"
    2) fallback: лист с 3 колонками, где первая колонка "ID"
    """
    if "ссылка_госуслуги" in workbook.sheetnames:
        return workbook["ссылка_госуслуги"]

    for name in workbook.sheetnames:
        ws = workbook[name]
        header_id = ws.cell(1, 1).value
        if ws.max_column >= 3 and str(header_id).strip().lower() == "id":
            # Лист со структурой: ID | название | ссылка
            return ws

    raise RuntimeError("Не найден лист со ссылками (ожидался 'ссылка_госуслуги').")


def read_links_from_excel() -> dict[int, str | None]:
    wb = load_workbook(EXCEL_PATH, data_only=True)
    ws = pick_links_sheet(wb)

    links_by_id: dict[int, str | None] = {}
    # 1-я строка — заголовок
    for row_idx in range(2, ws.max_row + 1):
        raw_id = ws.cell(row_idx, 1).value
        raw_link = ws.cell(row_idx, 3).value

        if raw_id is None:
            continue
        try:
            school_id = int(raw_id)
        except (TypeError, ValueError):
            continue

        links_by_id[school_id] = normalize_link(raw_link)

    return links_by_id


def main() -> None:
    if not EXCEL_PATH.exists():
        raise FileNotFoundError(f"Excel не найден: {EXCEL_PATH}")
    if not INPUT_JSON_PATH.exists():
        raise FileNotFoundError(f"JSON не найден: {INPUT_JSON_PATH}")

    links_by_id = read_links_from_excel()

    with open(INPUT_JSON_PATH, "r", encoding="utf-8") as f:
        schools = json.load(f)

    updated = 0
    from_excel = 0
    not_in_excel = 0

    for school in schools:
        school_id = school.get("id")
        try:
            sid = int(school_id)
        except (TypeError, ValueError):
            school["link_gosuslugi"] = "нету в excel"
            not_in_excel += 1
            continue

        if sid in links_by_id:
            school["link_gosuslugi"] = links_by_id[sid]
            from_excel += 1
        else:
            school["link_gosuslugi"] = "нету в excel"
            not_in_excel += 1
        updated += 1

    OUTPUT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(schools, f, ensure_ascii=False, indent=4)

    print(f"[OK] Обновлено объектов: {updated}")
    print(f"[OK] Найдено в excel: {from_excel}")
    print(f"[OK] Нету в excel: {not_in_excel}")
    print(f"[OK] Сохранено: {OUTPUT_JSON_PATH}")


if __name__ == "__main__":
    main()
