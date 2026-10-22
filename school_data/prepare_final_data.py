#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Преобразование sd_2_stage_gosuslugi_infrastucture_output_extract.json
в итоговый датасет final_school_data.json (схема для аналитики / Excel).

Запуск из корня репозитория:
  python school_data/prepare_final_data.py

По мере появления расчётов рейтингов и прочих полей — дополняйте функции
в секции «Расчёты (пока пусто)».
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
CAPACITY_EXCEL = BASE_DIR / "sd_2_stage_gosuslugi" / "Здания школ2.xlsx"
ADMIN_DISTRICT_DOCS_DIR = BASE_DIR / "administrative_district_docs"
REVIEWS_ANALYZED_DIR = (
    REPO_ROOT
    / "review_data"
    / "rd_2_stage_analys"
    / "rd_separately_analyzed"
)
REVIEWS_ANALYZED_PATTERN = re.compile(
    r"school_reviews_separately_(\d+)_analyz\.json$"
)
TOP_TAGS_LIMIT = 5
CAPACITY_AREA_PER_STUDENT = 19
VUZ_REFERENCE_YEAR = 2025
VUZ_DECAY_PER_YEAR = 0.9
EGE_REFERENCE_YEAR = 2025
EGE_DECAY_PER_YEAR = 0.9
MAX_DATA_AGE_YEARS = 10  # старше → рейтинг ЕГЭ/ВУЗ обнуляется

# Дубликаты зданий: оставляем второй id из пары (меньший в записи «70 + 64» → 64)
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

# Префикс ID объекта по спецификации (6448 + 4 цифры порядкового номера)
OBJECT_ID_PREFIX = 64480000

# Топики распознавания отзывов → поля рейтинга
REVIEW_TOPIC_GROUPS: dict[str, tuple[str, ...]] = {
    "rating_teachers": ("учителя",),
    "rating_mto": ("ремонт", "инфраструктура", "уборка"),
    "rating_access_convenience": ("инфраструктура", "охрана"),
    "rating_psychological_climate": ("буллинг", "администрация"),
}

# Этапы ВсОШ по возрастанию сложности:
# муниципальный < региональный < заключительный.
OLYMPIAD_STAGE_WEIGHTS: dict[str, float] = {
    "municipal": 1.0,
    "regional": 1.35,
    "final": 1.8,
    "unknown": 1.0,
}

# Вес статуса в олимпиадах: победитель > призер.
OLYMPIAD_AWARD_WEIGHTS: dict[str, float] = {
    "winner": 1.0,
    "prizer": 0.65,
    "mixed": 0.8,
    "unknown": 0.75,
}

# Поля, которые складываются в rating_total (простая сумма, без весов).
RATING_TOTAL_SUM_KEYS: tuple[str, ...] = (
    "rating_2gis",
    "rating_yandex",
    "rating_ege",
    "rating_olympiads",
    "rating_university_admission",
    "rating_teachers",
    "rating_mto",
    "rating_psychological_climate",
    "rating_sports_infrastructure",
)

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


def scale_10_to_100(value: Any) -> float | None:
    base = round_or_none(value, 3)
    if base is None:
        return None
    return round(base * 10.0, 1)


