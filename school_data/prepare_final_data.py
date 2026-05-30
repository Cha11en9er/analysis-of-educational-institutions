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

# Префикс ID объекта по спецификации (6448 + 4 цифры порядкового номера)
OBJECT_ID_PREFIX = 64480000

# Топики распознавания отзывов → поля рейтинга
REVIEW_TOPIC_GROUPS: dict[str, tuple[str, ...]] = {
    "rating_teachers": ("учителя",),
    "rating_mto": ("ремонт", "инфраструктура", "уборка"),
    "rating_access_convenience": ("инфраструктура", "охрана"),
    "rating_psychological_climate": ("буллинг", "администрация"),
}

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


def load_capacity_map() -> dict[int, tuple[int, str]]:
    """school_id → (вместимость, источник: Проектный | Расчетный)."""
    if not CAPACITY_EXCEL.is_file():
        return {}

    df = pd.read_excel(CAPACITY_EXCEL, sheet_name=0)
    result: dict[int, tuple[int, str]] = {}

    for _, row in df.iterrows():
        raw_id = row.iloc[0]
        if raw_id is None or (isinstance(raw_id, float) and pd.isna(raw_id)):
            continue

        id_parts = re.findall(r"\d+", str(raw_id).strip())
        if not id_parts:
            continue
        school_id = int(id_parts[-1])

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
            source_kind = "Проектный"

        result[school_id] = (capacity, source_kind)

    return result


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
    topics = review.get("topics")
    if not isinstance(topics, dict) or not topics:
        return []
    result: list[str] = []
    for topic in topics:
        if isinstance(topic, str) and topic.strip():
            result.append(topic.strip())
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
    # Шкала 0–10: среднее по pos(+1)/neg(-1)/neutral(0)
    return round((mean + 1) / 2 * 10, 1)


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
            topics = review.get("topics")
            if not isinstance(topics, dict):
                continue
            for topic_name in topic_names:
                if topic_name not in topics:
                    continue
                score = _sentiment_to_score(topics[topic_name])
                if score is not None:
                    scores.append(score)
        result[field] = _rating_from_topic_scores(scores)

    return result


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
        "rating_university_admission": None,
        "rating_teachers": None,
        "rating_mto": None,
        "rating_sports_infrastructure": None,
        "rating_access_convenience": None,
        "rating_psychological_climate": None,
        "ege_average_score": None,
        "ege_year": None,
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
) -> dict[str, Any]:
    lat, lon = coords_from_school(school)
    profiles = derive_profiles(school)
    sports = derive_sports(school)

    ratings = empty_ratings_block()
    school_id = school.get("id")
    ratings["top_tags"] = top_tags_from_analysis(school_id)
    ratings.update(review_ratings_from_analysis(school_id))

    capacity, capacity_source = capacity_for_school(school, capacity_map)
    ratings["capacity_students"] = capacity
    ratings["capacity_source"] = capacity_source
    ratings["mto_url"] = school.get("infrastructure")

    record: dict[str, Any] = {
        "object_id": object_id_from_school_id(school.get("id")),
        "name_2gis": school.get("name_2gis"),
        "short_name": school.get("short_name"),
        "address": school.get("address"),
        "building_type": school.get("building_type"),
        "rating_2gis": round_or_none(school.get("rating_2gis"), 1),
        "rating_yandex": round_or_none(school.get("rating_yandex"), 1),
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

    # Сохраняем исходный id школы для отладки и будущих скриптов
    record["school_id"] = school.get("id")

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


def main() -> None:
    if not INPUT_JSON.is_file():
        raise FileNotFoundError(f"Нет входного файла: {INPUT_JSON}")

    capacity_map = load_capacity_map()
    source = load_schools(INPUT_JSON)
    result = []
    for school in source:
        try:
            sid = int(school.get("id"))
        except (TypeError, ValueError):
            sid = None
        if sid in SCHOOL_IDS_TO_DROP:
            continue
        result.append(transform_school(school, capacity_map))

    save_schools(OUTPUT_JSON, result)
    print(f"OK: {len(result)} schools -> {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
