#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Перенос данных из JSON (парсинг Госуслуг + инфраструктура) в Excel.

Вход:
  parsing/school_gosuslugi/sg_data/sg_data_output/sd_2_stage_gosuslugi_infrastucture_output_extract.json

Выход:
  school_data/sd_2_stage_gosuslugi/Здания школ2.xlsx
  Лист: «Информация о школах Саратова» (как в sd_2_stage/from_excel_to_json/s_read_excel.py)

Базовые столбцы — обратное соответствие column_mapping из s_read_excel.py.
Дополнительные столбцы (Госуслуги): при отсутствии значения в JSON пишется «нету».
"""

from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook

BASE_DIR = Path(__file__).resolve().parents[2]
INPUT_JSON_PATH = (
    BASE_DIR
    / "parsing"
    / "school_gosuslugi"
    / "sg_data"
    / "sg_data_output"
    / "sd_2_stage_gosuslugi_infrastucture_output_extract.json"
)
OUTPUT_EXCEL_PATH = BASE_DIR / "school_data" / "sd_2_stage_gosuslugi" / "Здания школ2.xlsx"
SHEET_NAME = "Информация о школах Саратова"
RATING_COLUMN = ("Итоговый рейтинг", "rating_overall_equal_weights")

# Как в s_read_excel.py: заголовок Excel -> ключ JSON
COLUMN_MAPPING: dict[str, str] = {
    "ID": "id",
    "Название на 2ГИС": "name_2gis",
    "Короткое название": "short_name",
    "Адрес": "address",
    "Тип здания": "building_type",
    "S, м2": "area_sqm",
    "Этажей": "floors",
    "Подз/э": "underground_floors",
    "Матер": "material",
    "г/пост": "year_built",
    "реконструкция": "reconstruction_year",
    "вместимость": "capacity",
    "ФОК": "has_sports_complex",
    "бассейн": "has_pool",
    "стадион": "has_stadium",
    "спортплощадка": "has_sports_ground",
    "Широта": "latitude",
    "Долгота": "longitude",
    "Кадастровый номер": "cadastral_number",
    "Рейтинг 2ГИС": "rating_2gis",
    "Рейтинг Яндекс": "rating_yandex",
    "Ссылка на Яндекс": "link_yandex",
    "Ссылка на отзывы Яндекс": "reviews_link_yandex",
    "Ссылка на 2ГИС": "link_2gis",
    "Ссылка на отзывы 2ГИС": "reviews_link_2gis",
}

# Дополнительные поля парсера; если ключа нет или значение пустое — «нету»
GOSUSLUGI_COLUMNS: list[tuple[str, str]] = [
    ("Ссылка Госуслуги", "link_gosuslugi"),
    ("Профильные направления", "specialization"),
    ("ЕГЭ", "EGE"),
    ("ВУЗы", "VUZ"),
    ("Олимпиады", "Olympiads"),
    ("МТО (URL)", "infrastructure"),
    ("Инфраструктура (спорт)", "infrastucture"),
]


def format_base_value(value: object) -> object:
    """Пустые значения в Excel — пустая ячейка."""
    if value is None:
        return None
    return value


def format_gosuslugi_value(school: dict, key: str) -> str:
    """Отсутствующие/пустые поля Госуслуг — строка «нету»."""
    if key not in school:
        return "нету"
    val = school[key]
    if val is None:
        return "нету"
    if isinstance(val, list):
        if not val:
            return "нету"
        return "; ".join(str(x) for x in val)
    s = str(val).strip()
    if not s or s.lower() in {"none", "null"}:
        return "нету"
    return s


def main() -> None:
    if not INPUT_JSON_PATH.exists():
        raise FileNotFoundError(f"JSON не найден: {INPUT_JSON_PATH}")

    with open(INPUT_JSON_PATH, "r", encoding="utf-8") as f:
        schools: list[dict] = json.load(f)

    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = SHEET_NAME

    base_headers = list(COLUMN_MAPPING.keys())
    gos_headers = [h for h, _ in GOSUSLUGI_COLUMNS]
    headers = base_headers + gos_headers + [RATING_COLUMN[0]]

    for col, title in enumerate(headers, start=1):
        ws.cell(row=1, column=col, value=title)

    json_keys_base = list(COLUMN_MAPPING.values())

    for row_idx, school in enumerate(schools, start=2):
        for col_idx, jkey in enumerate(json_keys_base, start=1):
            val = school.get(jkey)
            ws.cell(row=row_idx, column=col_idx, value=format_base_value(val))

        col_offset = len(json_keys_base)
        for i, (_, jkey) in enumerate(GOSUSLUGI_COLUMNS, start=1):
            ws.cell(
                row=row_idx,
                column=col_offset + i,
                value=format_gosuslugi_value(school, jkey),
            )
        ws.cell(
            row=row_idx,
            column=col_offset + len(GOSUSLUGI_COLUMNS) + 1,
            value=school.get(RATING_COLUMN[1]),
        )

    OUTPUT_EXCEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUTPUT_EXCEL_PATH)
    print(f"[OK] Школ: {len(schools)}")
    print(f"[OK] Сохранено: {OUTPUT_EXCEL_PATH}")


if __name__ == "__main__":
    main()
