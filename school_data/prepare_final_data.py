#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Преобразование sd_2_stage_gosuslugi_infrastucture_output_extract.json
в итоговый датасет final_school_data.json.

Запуск из корня репозитория:
  python school_data/prepare_final_data.py

Формула rating_total — см. .cursor/rules/rating-formula.mdc и RATING_TOTAL.md.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
INPUT_JSON = BASE_DIR / "sd_2_stage_gosuslugi_infrastucture_output_extract.json"
OUTPUT_JSON = BASE_DIR / "final_school_data.json"
RATING_MATRIX_CSV = BASE_DIR / "rating_matrix.csv"
CAPACITY_EXCEL = BASE_DIR / "sd_2_stage_gosuslugi" / "Здания школ2.xlsx"
ADMIN_DISTRICT_DOCS_DIR = BASE_DIR / "administrative_district_docs"
REVIEWS_ANALYZED_DIR = (
    REPO_ROOT / "review_data" / "rd_2_stage_analys" / "rd_separately_analyzed"
)
TOP_TAGS_LIMIT = 5
CAPACITY_AREA_PER_STUDENT = 19

# Дубликаты зданий: оставляем второй id из пары
SCHOOL_IDS_TO_DROP = frozenset({70, 23, 175, 159, 124, 115})
REVIEW_ALIAS_IDS: dict[int, list[int]] = {
    64: [70],
    167: [23],
    171: [175],
    33: [159],
    155: [124],
    80: [115],
}
OLYMPIAD_ALIAS_IDS: dict[int, list[int]] = {
    64: [70],
    167: [23],
    171: [175],
    33: [159],
    155: [124],
    80: [115],
}

# Отзывы — только карточка школы, в rating_total не входят
REVIEW_TOPIC_GROUPS: dict[str, tuple[str, ...]] = {
    "rating_teachers": ("учителя",),
    "rating_mto": ("ремонт", "инфраструктура", "уборка"),
    "rating_access_convenience": ("инфраструктура", "охрана"),
    "rating_psychological_climate": ("буллинг", "администрация"),
}

# Спорт в рейтинге: только эти три (+1 каждый)
SPORT_RATING_KEYS: tuple[str, ...] = ("pool", "fok", "sports_ground")

DISTRICT_KEYWORDS: dict[str, str] = {
    "волжск": "Волжский",
    "гагарин": "Гагаринский",
    "заводск": "Заводской",
    "кировск": "Кировский",
    "ленинск": "Ленинский",
    "октябр": "Октябрьский",
    "фрунз": "Фрунзенский",
}

SCHOOL_NAME_HINTS = (
    "школ",
    "сош",
    "оош",
    "лицей",
    "гимназ",
    "моу",
    "маоу",
    "гаоу",
    "соши",
)

MATERIAL_MAP = {
    "кирп": "Кирпич",
    "кирпич": "Кирпич",
    "панель": "Панель",
    "пан": "Панель",
    "смеш": "Смешанные",
    "смешан": "Смешанные",
    "смешанные": "Смешанные",
}


def round_or_none(value: Any, digits: int) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def rating_stars_1_to_5(value: Any) -> float | None:
    """Рейтинг 2ГИС/Яндекс как на площадке: 1..5."""
    base = round_or_none(value, 1)
    if base is None:
        return None
    return round(max(1.0, min(5.0, base)), 1)


def _to_float_or_none(value: Any) -> float | None:
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


def normalize_wall_material(raw: Any) -> str:
    if raw is None or str(raw).strip() == "":
        return "Неизвестно"
    key = str(raw).strip().lower()
    for prefix, label in MATERIAL_MAP.items():
        if key.startswith(prefix):
            return label
    return "Неизвестно"


