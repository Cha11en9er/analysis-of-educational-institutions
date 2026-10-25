# -*- coding: utf-8 -*-
"""Чтение школ и отзывов из JSON (без PostgreSQL)."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
FINAL_SCHOOLS_JSON = REPO_ROOT / "school_data" / "final_school_data.json"
REVIEWS_ANALYZED_DIR = (
    REPO_ROOT / "review_data" / "rd_2_stage_analys" / "rd_separately_analyzed"
)
REVIEWS_PATTERN = re.compile(r"school_reviews_separately_(\d+)_analyz\.json$")


def _truthy_flag(value: Any) -> bool:
    return value == 1 or value is True


@lru_cache(maxsize=1)
def load_schools_raw() -> list[dict[str, Any]]:
    if not FINAL_SCHOOLS_JSON.is_file():
        raise FileNotFoundError(f"Нет файла: {FINAL_SCHOOLS_JSON}")
    data = json.loads(FINAL_SCHOOLS_JSON.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Ожидался массив школ в {FINAL_SCHOOLS_JSON}")
    return data


@lru_cache(maxsize=1)
def review_analysis_school_ids() -> frozenset[int]:
    ids: set[int] = set()
    if not REVIEWS_ANALYZED_DIR.is_dir():
        return frozenset()
    for path in REVIEWS_ANALYZED_DIR.glob("school_reviews_separately_*_analyz.json"):
        m = REVIEWS_PATTERN.match(path.name)
        if m:
            ids.add(int(m.group(1)))
    return frozenset(ids)


def school_to_map_item(raw: dict[str, Any]) -> dict[str, Any]:
    sid = int(raw["id"])
    lat = raw.get("latitude")
    lon = raw.get("longitude")
    coords = None
    if lat is not None and lon is not None:
        coords = [float(lon), float(lat)]
    return {
        "school_id": sid,
        "name_2gis": raw.get("name_2gis"),
        "name_ym": raw.get("short_name"),
        "school_address": raw.get("address"),
        "year_built": raw.get("year_built"),
        "has_sports_complex": _truthy_flag(raw.get("fok")),
        "has_pool": _truthy_flag(raw.get("pool")),
        "has_stadium": _truthy_flag(raw.get("stadium")),
        "has_sports_ground": _truthy_flag(raw.get("sports_ground")),
        "location": {"type": "Point", "coordinates": coords},
        "rating_yandex": raw.get("rating_yandex"),
        "rating_2gis": raw.get("rating_2gis"),
        "rating_total": raw.get("rating_total"),
        "ege_average_score": raw.get("ege_average_score"),
        "olympiad_winners_count": raw.get("olympiad_winners_count"),
        "has_review_analysis": sid in review_analysis_school_ids(),
    }


def school_to_detail(raw: dict[str, Any]) -> dict[str, Any]:
    item = school_to_map_item(raw)
    item.update(
        {
            "building_type": raw.get("building_type"),
            "floors": raw.get("floors"),
            "reconstruction_year": raw.get("reconstruction_year"),
            "link_2gis": raw.get("link_2gis"),
            "link_yandex": raw.get("link_yandex"),
            "link_gosuslugi": raw.get("link_gosuslugi"),
            "short_name": raw.get("short_name"),
            "city": raw.get("city") or "Саратов",
            "top_tags": raw.get("top_tags") or [],
            "ege_average_score": raw.get("ege_average_score"),
            "ege_year": raw.get("ege_year"),
            "university_admission_percent": raw.get("university_admission_percent"),
            "university_admission_year": raw.get("university_admission_year"),
            "olympiad_winners_count": raw.get("olympiad_winners_count"),
            "administrative_district": raw.get("administrative_district"),
            "rating_ege": raw.get("rating_ege"),
            "rating_olympiads": raw.get("rating_olympiads"),
            "rating_teachers": raw.get("rating_teachers"),
            "rating_mto": raw.get("rating_mto"),
            "rating_psychological_climate": raw.get("rating_psychological_climate"),
            "rating_sports_infrastructure": raw.get("rating_sports_infrastructure"),
            "rating_profiles": raw.get("rating_profiles"),
            "year_built": raw.get("year_built"),
            "capacity": raw.get("capacity_students"),
            "area_sqm": raw.get("area_sqm"),
            "wall_material": raw.get("wall_material"),
        }
    )
    return item


def get_school_raw(school_id: int) -> Optional[dict[str, Any]]:
    for raw in load_schools_raw():
        try:
            if int(raw.get("id")) == school_id:
                return raw
        except (TypeError, ValueError):
            continue
    return None


def filter_schools_for_map(
    *,
    search: Optional[str] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    rating_min: Optional[float] = None,
    rating_max: Optional[float] = None,
    has_pool: Optional[bool] = None,
    has_stadium: Optional[bool] = None,
    has_sports_ground: Optional[bool] = None,
    has_sports_complex: Optional[bool] = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    needle = (search or "").strip().lower()

    for raw in load_schools_raw():
        year = raw.get("year_built")
        if year_min is not None and (year is None or int(year) < year_min):
            continue
        if year_max is not None and (year is None or int(year) > year_max):
            continue

        rating = raw.get("rating_yandex")
        if rating_min is not None and (rating is None or float(rating) < rating_min):
            continue
        if rating_max is not None and (rating is None or float(rating) > rating_max):
            continue

        if has_pool is True and not _truthy_flag(raw.get("pool")):
            continue
        if has_stadium is True and not _truthy_flag(raw.get("stadium")):
            continue
        if has_sports_ground is True and not _truthy_flag(raw.get("sports_ground")):
            continue
        if has_sports_complex is True and not _truthy_flag(raw.get("fok")):
            continue

        if needle:
            blob = " ".join(
                str(x or "")
                for x in (
                    raw.get("name_2gis"),
                    raw.get("short_name"),
                    raw.get("address"),
                )
            ).lower()
            if needle not in blob:
                continue

        out.append(school_to_map_item(raw))

    out.sort(key=lambda s: s["school_id"])
    return out


def load_reviews_topics(school_id: int) -> list[dict[str, Any]]:
    path = REVIEWS_ANALYZED_DIR / f"school_reviews_separately_{school_id}_analyz.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

    items = data if isinstance(data, list) else data.get("reviews") if isinstance(data, dict) else []
    if not isinstance(items, list):
        return []

    reviews: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        topics = item.get("topics")
        if not isinstance(topics, dict):
            topics = {}
        date_val = item.get("date") or item.get("review_date")
        if date_val is None:
            continue
        if hasattr(date_val, "isoformat"):
            date_val = date_val.isoformat()
        else:
            date_val = str(date_val)[:10]
        reviews.append({"review_date": date_val, "topics": topics})
    reviews.sort(key=lambda r: r["review_date"])
    return reviews