def _to_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    # Для формата типа "49.6(68)" берём приведённое значение до скобки.
    m = re.search(r"([0-9]+(?:[.,][0-9]+)?)", text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def object_id_from_school_id(school_id: Any) -> int | None:
    if school_id is None:
        return None
    try:
        return OBJECT_ID_PREFIX + int(school_id)
    except (TypeError, ValueError):
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
    for key in ("specialization", "specialization_extract"):
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
    Профили по specialization и specialization_extract.

    Технологический / естественно-научный → физ-мат + мед-био;
    соц-эконом → социально-экономический; гуманитарный → гуманитарный.
    Универсальный (без специализации) отдельно не выделяется.
    """
    texts = _collect_profile_texts(school)
    extract = {str(x).lower() for x in (school.get("specialization_extract") or [])}

    phys_math = False
    med_bio = False
    soc_econ = False
    humanities = False
    religious = False

    if "без специализации" in extract and len(extract) == 1:
        return {
            "profile_phys_math": None,
            "profile_med_bio": None,
            "profile_soc_econ": None,
            "profile_humanitarian": None,
            "profile_religious": None,
        }

    # Нормализованные теги парсера
    if "физ-мат" in extract:
        phys_math = True
    if "хим-био" in extract:
        med_bio = True
    if "технологическая" in extract:
        phys_math = True
        med_bio = True
    if "соц-эконом" in extract:
        soc_econ = True
    if "гуманитарная" in extract:
        humanities = True

    # Отдельные предметы (specialization_extract)
    subject_phys = (
        "физика",
        "математика",
        "математический профиль",
        "информатика",
        "информатика и икт",
    )
    subject_med = ("химия", "биология", "медицинский класс")
    subject_soc = ("обществознание", "право", "эконом")
    subject_hum = ("история", "русский язык", "литерат", "иностранн", "лингвист")

    for tag in extract:
        if tag in subject_phys:
            phys_math = True
        if tag in subject_med:
            med_bio = True
        if any(s in tag for s in subject_soc):
            soc_econ = True
        if any(s in tag for s in subject_hum):
            humanities = True
        if "религ" in tag:
            religious = True

    # Полные названия профилей (specialization)
    if _has_profile_keyword(
        texts,
        "физико-математ",
        "физ-мат",
        "физмат",
    ):
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
        med_bio = True
    if _has_profile_keyword(texts, "технолог"):
        phys_math = True
        med_bio = True
    if _has_profile_keyword(texts, "социально-эконом", "соц-эконом", "соцэкон"):
        soc_econ = True
    if _has_profile_keyword(texts, "гуманитар", "социально-гуманитар"):
        humanities = True
    if _has_profile_keyword(texts, "религиоз"):
        religious = True

    def as_flag(flag: bool) -> int | None:
        return 1 if flag else None

    return {
        "profile_phys_math": as_flag(phys_math),
        "profile_med_bio": as_flag(med_bio),
        "profile_soc_econ": as_flag(soc_econ),
        "profile_humanitarian": as_flag(humanities),
        "profile_religious": as_flag(religious),
    }


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
        "stadium": _sport_flag(
            school,
            "has_stadium",
            ("стадион",),
        ),
        "sports_ground": _sport_flag(
            school,
            "has_sports_ground",
            ("площадк", "коробка-трансформер"),
        ),
    }


def coords_from_school(school: dict[str, Any]) -> tuple[float | None, float | None]:
    lat = school.get("latitude")
    lon = school.get("longitude")
    if lat is not None and lon is not None:
        return round_or_none(lat, 6), round_or_none(lon, 6)
    loc = school.get("location")
    if isinstance(loc, dict):
        coords = loc.get("coordinates")
        if isinstance(coords, list) and len(coords) >= 2:
            # GeoJSON: [lon, lat]
            return round_or_none(coords[1], 6), round_or_none(coords[0], 6)
    return None, None


# --- Расчёты из распознанных отзывов и прочие поля ---


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


def parse_vuz_cell(raw: Any) -> tuple[float | str | None, int | None]:
    """
    Парсит ячейку «ВУЗы».
    2025 год → (процент float, 2025).
    Ранее → (строка «приведённый(исходный)», год данных).
    «нету» / пусто → (None, None).
    """
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
                data_year = VUZ_REFERENCE_YEAR - int(span_match.group(1))
            else:
                data_year = VUZ_REFERENCE_YEAR

    if data_year > VUZ_REFERENCE_YEAR:
        data_year = VUZ_REFERENCE_YEAR

    # В JSON храним исходный %; устаревание только в rating_university_admission.
    if abs(original_percent - round(original_percent)) < 0.05:
        return int(round(original_percent)), data_year
    return round(original_percent, 1), data_year


def _parse_ege_raw_score_and_year(raw: Any) -> tuple[float, int] | tuple[None, None]:
    """
    Парсит ячейку «ЕГЭ»: исходный средний балл (без устаревания) и год данных.
    """
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
    data_year = max(years)
    if data_year > EGE_REFERENCE_YEAR:
        data_year = EGE_REFERENCE_YEAR

    return round(score, 2), data_year


def adjust_ege_rating(raw_score: float, data_year: int) -> float:
    """Рейтинг ЕГЭ: −10% за каждый год отставания от 2025; ≥10 лет → 0."""
    years_behind = EGE_REFERENCE_YEAR - data_year
    if years_behind <= 0:
        return raw_score
    if years_behind >= MAX_DATA_AGE_YEARS:
        return 0.0
    return round(raw_score * (EGE_DECAY_PER_YEAR**years_behind), 2)


def adjust_vuz_rating(original_percent: float, data_year: int) -> float:
    """Рейтинг поступления в ВУЗ: −10% за год; ≥10 лет → 0. Исходный % не меняется."""
    years_behind = VUZ_REFERENCE_YEAR - data_year
    if years_behind <= 0:
        return round(original_percent, 1)
    if years_behind >= MAX_DATA_AGE_YEARS:
        return 0.0
    return round(original_percent * (VUZ_DECAY_PER_YEAR**years_behind), 1)


def _original_vuz_percent(stored: Any) -> float | None:
    """Исходный % из поля (поддержка старого формата «70.7(97)»)."""
    if stored is None:
        return None
    if isinstance(stored, str):
        inner = re.search(r"\((\d+(?:[.,]\d+)?)\)\s*$", stored.strip())
        if inner:
            return float(inner.group(1).replace(",", "."))
        return _to_float_or_none(stored)
    return _to_float_or_none(stored)


def _find_ege_column(df: pd.DataFrame) -> str | None:
    """
    В Excel заголовок столбца ЕГЭ может быть "битым" (из-за кодировки),
    поэтому ищем столбец по наличию типичного паттерна: число + '-' + год 20xx.
    """
    pattern = re.compile(r"(\d+(?:[.,]\d+)?)\s*-.*?(20\d{2})", flags=re.IGNORECASE)
    best_col = None
    best_cnt = 0
    for col in df.columns:
        try:
            s = df[col].dropna().astype(str)
        except Exception:
            continue
        cnt = 0
        for x in s.head(80).tolist():
            if pattern.search(x):
                cnt += 1
        if cnt > best_cnt:
            best_cnt = cnt
            best_col = col
    return best_col if best_cnt > 0 else None


def load_ege_map() -> dict[int, tuple[float, int]]:
    """
    school_id → (исходный средний балл ЕГЭ, год данных)
    """
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
    """school_id → (вместимость, источник: ссылка из Excel | Расчетный)."""
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


def load_vuz_map() -> dict[int, tuple[float | str | None, int | None]]:
    """school_id → (university_admission_percent, university_admission_year)."""
    if not CAPACITY_EXCEL.is_file():
        return {}

    df = pd.read_excel(CAPACITY_EXCEL, sheet_name=0)
    if "ВУЗы" not in df.columns:
        return {}

    result: dict[int, tuple[float | str | None, int | None]] = {}
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
    vuz_map: dict[int, tuple[float | str | None, int | None]],
) -> tuple[float | str | None, int | None]:
    school_id = school.get("id")
    if school_id is not None:
        try:
            mapped = vuz_map.get(int(school_id))
            if mapped is not None:
                return mapped
        except (TypeError, ValueError):
            pass
    return parse_vuz_cell(school.get("VUZ"))


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


def _infer_olympiad_stage(text: str) -> str:
    lower = text.lower()
    # По требованию: если есть "муниципального и регионального" — считать муниципальным.
    if "муницип" in lower:
        return "municipal"
    if "регион" in lower:
        return "regional"
    if "заключ" in lower or "федерал" in lower:
        return "final"
    return "unknown"


def _infer_olympiad_award(text: str) -> str:
    lower = text.lower()
    has_winner = "побед" in lower
    has_prizer = "приз" in lower
    if has_winner and has_prizer:
        return "mixed"
    if has_winner:
        return "winner"
    if has_prizer:
        return "prizer"
    return "unknown"


def _extract_year_span_from_text(text: str) -> int:
    lower = text.lower()
    span_match = re.search(r"за\s+(\d+)\s+год", lower)
    if span_match:
        return max(1, int(span_match.group(1)))
    range_match = re.search(r"(20\d{2})\s*-\s*(20\d{2})", lower)
    if range_match:
        y1 = int(range_match.group(1))
        y2 = int(range_match.group(2))
        return max(1, abs(y2 - y1) + 1)
    slash_year_match = re.search(r"(20\d{2})\s*/\s*(20\d{2})", lower)
    if slash_year_match:
        y1 = int(slash_year_match.group(1))
        y2 = int(slash_year_match.group(2))
        return max(1, abs(y2 - y1) + 1)
    return 1


def _extract_count_from_olympiad_text(text: str, stage: str) -> float:
    """
    Берём первое число как базовое.
    Для формата A/B:
    - при stage=municipal -> A
    - при stage=regional -> B
    - иначе -> A
    """
    slash_match = re.search(r"(\d+)\s*/\s*(\d+)", text)
    if slash_match:
        left = float(slash_match.group(1))
        right = float(slash_match.group(2))
        if stage == "regional":
            return right
        return left
    first_num = re.search(r"(\d+(?:[.,]\d+)?)", text)
    if not first_num:
        return 0.0
    return float(first_num.group(1).replace(",", "."))


def _normalize_name_for_group(name: Any) -> str:
    if name is None:
        return ""
    normalized = re.sub(r"\s+", " ", str(name).strip().lower())
    return normalized


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
    """
    Ищем классы рядом с упоминанием школы:
    ... № 14 (1-9-е классы) ...
    """
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
    """
    Строит карту: номер школы -> административный район(ы),
    при наличии — с диапазонами классов.
    """
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
            # Берём только ячейки, похожие на наименование школы (а не шапки документа).
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
                        if cls:
                            entry = f"{district} ({cls})"
                        else:
                            entry = district
                        result_by_num.setdefault(num, set()).add(entry)
                        result_by_num_kind.setdefault((num, kind), set()).add(entry)

    normalized: dict[int, str] = {}
    for num, entries in result_by_num.items():
        # Сортируем: сначала чистые районы, потом с классами
        sorted_entries = sorted(entries, key=lambda x: (x.count("("), x))
        normalized[num] = "; ".join(sorted_entries)
    # Добавляем приоритетные ключи по типу школы как отрицательные номера-шаблоны через префикс.
    # Это внутренний служебный трюк: ключи вида -(num*10 + kind_code) не пересекаются с реальными id.
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
    kind = _school_kind(str(school.get("name_2gis") or "") + " " + str(school.get("short_name") or ""))
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


def build_olympiad_metrics_map(
    source_schools: list[dict[str, Any]],
    kept_schools: list[dict[str, Any]],
    capacity_map: dict[int, tuple[int, str]],
) -> dict[int, dict[str, Any]]:
    """
    Готовит метрики олимпиад:
      - olympiad_winners_count
      - olympiad_years_span
      - rating_olympiads

    Если у одинаковых школ (по short_name) данные есть только в одной записи,
    распределяем между всеми записями группы пропорционально площади здания.
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
        year_span = 1
        has_any = False

        for current_id in ids:
            current = source_by_id.get(current_id)
            if not current:
                continue
            for entry in _extract_olympiad_entries(current):
                stage = _infer_olympiad_stage(entry)
                count = _extract_count_from_olympiad_text(entry, stage)
                if count <= 0:
                    continue
                span = _extract_year_span_from_text(entry)
                year_span = max(year_span, span)
                total_raw += count
                has_any = True

        metrics[sid] = {
            "raw_total": total_raw,
            "year_span": year_span,
            "has_data": has_any,
            "area_sqm": float(school.get("area_sqm") or 0.0),
        }

    # Распределение между одинаковыми школами (разные корпуса) по площади
    grouped: dict[str, list[int]] = {}
    for school in kept_schools:
        try:
            sid = int(school.get("id"))
        except (TypeError, ValueError):
            continue
        key = _normalize_name_for_group(school.get("short_name") or school.get("name_2gis"))
        if not key:
            continue
        grouped.setdefault(key, []).append(sid)

    for _name_key, ids in grouped.items():
        if len(ids) < 2:
            continue
        with_data = [sid for sid in ids if metrics.get(sid, {}).get("has_data")]
        without_data = [sid for sid in ids if not metrics.get(sid, {}).get("has_data")]
        if not with_data or not without_data:
            continue

        total_raw = sum(metrics[sid]["raw_total"] for sid in with_data)
        year_span = max(metrics[sid]["year_span"] for sid in with_data)
        if total_raw <= 0:
            continue

        area_sum = 0.0
        for sid in ids:
            area = metrics[sid]["area_sqm"]
            area_sum += area if area > 0 else 1.0

        for sid in ids:
            area = metrics[sid]["area_sqm"]
            weight = (area if area > 0 else 1.0) / area_sum
            metrics[sid]["raw_total"] = total_raw * weight
            metrics[sid]["year_span"] = year_span
            metrics[sid]["has_data"] = True

    per_capita: dict[int, float] = {}
    for sid, info in metrics.items():
        if not info.get("has_data"):
            continue
        year_span = max(1, int(info["year_span"]))
        winners = float(info["raw_total"])
        if winners <= 0:
            continue
        school_stub = {"id": sid}
        capacity, _source = capacity_for_school(school_stub, capacity_map)
        if capacity and capacity > 0:
            per_capita[sid] = winners / year_span / capacity

    max_raw = max(per_capita.values()) if per_capita else 0.0
    if per_capita:
        sorted_vals = sorted(per_capita.values())
        p95_idx = int(round(0.95 * (len(sorted_vals) - 1)))
        p95_ref = sorted_vals[p95_idx]
        if p95_ref > 0:
            max_raw = min(max_raw, p95_ref)

    final_map: dict[int, dict[str, Any]] = {}
    for sid, info in metrics.items():
        if not info.get("has_data"):
            final_map[sid] = {
                "olympiad_winners_count": None,
                "olympiad_years_span": None,
                "rating_olympiads": None,
            }
            continue
        year_span = max(1, int(info["year_span"]))
        winners = int(round(float(info["raw_total"])))
        raw_pc = per_capita.get(sid)
        rating = None
        if raw_pc is not None and max_raw > 0:
            rating = round(min(raw_pc, max_raw) / max_raw * 100.0, 1)
        final_map[sid] = {
            "olympiad_winners_count": winners,
            "olympiad_years_span": year_span,
            "rating_olympiads": rating,
        }

    return final_map


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


def _school_ids_for_reviews(school_id: Any) -> list[int]:
    try:
        primary = int(school_id)
    except (TypeError, ValueError):
        return []
    ids = [primary]
    ids.extend(REVIEW_ALIAS_IDS.get(primary, []))
    return ids


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


def _extract_topics(review: dict[str, Any]) -> list[str]:
    return [topic for topic, _sentiment in _extract_topic_sentiments(review)]


def _extract_topic_sentiments(review: dict[str, Any]) -> list[tuple[str, str]]:
    """
    Нормализует темы в единый формат.
    Поддерживаем два типа:
    1) {"topics": {"учителя": "pos", ...}}
    2) {"topics": [{"topic": "учителя", "sentiment": "pos"}, ...]}
    """
    topics = review.get("topics")
    result: list[tuple[str, str]] = []

    if isinstance(topics, dict):
        for topic, sentiment in topics.items():
            if not isinstance(topic, str) or not topic.strip():
                continue
            if not isinstance(sentiment, str):
                continue
            result.append((topic.strip(), sentiment.strip().lower()))
        return result

    if isinstance(topics, list):
        for item in topics:
            if not isinstance(item, dict):
                continue
            topic = item.get("topic")
            sentiment = item.get("sentiment")
            if not isinstance(topic, str) or not topic.strip():
                continue
            if not isinstance(sentiment, str):
                continue
            result.append((topic.strip(), sentiment.strip().lower()))
        return result

    return result


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
    # Индекс тональности 0..1 (не 10 и не 100): pos=1, neutral=0.5, neg=0
    return round((mean + 1) / 2, 3)


def review_ratings_from_analysis(school_id: Any) -> dict[str, float | None]:
    reviews = load_reviews_for_school(school_id)
    result: dict[str, float | None] = {
        field: None for field in REVIEW_TOPIC_GROUPS
    }
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


def compute_rating_total(record: dict[str, Any]) -> float | None:
    """Итог = простая сумма всех заполненных рейтингов (может быть > 100)."""
    total = 0.0
    found = False
    for key in RATING_TOTAL_SUM_KEYS:
        value = _to_float_or_none(record.get(key))
        if value is None:
            continue
        total += value
        found = True
    if not found:
        return None
    return round(total, 2)


def top_tags_from_analysis(school_id: Any) -> list[str]:
    """
    Топ-5 самых частых топиков из распознанных отзывов школы.
    Учитываются только названия топиков, без pos/neg.
    """
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


def empty_ratings_block() -> dict[str, Any]:
    return {
        "rating_total": None,
        "top_tags": [],
        "rating_ege": None,
        "rating_olympiads": None,
        "rating_teachers": None,
        "rating_mto": None,
        "rating_sports_infrastructure": None,
        "rating_psychological_climate": None,
        "ege_average_score": 0.0,
        "ege_year": None,
        "rating_university_admission": None,
        "university_admission_percent": None,
        "university_admission_year": None,
        "olympiad_winners_count": None,
        "olympiad_years_span": None,
        "capacity_students": None,
        "capacity_source": None,
        "mto_url": None,
        "administrative_district": None,
    }


def transform_school(
    school: dict[str, Any],
    capacity_map: dict[int, tuple[int, str]],
    vuz_map: dict[int, tuple[float | str | None, int | None]],
    ege_map: dict[int, tuple[float, int]],
    olympiad_map: dict[int, dict[str, Any]],
    district_map: dict[int, str],
) -> dict[str, Any]:
    lat, lon = coords_from_school(school)
    profiles = derive_profiles(school)
    sports = derive_sports(school)

    ratings = empty_ratings_block()
    school_id = school.get("id")
    ratings["top_tags"] = top_tags_from_analysis(school_id)
    ratings.update(review_ratings_from_analysis(school_id))

    # Спорт: 0..4 только если по зданию есть хоть какие-то данные; иначе None (не в итоге).
    sport_keys = ("fok", "pool", "stadium", "sports_ground")
    sport_flags = [sports.get(k) for k in sport_keys]
    if any(v is not None for v in sport_flags):
        ratings["rating_sports_infrastructure"] = sum(1 for v in sport_flags if v == 1)
    else:
        ratings["rating_sports_infrastructure"] = None

    # "Рейтинг МТО и удобства доступа" — единое поле `rating_mto` (без отдельного поля доступа в JSON).
    mto = ratings.pop("rating_mto", None)
    access = ratings.pop("rating_access_convenience", None)
    if mto is not None and access is not None:
        ratings["rating_mto"] = round((float(mto) + float(access)) / 2.0, 1)
    elif mto is not None or access is not None:
        ratings["rating_mto"] = mto if mto is not None else access

    capacity, capacity_source = capacity_for_school(school, capacity_map)
    ratings["capacity_students"] = capacity
    ratings["capacity_source"] = capacity_source
    ratings["mto_url"] = school.get("infrastructure")

    vuz_percent, vuz_year = vuz_for_school(school, vuz_map)
    ratings["university_admission_percent"] = vuz_percent
    ratings["university_admission_year"] = vuz_year
    vuz_original = _original_vuz_percent(vuz_percent)
    if vuz_original is not None and vuz_year is not None:
        ratings["rating_university_admission"] = adjust_vuz_rating(vuz_original, int(vuz_year))
    else:
        ratings["rating_university_admission"] = None

    school_id = school.get("id")
    if school_id is not None:
        try:
            ege_mapped = ege_map.get(int(school_id))
        except (TypeError, ValueError):
            ege_mapped = None
    else:
        ege_mapped = None

    if ege_mapped is not None:
        raw_ege, ege_year = ege_mapped
        ratings["ege_average_score"] = raw_ege
        ratings["ege_year"] = ege_year
        ratings["rating_ege"] = adjust_ege_rating(raw_ege, ege_year)
    else:
        ratings["ege_average_score"] = 0.0
        ratings["ege_year"] = None
        ratings["rating_ege"] = None

    if school_id is not None:
        try:
            olympiad = olympiad_map.get(int(school_id))
        except (TypeError, ValueError):
            olympiad = None
    else:
        olympiad = None
    if olympiad is not None:
        ratings["olympiad_winners_count"] = olympiad.get("olympiad_winners_count")
        ratings["olympiad_years_span"] = olympiad.get("olympiad_years_span")
        ratings["rating_olympiads"] = olympiad.get("rating_olympiads")
    ratings["administrative_district"] = administrative_district_for_school(school, district_map)

    record: dict[str, Any] = {
        "id": school.get("id"),
        "name_2gis": school.get("name_2gis"),
        "short_name": school.get("short_name"),
        "address": school.get("address"),
        "building_type": school.get("building_type"),
        "rating_2gis": rating_stars_1_to_5(school.get("rating_2gis")),
        "rating_yandex": rating_stars_1_to_5(school.get("rating_yandex")),
        **ratings,
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
    apply_rating_totals(result)

    save_schools(OUTPUT_JSON, result)
    print(f"OK: {len(result)} schools -> {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