def _collect_profile_texts(school: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    for key in ("specialization", "specialization_extract", "name_2gis", "short_name"):
        val = school.get(key)
        if isinstance(val, list):
            parts.extend(str(x).lower() for x in val)
        elif val is not None:
            parts.append(str(val).lower())
    return parts


def _has_profile_keyword(texts: list[str], *keywords: str) -> bool:
    blob = " ".join(texts)
    return any(kw in blob for kw in keywords)


def derive_profiles(school: dict[str, Any]) -> dict[str, int | None]:
    """
    Четыре кластера профилей для рейтинга:
    физ-мат, соц-эконом, хим-био, физический (спортивные школы).
    """
    texts = _collect_profile_texts(school)
    extract = {str(x).lower() for x in (school.get("specialization_extract") or [])}

    phys_math = False
    chem_bio = False
    soc_econ = False
    physical = False

    if "без специализации" in extract and len(extract) == 1:
        # Физический кластер может быть по названию даже без академических профилей
        if _has_profile_keyword(
            texts,
            "спортивн",
            "олимпийск",
            "школа олимпийского",
            "физическ",
        ):
            return {
                "profile_phys_math": None,
                "profile_chem_bio": None,
                "profile_soc_econ": None,
                "profile_physical": 1,
            }
        return {
            "profile_phys_math": None,
            "profile_chem_bio": None,
            "profile_soc_econ": None,
            "profile_physical": None,
        }

    if "физ-мат" in extract:
        phys_math = True
    if "хим-био" in extract:
        chem_bio = True
    if "технологическая" in extract:
        phys_math = True
    if "соц-эконом" in extract:
        soc_econ = True

    subject_phys = (
        "физика",
        "математика",
        "математический профиль",
        "информатика",
        "информатика и икт",
    )
    subject_chem = ("химия", "биология", "медицинский класс")
    subject_soc = ("обществознание", "право", "эконом")

    for tag in extract:
        if tag in subject_phys:
            phys_math = True
        if tag in subject_chem:
            chem_bio = True
        if any(s in tag for s in subject_soc):
            soc_econ = True

    if _has_profile_keyword(texts, "физико-математ", "физ-мат", "физмат"):
        phys_math = True
    if _has_profile_keyword(
        texts,
        "хим-био",
        "химбио",
        "медико-биолог",
        "естественно-науч",
        "биолог",
        "хими",
    ):
        chem_bio = True
    if _has_profile_keyword(texts, "технолог", "инженер"):
        phys_math = True
    if _has_profile_keyword(texts, "социально-эконом", "соц-эконом", "соцэкон"):
        soc_econ = True
    if _has_profile_keyword(
        texts,
        "спортивн",
        "олимпийск",
        "школа олимпийского",
        "физическ",
    ):
        physical = True

    def as_flag(flag: bool) -> int | None:
        return 1 if flag else None

    return {
        "profile_phys_math": as_flag(phys_math),
        "profile_chem_bio": as_flag(chem_bio),
        "profile_soc_econ": as_flag(soc_econ),
        "profile_physical": as_flag(physical),
    }


def count_profile_clusters(profiles: dict[str, int | None]) -> int:
    keys = (
        "profile_phys_math",
        "profile_chem_bio",
        "profile_soc_econ",
        "profile_physical",
    )
    return sum(1 for k in keys if profiles.get(k) == 1)


def _infra_texts(school: dict[str, Any]) -> list[str]:
    raw = school.get("infrastucture") or school.get("infrastructure_list")
    if not isinstance(raw, list):
        return []
    return [str(x).lower() for x in raw]


def _sport_flag(school: dict[str, Any], field: str, infra_matchers: tuple[str, ...]) -> int | None:
    if school.get(field) == 1:
        return 1
    for text in _infra_texts(school):
        if any(m in text for m in infra_matchers):
            return 1
    return None


def derive_sports(school: dict[str, Any]) -> dict[str, int | None]:
    return {
        "fok": _sport_flag(
            school,
            "has_sports_complex",
            ("фок", "спортивно-оздоровительн", "спортивный комплекс"),
        ),
        "pool": _sport_flag(school, "has_pool", ("бассейн",)),
        "stadium": _sport_flag(school, "has_stadium", ("стадион",)),
        "sports_ground": _sport_flag(
            school,
            "has_sports_ground",
            ("площадк", "коробка-трансформер"),
        ),
    }


def sports_rating_points(sports: dict[str, int | None]) -> int | None:
    """+1 за бассейн, ФОК, спортплощадку. Стадион в рейтинг не входит."""
    flags = [sports.get(k) for k in SPORT_RATING_KEYS]
    if not any(v is not None for v in flags):
        return None
    return sum(1 for v in flags if v == 1)


def coords_from_school(school: dict[str, Any]) -> tuple[float | None, float | None]:
    lat = school.get("latitude")
    lon = school.get("longitude")
    if lat is not None and lon is not None:
        return round_or_none(lat, 6), round_or_none(lon, 6)
    loc = school.get("location")
    if isinstance(loc, dict):
        coords = loc.get("coordinates")
        if isinstance(coords, list) and len(coords) >= 2:
            return round_or_none(coords[1], 6), round_or_none(coords[0], 6)
    return None, None


def _school_id_from_excel_cell(raw_id: Any) -> int | None:
    if raw_id is None or (isinstance(raw_id, float) and pd.isna(raw_id)):
        return None
    id_parts = re.findall(r"\d+", str(raw_id).strip())
    if not id_parts:
        return None
    return int(id_parts[-1])


def _parse_percent_number(raw: str) -> float | None:
    cleaned = raw.replace(" ", "").replace(",", ".")
    while ".." in cleaned:
        cleaned = cleaned.replace("..", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_vuz_cell(raw: Any) -> tuple[float | None, int | None]:
    """Парсит ячейку «ВУЗы» → (исходный %, год)."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None, None

    text = str(raw).strip()
    if not text or text.lower() in {"нету", "нет", "none", "null"}:
        return None, None

    percent_match = re.search(
        r"(\d+(?:[.,\s]\d+)*)\s*%",
        text,
        flags=re.IGNORECASE,
    )
    if not percent_match:
        percent_match = re.search(r"^(\d+(?:[.,]\d+)?)\s*-", text)
    if not percent_match:
        return None, None

    original_percent = _parse_percent_number(percent_match.group(1))
    if original_percent is None:
        return None, None

    range_match = re.search(r"(20\d{2})\s*-\s*(20\d{2})", text)
    if range_match:
        data_year = int(range_match.group(2))
    else:
        years = re.findall(r"(20\d{2})", text)
        if years:
            data_year = int(years[-1])
        else:
            span_match = re.search(r"за\s+(\d+)\s+год", text, flags=re.IGNORECASE)
            if span_match:
                data_year = 2025 - int(span_match.group(1))
            else:
                data_year = 2025

    if abs(original_percent - round(original_percent)) < 0.05:
        return float(int(round(original_percent))), data_year
    return round(original_percent, 1), data_year


def _parse_ege_raw_score_and_year(raw: Any) -> tuple[float, int] | tuple[None, None]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None, None

    text = str(raw).strip()
    if not text or text.lower() in {"нету", "нет", "none", "null"}:
        return None, None

    score_match = re.search(r"(\d+(?:[.,]\d+)?)\s*-", text)
    if not score_match:
        return None, None
    score = float(score_match.group(1).replace(",", "."))

    years = [int(y) for y in re.findall(r"(20\d{2})", text)]
    if not years:
        return None, None
    return round(score, 2), max(years)


def _find_ege_column(df: pd.DataFrame) -> str | None:
    pattern = re.compile(r"(\d+(?:[.,]\d+)?)\s*-.*?(20\d{2})", flags=re.IGNORECASE)
    best_col = None
    best_cnt = 0
    for col in df.columns:
        try:
            s = df[col].dropna().astype(str)
        except Exception:
            continue
        cnt = sum(1 for x in s.head(80).tolist() if pattern.search(x))
        if cnt > best_cnt:
            best_cnt = cnt
            best_col = col
    return best_col if best_cnt > 0 else None


def load_ege_map() -> dict[int, tuple[float, int]]:
    if not CAPACITY_EXCEL.is_file():
        return {}
    df = pd.read_excel(CAPACITY_EXCEL, sheet_name=0)
    ege_col = _find_ege_column(df)
    if ege_col is None:
        return {}
    result: dict[int, tuple[float, int]] = {}
    for _, row in df.iterrows():
        school_id = _school_id_from_excel_cell(row.iloc[0])
        if school_id is None:
            continue
        score, year = _parse_ege_raw_score_and_year(row.get(ege_col))
        if score is None or year is None:
            continue
        result[school_id] = (score, year)
    return result


def load_capacity_map() -> dict[int, tuple[int, str]]:
    if not CAPACITY_EXCEL.is_file():
        return {}
    df = pd.read_excel(CAPACITY_EXCEL, sheet_name=0)
    result: dict[int, tuple[int, str]] = {}
    for _, row in df.iterrows():
        school_id = _school_id_from_excel_cell(row.iloc[0])
        if school_id is None:
            continue
        capacity_raw = row.iloc[2]
        if capacity_raw is None or (isinstance(capacity_raw, float) and pd.isna(capacity_raw)):
            continue
        capacity = int(round(float(capacity_raw)))
        source_raw = row.iloc[1]
        source_text = (
            str(source_raw).strip().lower()
            if source_raw is not None and not (isinstance(source_raw, float) and pd.isna(source_raw))
            else ""
        )
        if (
            "вычисл" in source_text
            or source_text.startswith("=")
            or "не могу" in source_text
            or "описи" in source_text
        ):
            source_kind = "Расчетный"
        else:
            source_kind = str(source_raw).strip() or "Проектный"
        result[school_id] = (capacity, source_kind)
    return result


def load_vuz_map() -> dict[int, tuple[float | None, int | None]]:
    if not CAPACITY_EXCEL.is_file():
        return {}
    df = pd.read_excel(CAPACITY_EXCEL, sheet_name=0)
    if "ВУЗы" not in df.columns:
        return {}
    result: dict[int, tuple[float | None, int | None]] = {}
    for _, row in df.iterrows():
        school_id = _school_id_from_excel_cell(row.iloc[0])
        if school_id is None:
            continue
        parsed = parse_vuz_cell(row["ВУЗы"])
        if parsed != (None, None):
            result[school_id] = parsed
    return result


def vuz_for_school(
    school: dict[str, Any],
    vuz_map: dict[int, tuple[float | None, int | None]],
) -> tuple[float | None, int | None]:
    school_id = school.get("id")
    if school_id is not None:
        try:
            mapped = vuz_map.get(int(school_id))
            if mapped is not None:
                return mapped
        except (TypeError, ValueError):
            pass
    return parse_vuz_cell(school.get("VUZ"))


def ege_for_school(
    school: dict[str, Any],
    ege_map: dict[int, tuple[float, int]],
) -> tuple[float | None, int | None]:
    school_id = school.get("id")
    if school_id is not None:
        try:
            mapped = ege_map.get(int(school_id))
            if mapped is not None:
                return mapped
        except (TypeError, ValueError):
            pass
    return _parse_ege_raw_score_and_year(school.get("EGE"))


def _extract_olympiad_entries(school: dict[str, Any]) -> list[str]:
    raw = school.get("Olympiads")
    entries: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            text = str(item).strip()
            if text and text.lower() not in {"нету", "нет", "none", "null"}:
                entries.append(text)
    elif raw is not None:
        text = str(raw).strip()
        if text and text.lower() not in {"нету", "нет", "none", "null"}:
            entries.append(text)
    return entries


def _extract_count_from_olympiad_text(text: str) -> float:
    """
    Число олимпиадников из строки.
    «242 - … за 2022/2023» → 242 (годы через / не считаем).
    «10/5 победителей/призёров» → 15.
    """
    cleaned = text.strip()
    lead = re.search(r"^(\d+(?:[.,]\d+)?)\s*[-–—]", cleaned)
    if lead:
        return float(lead.group(1).replace(",", "."))

    slash_match = re.search(r"(\d+)\s*/\s*(\d+)", cleaned)
    if slash_match:
        left = int(slash_match.group(1))
        right = int(slash_match.group(2))
        # Диапазон учебных лет (2022/2023) — не количество
        if left < 1900 and right < 1900:
            return float(left + right)

    first_num = re.search(r"(\d+(?:[.,]\d+)?)", cleaned)
    if not first_num:
        return 0.0
    return float(first_num.group(1).replace(",", "."))


def _normalize_name_for_group(name: Any) -> str:
    if name is None:
        return ""
    return re.sub(r"\s+", " ", str(name).strip().lower())


def _district_from_filename(name: str) -> str | None:
    lowered = name.lower()
    for key, district in DISTRICT_KEYWORDS.items():
        if key in lowered:
            return district
    return None


def _extract_school_num_from_text(text: str) -> list[int]:
    nums = []
    for match in re.finditer(r"№\s*(\d+)", text):
        try:
            nums.append(int(match.group(1)))
        except ValueError:
            continue
    return nums


def _is_school_name_cell(text: str) -> bool:
    lowered = text.lower()
    if "№" not in text:
        return False
    if "приложени" in lowered or "постановлен" in lowered:
        return False
    return any(hint in lowered for hint in SCHOOL_NAME_HINTS)


def _school_kind(text: str) -> str:
    lowered = text.lower()
    if "лицей" in lowered:
        return "lyceum"
    if "гимназ" in lowered:
        return "gymnasium"
    if "оош" in lowered:
        return "oosh"
    if "сош" in lowered or "школ" in lowered:
        return "school"
    return "unknown"


def _extract_class_range_for_school(text: str, school_num: int) -> str | None:
    pattern = re.compile(
        rf"№\s*{school_num}\b[^()]*\(([^)]*класс[^)]*)\)",
        flags=re.IGNORECASE,
    )
    m = pattern.search(text)
    if not m:
        return None
    value = re.sub(r"\s+", " ", m.group(1)).strip()
    value = value.replace("классы", "").replace("класс", "").strip(" -")
    return value or None


def load_admin_district_map() -> dict[int, str]:
    result_by_num: dict[int, set[str]] = {}
    result_by_num_kind: dict[tuple[int, str], set[str]] = {}
    if not ADMIN_DISTRICT_DOCS_DIR.is_dir():
        return {}

    for path in ADMIN_DISTRICT_DOCS_DIR.glob("*.xlsx"):
        if path.name.startswith("~$"):
            continue
        district = _district_from_filename(path.name)
        if district is None:
            continue
        try:
            sheets = pd.read_excel(path, sheet_name=None, header=None)
        except Exception:
            continue
        for _sheet_name, df in sheets.items():
            for _idx, row in df.iterrows():
                for value in row.tolist():
                    if value is None or (isinstance(value, float) and pd.isna(value)):
                        continue
                    text = str(value).strip()
                    if not _is_school_name_cell(text):
                        continue
                    nums = _extract_school_num_from_text(text)
                    if not nums:
                        continue
                    for num in nums:
                        kind = _school_kind(text)
                        cls = _extract_class_range_for_school(text, num)
                        entry = f"{district} ({cls})" if cls else district
                        result_by_num.setdefault(num, set()).add(entry)
                        result_by_num_kind.setdefault((num, kind), set()).add(entry)

    normalized: dict[int, str] = {}
    for num, entries in result_by_num.items():
        sorted_entries = sorted(entries, key=lambda x: (x.count("("), x))
        normalized[num] = "; ".join(sorted_entries)
    kind_code = {"lyceum": 1, "gymnasium": 2, "oosh": 3, "school": 4, "unknown": 9}
    for (num, kind), entries in result_by_num_kind.items():
        sorted_entries = sorted(entries, key=lambda x: (x.count("("), x))
        normalized[-(num * 10 + kind_code.get(kind, 9))] = "; ".join(sorted_entries)
    return normalized


def administrative_district_for_school(
    school: dict[str, Any],
    district_map: dict[int, str],
) -> str | None:
    kind_code = {"lyceum": 1, "gymnasium": 2, "oosh": 3, "school": 4, "unknown": 9}
    kind = _school_kind(
        str(school.get("name_2gis") or "") + " " + str(school.get("short_name") or "")
    )
    for key in ("name_2gis", "short_name"):
        value = school.get(key)
        if not value:
            continue
        nums = _extract_school_num_from_text(str(value))
        for num in nums:
            typed = district_map.get(-(num * 10 + kind_code.get(kind, 9)))
            if typed:
                return typed
            district = district_map.get(num)
            if district:
                return district
    return None


def capacity_for_school(
    school: dict[str, Any],
    capacity_map: dict[int, tuple[int, str]],
) -> tuple[int | None, str | None]:
    school_id = school.get("id")
    if school_id is not None:
        try:
            mapped = capacity_map.get(int(school_id))
            if mapped is not None:
                return mapped
        except (TypeError, ValueError):
            pass

    raw_capacity = school.get("capacity")
    if raw_capacity is not None:
        try:
            return int(round(float(raw_capacity))), "Проектный"
        except (TypeError, ValueError):
            pass

    area = school.get("area_sqm")
    if area is not None:
        try:
            return int(round(float(area) / CAPACITY_AREA_PER_STUDENT)), "Расчетный"
        except (TypeError, ValueError):
            pass
    return None, None


def build_olympiad_metrics_map(
    source_schools: list[dict[str, Any]],
    kept_schools: list[dict[str, Any]],
    capacity_map: dict[int, tuple[int, str]],
) -> dict[int, dict[str, Any]]:
    """
    olympiad_winners_count — сумма чисел из строк Olympiads.
    rating_olympiads = winners / capacity * 10.
    Корпуса с одним name_2gis делят общий пул пропорционально площади.
    """
    source_by_id: dict[int, dict[str, Any]] = {}
    for school in source_schools:
        try:
            sid = int(school.get("id"))
        except (TypeError, ValueError):
            continue
        source_by_id[sid] = school

    metrics: dict[int, dict[str, Any]] = {}
    for school in kept_schools:
        try:
            sid = int(school.get("id"))
        except (TypeError, ValueError):
            continue

        ids = [sid] + OLYMPIAD_ALIAS_IDS.get(sid, [])
        total_raw = 0.0
        has_any = False
        for current_id in ids:
            current = source_by_id.get(current_id)
            if not current:
                continue
            for entry in _extract_olympiad_entries(current):
                count = _extract_count_from_olympiad_text(entry)
                if count <= 0:
                    continue
                total_raw += count
                has_any = True

        metrics[sid] = {
            "raw_total": total_raw,
            "has_data": has_any,
            "area_sqm": float(school.get("area_sqm") or 0.0),
            "name_key": _normalize_name_for_group(school.get("name_2gis")),
        }

    # Один name_2gis → общий пул олимпиадников, деление по площади корпусов
    grouped: dict[str, list[int]] = {}
    for sid, info in metrics.items():
        key = info["name_key"]
        if not key:
            continue
        grouped.setdefault(key, []).append(sid)

    for _name_key, ids in grouped.items():
        if len(ids) < 2:
            continue
        with_data = [sid for sid in ids if metrics[sid]["has_data"]]
        if not with_data:
            continue
        total_raw = sum(metrics[sid]["raw_total"] for sid in with_data)
        if total_raw <= 0:
            continue
        area_sum = sum(
            (metrics[sid]["area_sqm"] if metrics[sid]["area_sqm"] > 0 else 1.0) for sid in ids
        )
        for sid in ids:
            area = metrics[sid]["area_sqm"]
            weight = (area if area > 0 else 1.0) / area_sum
            metrics[sid]["raw_total"] = total_raw * weight
            metrics[sid]["has_data"] = True

    final_map: dict[int, dict[str, Any]] = {}
    for sid, info in metrics.items():
        if not info.get("has_data"):
            final_map[sid] = {
                "olympiad_winners_count": None,
                "rating_olympiads": None,
            }
            continue
        winners = int(round(float(info["raw_total"])))
        capacity, _ = capacity_for_school({"id": sid}, capacity_map)
        rating = None
        if capacity and capacity > 0 and winners >= 0:
            rating = round(winners / capacity * 10.0, 2)
        final_map[sid] = {
            "olympiad_winners_count": winners,
            "rating_olympiads": rating,
        }
    return final_map


def share_academic_across_buildings(
    records: list[dict[str, Any]],
) -> None:
    """ЕГЭ/ВУЗ — показатели школы, не корпуса: копируем на все здания с одним name_2gis."""
    by_name: dict[str, list[dict[str, Any]]] = {}
    for rec in records:
        key = _normalize_name_for_group(rec.get("name_2gis"))
        if key:
            by_name.setdefault(key, []).append(rec)

    for group in by_name.values():
        if len(group) < 2:
            continue
        ege_score = next((r["ege_average_score"] for r in group if r.get("ege_year") is not None), None)
        ege_year = next((r["ege_year"] for r in group if r.get("ege_year") is not None), None)
        ege_rating = next((r["rating_ege"] for r in group if r.get("rating_ege") is not None), None)
        vuz_pct = next(
            (r["university_admission_percent"] for r in group if r.get("university_admission_percent") is not None),
            None,
        )
        vuz_year = next(
            (r["university_admission_year"] for r in group if r.get("university_admission_year") is not None),
            None,
        )
        vuz_rating = next(
            (r["rating_university_admission"] for r in group if r.get("rating_university_admission") is not None),
            None,
        )
        for r in group:
            if r.get("ege_year") is None and ege_year is not None:
                r["ege_average_score"] = ege_score
                r["ege_year"] = ege_year
                r["rating_ege"] = ege_rating
            if r.get("university_admission_percent") is None and vuz_pct is not None:
                r["university_admission_percent"] = vuz_pct
                r["university_admission_year"] = vuz_year
                r["rating_university_admission"] = vuz_rating


def _school_ids_for_reviews(school_id: Any) -> list[int]:
    try:
        primary = int(school_id)
    except (TypeError, ValueError):
        return []
    return [primary] + REVIEW_ALIAS_IDS.get(primary, [])


def review_analysis_path(school_id: Any) -> Path | None:
    if school_id is None:
        return None
    try:
        num = int(school_id)
    except (TypeError, ValueError):
        return None
    return REVIEWS_ANALYZED_DIR / f"school_reviews_separately_{num}_analyz.json"


def _normalize_review_items(data: Any) -> list[dict[str, Any]] | None:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        reviews = data.get("reviews")
        if isinstance(reviews, list):
            return [item for item in reviews if isinstance(item, dict)]
    return None


def _extract_topic_sentiments(review: dict[str, Any]) -> list[tuple[str, str]]:
    topics = review.get("topics")
    result: list[tuple[str, str]] = []
    if isinstance(topics, dict):
        for topic, sentiment in topics.items():
            if isinstance(topic, str) and topic.strip() and isinstance(sentiment, str):
                result.append((topic.strip(), sentiment.strip().lower()))
        return result
    if isinstance(topics, list):
        for item in topics:
            if not isinstance(item, dict):
                continue
            topic = item.get("topic")
            sentiment = item.get("sentiment")
            if isinstance(topic, str) and topic.strip() and isinstance(sentiment, str):
                result.append((topic.strip(), sentiment.strip().lower()))
    return result


def _extract_topics(review: dict[str, Any]) -> list[str]:
    return [topic for topic, _sentiment in _extract_topic_sentiments(review)]


def _sentiment_to_score(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    key = value.strip().lower()
    if key in {"pos", "positive"}:
        return 1
    if key in {"neg", "negative"}:
        return -1
    if key in {"neutral", "neu"}:
        return 0
    return None


def load_reviews_for_school(school_id: Any) -> list[dict[str, Any]]:
    reviews: list[dict[str, Any]] = []
    for sid in _school_ids_for_reviews(school_id):
        path = review_analysis_path(sid)
        if path is None or not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, OSError):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
        items = _normalize_review_items(data)
        if items:
            reviews.extend(items)
    return reviews


def _rating_from_topic_scores(scores: list[int]) -> float | None:
    if not scores:
        return None
    mean = sum(scores) / len(scores)
    return round((mean + 1) / 2, 3)


def review_ratings_from_analysis(school_id: Any) -> dict[str, float | None]:
    reviews = load_reviews_for_school(school_id)
    result: dict[str, float | None] = {field: None for field in REVIEW_TOPIC_GROUPS}
    if not reviews:
        return result
    for field, topic_names in REVIEW_TOPIC_GROUPS.items():
        scores: list[int] = []
        for review in reviews:
            pairs = _extract_topic_sentiments(review)
            if not pairs:
                continue
            normalized = {topic: sentiment for topic, sentiment in pairs}
            for topic_name in topic_names:
                if topic_name not in normalized:
                    continue
                score = _sentiment_to_score(normalized[topic_name])
                if score is not None:
                    scores.append(score)
        result[field] = _rating_from_topic_scores(scores)
    return result


def top_tags_from_analysis(school_id: Any) -> list[str]:
    reviews = load_reviews_for_school(school_id)
    if not reviews:
        return []
    counter: Counter[str] = Counter()
    for review in reviews:
        counter.update(_extract_topics(review))
    if not counter:
        return []
    ranked = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return [topic for topic, _count in ranked[:TOP_TAGS_LIMIT]]


def average_maps_rating(rating_2gis: Any, rating_yandex: Any) -> float | None:
    vals = [v for v in (rating_2gis, rating_yandex) if v is not None]
    if not vals:
        return None
    return round(sum(float(v) for v in vals) / len(vals), 2)


def university_admission_rating(percent: Any) -> float | None:
    """% / 10 → вклад в сумму (100% → 10)."""
    val = _to_float_or_none(percent)
    if val is None:
        return None
    return round(val / 10.0, 2)


def compute_rating_total(record: dict[str, Any]) -> float | None:
    """
    rating_ege
    + rating_university_admission
    + rating_maps
    + rating_profiles
    + rating_olympiads
    + rating_sports_infrastructure
    − 10 если has_second_shift
    """
    parts = [
        record.get("rating_ege"),
        record.get("rating_university_admission"),
        record.get("rating_maps"),
        record.get("rating_profiles"),
        record.get("rating_olympiads"),
        record.get("rating_sports_infrastructure"),
    ]
    total = 0.0
    found = False
    for value in parts:
        num = _to_float_or_none(value)
        if num is None:
            continue
        total += num
        found = True

    if record.get("has_second_shift") is True:
        total -= 10.0
        found = True

    if not found:
        return None
    return round(total, 2)


def transform_school(
    school: dict[str, Any],
    capacity_map: dict[int, tuple[int, str]],
    vuz_map: dict[int, tuple[float | None, int | None]],
    ege_map: dict[int, tuple[float, int]],
    olympiad_map: dict[int, dict[str, Any]],
    district_map: dict[int, str],
) -> dict[str, Any]:
    lat, lon = coords_from_school(school)
    profiles = derive_profiles(school)
    sports = derive_sports(school)
    school_id = school.get("id")

    rating_2gis = rating_stars_1_to_5(school.get("rating_2gis"))
    rating_yandex = rating_stars_1_to_5(school.get("rating_yandex"))

    review = review_ratings_from_analysis(school_id)
    mto = review.pop("rating_mto", None)
    access = review.pop("rating_access_convenience", None)
    if mto is not None and access is not None:
        rating_mto = round((float(mto) + float(access)) / 2.0, 3)
    elif mto is not None or access is not None:
        rating_mto = mto if mto is not None else access
    else:
        rating_mto = None

    capacity, capacity_source = capacity_for_school(school, capacity_map)
    vuz_percent, vuz_year = vuz_for_school(school, vuz_map)
    ege_score, ege_year = ege_for_school(school, ege_map)

    olympiad: dict[str, Any] = {}
    if school_id is not None:
        try:
            olympiad = olympiad_map.get(int(school_id)) or {}
        except (TypeError, ValueError):
            olympiad = {}

    rating_ege = round(float(ege_score), 2) if ege_score is not None else None
    rating_profiles_value = count_profile_clusters(profiles)

    record: dict[str, Any] = {
        "id": school.get("id"),
        "name_2gis": school.get("name_2gis"),
        "short_name": school.get("short_name"),
        "address": school.get("address"),
        "building_type": school.get("building_type"),
        "rating_2gis": rating_2gis,
        "rating_yandex": rating_yandex,
        "rating_maps": average_maps_rating(rating_2gis, rating_yandex),
        "rating_total": None,
        "top_tags": top_tags_from_analysis(school_id),
        "rating_ege": rating_ege,
        "rating_olympiads": olympiad.get("rating_olympiads"),
        "rating_teachers": review.get("rating_teachers"),
        "rating_mto": rating_mto,
        "rating_sports_infrastructure": sports_rating_points(sports),
        "rating_psychological_climate": review.get("rating_psychological_climate"),
        "rating_profiles": rating_profiles_value,
        "ege_average_score": float(ege_score) if ege_score is not None else 0.0,
        "ege_year": ege_year,
        "rating_university_admission": university_admission_rating(vuz_percent),
        "university_admission_percent": vuz_percent,
        "university_admission_year": vuz_year,
        "olympiad_winners_count": olympiad.get("olympiad_winners_count"),
        "capacity_students": capacity,
        "capacity_source": capacity_source,
        "mto_url": school.get("infrastructure"),
        "administrative_district": administrative_district_for_school(school, district_map),
        "has_second_shift": None,
        **profiles,
        **sports,
        "latitude": lat,
        "longitude": lon,
        "cadastral_number": school.get("cadastral_number"),
        "link_yandex": school.get("link_yandex"),
        "reviews_link_yandex": school.get("reviews_link_yandex"),
        "link_2gis": school.get("link_2gis"),
        "reviews_link_2gis": school.get("reviews_link_2gis"),
        "link_gosuslugi": school.get("link_gosuslugi"),
        "area_sqm": round_or_none(school.get("area_sqm"), 1),
        "year_built": school.get("year_built"),
        "reconstruction_year": school.get("reconstruction_year"),
        "floors": school.get("floors"),
        "underground_floors": school.get("underground_floors"),
        "wall_material": normalize_wall_material(school.get("material")),
        # Форма собственности: частные (ЧОУ/АНО/религиозные) vs общие (муниципальные/государственные).
        # В rating_total не входит — только для фильтра «Общие/Частные» на сайте.
        "ownership": (
            "private"
            if re.search(
                r"\bчоу\b|\bаноо\b|\bано\b|\bноу\b|частн|православн|иудейск|еврейск|приходск",
                f"{school.get('name_2gis') or ''} {school.get('short_name') or ''}",
                re.IGNORECASE,
            )
            else "public"
        ),
    }
    return record


def load_schools(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Ожидался JSON-массив школ: {path}")
    return data


def save_schools(path: Path, schools: list[dict[str, Any]]) -> None:
    path.write_text(
        json.dumps(schools, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def apply_rating_totals(schools: list[dict[str, Any]]) -> None:
    for school in schools:
        school["rating_total"] = compute_rating_total(school)


def write_rating_matrix(path: Path, schools: list[dict[str, Any]]) -> None:
    """Матрица школа × составляющие рейтинга + итог."""
    headers = [
        "id",
        "short_name",
        "name_2gis",
        "address",
        "rating_ege",
        "rating_university_admission",
        "rating_maps",
        "rating_profiles",
        "rating_olympiads",
        "rating_sports_infrastructure",
        "has_second_shift",
        "rating_total",
        "ege_average_score",
        "university_admission_percent",
        "rating_2gis",
        "rating_yandex",
        "olympiad_winners_count",
        "capacity_students",
        "profile_phys_math",
        "profile_chem_bio",
        "profile_soc_econ",
        "profile_physical",
        "pool",
        "fok",
        "sports_ground",
    ]
    lines = [";".join(headers)]
    ordered = sorted(schools, key=lambda s: (-(s.get("rating_total") or 0), s.get("id") or 0))
    for s in ordered:
        row = []
        for h in headers:
            val = s.get(h)
            if val is None:
                row.append("")
            else:
                text = str(val).replace(";", ",")
                row.append(text)
        lines.append(";".join(row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def main() -> None:
    if not INPUT_JSON.is_file():
        raise FileNotFoundError(f"Нет входного файла: {INPUT_JSON}")

    capacity_map = load_capacity_map()
    vuz_map = load_vuz_map()
    ege_map = load_ege_map()
    district_map = load_admin_district_map()
    source = load_schools(INPUT_JSON)
    kept_schools: list[dict[str, Any]] = []
    for school in source:
        try:
            sid = int(school.get("id"))
        except (TypeError, ValueError):
            sid = None
        if sid in SCHOOL_IDS_TO_DROP:
            continue
        kept_schools.append(school)

    olympiad_map = build_olympiad_metrics_map(source, kept_schools, capacity_map)
    result = [
        transform_school(s, capacity_map, vuz_map, ege_map, olympiad_map, district_map)
        for s in kept_schools
    ]
    share_academic_across_buildings(result)
    apply_rating_totals(result)

    save_schools(OUTPUT_JSON, result)
    write_rating_matrix(RATING_MATRIX_CSV, result)
    print(f"OK: {len(result)} schools -> {OUTPUT_JSON}")
    print(f"OK: rating matrix -> {RATING_MATRIX_CSV}")


if __name__ == "__main__":
    main()
