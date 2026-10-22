#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Экспорт final_school_data.json в Excel для заказчика.

Вход:  school_data/final_school_data.json
Выход: school_data/sd_2_stage_gosuslugi/Школа_Саратова_для_заказчика.xlsx
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from openpyxl import Workbook

BASE_DIR = Path(__file__).resolve().parents[2]
INPUT_JSON = BASE_DIR / "school_data" / "final_school_data.json"
OUTPUT_EXCEL = BASE_DIR / "school_data" / "sd_2_stage_gosuslugi" / "Школа_Саратова_для_заказчика.xlsx"
OUTPUT_TPP_EXCEL = BASE_DIR / "school_data" / "Потапов данные школ для ТПП.xlsx"
SHEET_NAME = "Школы Саратова"

# (заголовок Excel, ключ JSON)
EXPORT_COLUMNS: list[tuple[str, str]] = [
    ("ID номер объекта", "id"),
    ("Название на 2ГИС", "name_2gis"),
    ("Короткое название", "short_name"),
    ("Адрес", "address"),
    ("Тип здания", "building_type"),
    ("Итоговый рейтинг", "rating_total"),
    ("Рейтинг 2ГИС", "rating_2gis"),
    ("Рейтинг Яндекс", "rating_yandex"),
    ("Топ-5 ключевых тэгов", "top_tags"),
    ("Рейтинг ЕГЭ", "rating_ege"),
    ("Рейтинг олимпиад", "rating_olympiads"),
    ("Рейтинг поступлений в ВУЗы", "rating_vuz"),
    ("Рейтинг учителей", "rating_teachers"),
    ("Рейтинг МТО и удобства доступа", "rating_mto"),
    ("Рейтинг спортинфраструктуры", "rating_sports_infrastructure"),
    ("Рейтинг Психологического климата", "rating_psychological_climate"),
    ("ЕГЭ, средний балл", "ege_average_score"),
    ("Год ЕГЭ (для приведенного ср. балла)", "ege_year"),
    ("% поступивших в ВУЗ", "university_admission_percent"),
    ("Год ВУЗ (для приведенного % поступивших)", "university_admission_year"),
    ("Количество победителей олимпиад, человек", "olympiad_winners_count"),
    ("Количество лет для приведенного числа олимпиадников", "olympiad_years_span"),
    ("Физико-математический", "profile_phys_math"),
    ("Медико-биологический профиль", "profile_med_bio"),
    ("Социально-экономический профиль", "profile_soc_econ"),
    ("Гуманитарный профиль", "profile_humanitarian"),
    ("Религиозный профиль", "profile_religious"),
    ("ФОК", "fok"),
    ("Бассейн", "pool"),
    ("Стадион (доступность до 15 м.п.)", "stadium"),
    ("Спортплощадка", "sports_ground"),
    ("Широта", "latitude"),
    ("Долгота", "longitude"),
    ("Кадастровый номер", "cadastral_number"),
    ("Административный район города", "administrative_district"),
    ("Ссылка на Яндекс", "link_yandex"),
    ("Ссылка на Отзывы Яндекс", "reviews_link_yandex"),
    ("Ссылка на 2ГИС", "link_2gis"),
    ("Ссылка на Отзывы 2ГИС", "reviews_link_2gis"),
    ("Ссылка на Госуслуги", "link_gosuslugi"),
    ("Ссылка на материально-техническое обеспечение (Госуслуги)", "mto_url"),
    ("Общая площадь, кв.м.", "area_sqm"),
    ("Год постройки", "year_built"),
    ("Год реконструкции", "reconstruction_year"),
    ("Количество надземных этажей", "floors"),
    ("Количество подземных этажей", "underground_floors"),
    ("Материал стен", "wall_material"),
    ("Вместимость, учеников", "capacity_students"),
    ("Источник данных о вместимости", "capacity_source"),
]

FLAG_KEYS = {
    "profile_phys_math",
    "profile_med_bio",
    "profile_soc_econ",
    "profile_humanitarian",
    "profile_religious",
    "fok",
    "pool",
    "stadium",
    "sports_ground",
}


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    m = re.search(r"([0-9]+(?:[.,][0-9]+)?)", text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def _rating_vuz_from_percent(raw: Any) -> float | None:
    """Рейтинг поступлений в ВУЗ (0-100) из приведённого процента."""
    val = _to_float(raw)
    if val is None:
        return None
    return round(max(0.0, min(100.0, val)), 1)


def _scale_100_to_10(value: Any) -> float | None:
    val = _to_float(value)
    if val is None:
        return None
    return round(val / 10.0, 1)


def _flag_value(value: Any) -> int | None:
    if value == 1:
        return 1
    return None


def _tags_text(value: Any) -> str | None:
    if not isinstance(value, list):
        return None
    tags = [str(x).strip() for x in value if str(x).strip()]
    if not tags:
        return None
    return "; ".join(tags)


def export_value(school: dict[str, Any], key: str) -> Any:
    if key == "rating_vuz":
        raw = school.get("rating_university_admission")
        if raw is not None:
            val = _to_float(raw)
        else:
            val = _rating_vuz_from_percent(school.get("university_admission_percent"))
        return round(val, 2) if val is not None else None
    if key in FLAG_KEYS:
        return _flag_value(school.get(key))
    if key == "top_tags":
        return _tags_text(school.get("top_tags"))
    if key in ("rating_2gis", "rating_yandex"):
        val = _to_float(school.get(key))
        return round(val, 1) if val is not None else None
    if key in ("rating_teachers", "rating_mto", "rating_psychological_climate"):
        val = _to_float(school.get(key))
        if val is None:
            return None
        return round(val * 100.0, 1)
    if key in (
        "rating_total",
        "rating_ege",
        "rating_olympiads",
        "ege_average_score",
    ):
        val = _to_float(school.get(key))
        return round(val, 2) if val is not None else None
    if key == "university_admission_percent":
        val = school.get(key)
        if val is None:
            return None
        if isinstance(val, str):
            inner = re.search(r"\((\d+(?:[.,]\d+)?)\)\s*$", val.strip())
            if inner:
                return float(inner.group(1).replace(",", "."))
            parsed = _to_float(val)
            return round(parsed, 1) if parsed is not None else val
        return round(float(val), 1)
    if key == "rating_sports_infrastructure":
        val = school.get(key)
        if val is None:
            return None
        try:
            return int(val)
        except (TypeError, ValueError):
            return None
    return school.get(key)


def write_workbook(path: Path, schools: list[dict[str, Any]]) -> None:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = SHEET_NAME

    headers = [h for h, _ in EXPORT_COLUMNS]
    for col, title in enumerate(headers, start=1):
        ws.cell(row=1, column=col, value=title)

    for row_idx, school in enumerate(schools, start=2):
        for col_idx, (_, key) in enumerate(EXPORT_COLUMNS, start=1):
            ws.cell(row=row_idx, column=col_idx, value=export_value(school, key))

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def main() -> None:
    if not INPUT_JSON.is_file():
        raise FileNotFoundError(f"Нет файла: {INPUT_JSON}")

    schools: list[dict[str, Any]] = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    schools.sort(key=lambda s: (s.get("id") is None, int(s.get("id") or 0)))

    write_workbook(OUTPUT_EXCEL, schools)
    print(f"OK: {len(schools)} schools -> {OUTPUT_EXCEL}")

    write_workbook(OUTPUT_TPP_EXCEL, schools)
    print(f"OK: {len(schools)} schools -> {OUTPUT_TPP_EXCEL}")


if __name__ == "__main__":
    main()
