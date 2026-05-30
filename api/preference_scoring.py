# -*- coding: utf-8 -*-
"""
Подбор школ по приоритетам: объединяет данные из infrastructure JSON и
файлов school_reviews_separately_*_analyz.json. Нормализация метрик — min-max
по всем школам, у которых есть сырые данные; при отсутствии данных по измерению
для конкретной школы используется нейтральное значение 0.5 (см. SCHOOL_PREFERENCES.md).
"""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from glob import glob
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
INFRA_JSON = REPO_ROOT / "parsing/school_gosuslugi/sg_data/sg_data_output/sd_2_stage_gosuslugi_infrastucture_output.json"
REVIEWS_PATTERN = str(
    REPO_ROOT / "review_data/rd_2_stage_analys/rd_separately_analyzed/school_reviews_separately_*_analyz.json"
)
# Финальные отзывы (текст + дата + topics), те же что грузятся в БД и в графики на сайте.
FINAL_REVIEWS_PATTERN = str(
    REPO_ROOT / "review_data/rd_3_stage/rd_3_stage_data/school_review_separately_*_final.json"
)

_SENTIMENT = {"pos": 1.0, "neg": 0.0, "neutral": 0.5}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _parse_olympiad_line(s: str) -> float:
    m = re.match(r"^\s*(\d+)\s*[-–]", str(s))
    n = float(m.group(1)) if m else 0.0
    sl = str(s).lower()
    tier = 1.0
    if "заключительн" in sl:
        tier = 4.0
    elif "региональн" in sl:
        tier = 2.5
    elif "муниципальн" in sl:
        tier = 2.0
    elif "школьн" in sl or "школ" in sl and "этап" in sl:
        tier = 1.0
    elif "всероссийск" in sl:
        tier = 2.0
    role = 1.0
    if "победител" in sl:
        role = 1.3
    return n * tier * role


def _olympiad_score_from_school(obj: Dict[str, Any]) -> float:
    raw = obj.get("Olympiads") or obj.get("olympiads")
    if not raw:
        return 0.0
    if isinstance(raw, str):
        raw = [raw]
    total = 0.0
    for line in raw:
        total += _parse_olympiad_line(line)
    return math.log1p(total)


def _parse_ege_vuz(obj: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    ege_s = obj.get("EGE") or obj.get("ege")
    vuz_s = obj.get("VUZ") or obj.get("vuz")
    ege_val = None
    vuz_val = None
    if ege_s and isinstance(ege_s, str):
        m = re.search(r"(\d+)[,.](\d+)", ege_s.replace(" ", ""))
        if m:
            ege_val = float(f"{m.group(1)}.{m.group(2)}")
        else:
            m2 = re.search(r"(\d+)\s*[-–]", ege_s)
            if m2:
                ege_val = float(m2.group(1))
    if vuz_s and isinstance(vuz_s, str):
        m = re.search(r"(\d+)\s*%", vuz_s.replace(" ", ""))
        if m:
            vuz_val = float(m.group(1))
    return ege_val, vuz_val


def _building_static(obj: Dict[str, Any]) -> float:
    """Сводный сырой балл по паспорту здания (до нормализации по выборке)."""
    parts: List[float] = []
    bt = (obj.get("building_type") or "") or ""
    if "новыми корпусами" in bt.lower():
        parts.append(1.0)
    else:
        parts.append(0.35)
    area = obj.get("area_sqm")
    if area is not None:
        try:
            parts.append(math.log1p(float(area)) / math.log1p(50000))
        except (TypeError, ValueError):
            parts.append(0.0)
    else:
        parts.append(0.0)
    fl = obj.get("floors")
    if fl is not None:
        try:
            parts.append(min(float(fl) / 12.0, 1.0))
        except (TypeError, ValueError):
            parts.append(0.0)
    else:
        parts.append(0.0)
    ry = obj.get("reconstruction_year")
    if ry is not None:
        try:
            y = float(ry)
            parts.append(min(max((y - 1980) / 40.0, 0.0), 1.0))
        except (TypeError, ValueError):
            parts.append(0.0)
    else:
        parts.append(0.15)
    inf = obj.get("infrastucture") or obj.get("infrastructure")
    if isinstance(inf, list):
        parts.append(min(len(inf) / 6.0, 1.0))
    elif isinstance(inf, str) and inf.strip():
        parts.append(0.4)
    else:
        parts.append(0.0)
    return sum(parts) / len(parts)


def _avg_topic_sentiment(reviews: List[Dict[str, Any]], keys: Tuple[str, ...]) -> Optional[float]:
    vals: List[float] = []
    for r in reviews:
        topics = r.get("topics") or {}
        if not isinstance(topics, dict):
            continue
        for k in keys:
            if k in topics and topics[k] in _SENTIMENT:
                vals.append(_SENTIMENT[topics[k]])
    if not vals:
        return None
    return sum(vals) / len(vals)


def _school_id_from_review_filename(path: str) -> Optional[int]:
    base = Path(path).name
    m = re.match(r"school_reviews_separately_(\d+)_analyz\.json$", base)
    return int(m.group(1)) if m else None


def _school_id_from_rd3_final_filename(path: str) -> Optional[int]:
    m = re.match(r"school_review_separately_(\d+)_final\.json$", Path(path).name)
    return int(m.group(1)) if m else None


def _min_max_norm(values: Dict[int, float], school_id: int, neutral: float = 0.5) -> float:
    xs = [v for v in values.values() if v is not None]
    if school_id not in values:
        return neutral
    v = values[school_id]
    if len(xs) < 2:
        return 0.5 if v is not None else neutral
    lo, hi = min(xs), max(xs)
    if hi <= lo:
        return 0.5
    return (v - lo) / (hi - lo)


def _min_max_norm_present(values: Dict[int, float], school_id: int) -> Optional[float]:
    """Нормализация только если школа есть в словаре измерений."""
    if school_id not in values:
        return None
    return _min_max_norm(values, school_id, neutral=0.5)


@lru_cache(maxsize=1)
def load_preference_bundle() -> Dict[str, Any]:
    """Загружает JSON и считает нормализованные метрики по school_id."""
    by_id: Dict[int, Dict[str, float]] = {}

    if INFRA_JSON.is_file():
        with open(INFRA_JSON, "r", encoding="utf-8") as f:
            schools = json.load(f)
        for obj in schools:
            sid = obj.get("id")
            if sid is None:
                continue
            sid = int(sid)
            by_id.setdefault(sid, {})
            oly = _olympiad_score_from_school(obj)
            by_id[sid]["_olympiad_raw"] = oly
            ege, vuz = _parse_ege_vuz(obj)
            if ege is not None:
                by_id[sid]["_ege_raw"] = ege
            if vuz is not None:
                by_id[sid]["_vuz_raw"] = vuz
            by_id[sid]["_building_static_raw"] = _building_static(obj)

    for path in glob(REVIEWS_PATTERN):
        sid = _school_id_from_review_filename(path)
        if sid is None:
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                reviews = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(reviews, list):
            continue
        by_id.setdefault(sid, {})
        b = by_id[sid]
        bs = _avg_topic_sentiment(reviews, ("буллинг",))
        if bs is not None:
            b["_bullying_raw"] = bs
        st = _avg_topic_sentiment(reviews, ("учителя", "администрация"))
        if st is not None:
            b["_staff_raw"] = st
        rep = _avg_topic_sentiment(reviews, ("ремонт",))
        inf = _avg_topic_sentiment(reviews, ("инфраструктура",))
        br_parts = [x for x in (rep, inf) if x is not None]
        if br_parts:
            b["_building_review_raw"] = sum(br_parts) / len(br_parts)

    olympiad_map = {k: v["_olympiad_raw"] for k, v in by_id.items() if "_olympiad_raw" in v}
    ege_map = {k: v["_ege_raw"] for k, v in by_id.items() if "_ege_raw" in v}
    vuz_map = {k: v["_vuz_raw"] for k, v in by_id.items() if "_vuz_raw" in v}
    bstat_map = {k: v["_building_static_raw"] for k, v in by_id.items() if "_building_static_raw" in v}
    bully_map = {k: v["_bullying_raw"] for k, v in by_id.items() if "_bullying_raw" in v}
    staff_map = {k: v["_staff_raw"] for k, v in by_id.items() if "_staff_raw" in v}
    br_map = {k: v["_building_review_raw"] for k, v in by_id.items() if "_building_review_raw" in v}

    metrics: Dict[int, Dict[str, float]] = {}
    for sid in by_id:
        m: Dict[str, float] = {}
        m["olympiads"] = _min_max_norm(olympiad_map, sid) if olympiad_map else 0.5
        ege_n = _min_max_norm_present(ege_map, sid) if ege_map else None
        vuz_n = _min_max_norm_present(vuz_map, sid) if vuz_map else None
        if ege_n is not None and vuz_n is not None:
            m["exam"] = 0.5 * ege_n + 0.5 * vuz_n
        elif ege_n is not None:
            m["exam"] = ege_n
        elif vuz_n is not None:
            m["exam"] = vuz_n
        else:
            m["exam"] = 0.5
        if bstat_map:
            bs_n = _min_max_norm(bstat_map, sid)
        else:
            bs_n = 0.5
        if br_map:
            br_n = _min_max_norm(br_map, sid)
        else:
            br_n = 0.5
        m["building"] = 0.55 * bs_n + 0.45 * br_n
        m["bullying"] = _min_max_norm(bully_map, sid) if bully_map else 0.5
        m["staff"] = _min_max_norm(staff_map, sid) if staff_map else 0.5
        metrics[sid] = m

    final_review_school_ids: set = set()
    for path in glob(FINAL_REVIEWS_PATTERN):
        sid = _school_id_from_rd3_final_filename(path)
        if sid is not None:
            final_review_school_ids.add(sid)

    return {
        "metrics_by_school": metrics,
        "final_review_school_ids": frozenset(final_review_school_ids),
    }


def score_school_row(
    school_id: int,
    lat: Optional[float],
    lon: Optional[float],
    prefs: Dict[str, bool],
    user_lat: Optional[float],
    user_lon: Optional[float],
    bundle: Dict[str, Any],
) -> Tuple[float, Dict[str, float]]:
    """
    prefs: olympiads, bullying, staff, building, exam, location
    Возвращает (итог 0..1, разбивка по включённым осям).
    """
    metrics_by_school: Dict[int, Dict[str, float]] = bundle["metrics_by_school"]
    m = metrics_by_school.get(school_id, {})
    olympiads = m.get("olympiads", 0.5)
    bullying = m.get("bullying", 0.5)
    staff = m.get("staff", 0.5)
    building = m.get("building", 0.5)
    exam = m.get("exam", 0.5)

    loc_score = 0.5
    if (
        prefs.get("location")
        and user_lat is not None
        and user_lon is not None
        and lat is not None
        and lon is not None
    ):
        d = _haversine_km(user_lat, user_lon, lat, lon)
        loc_score = 1.0 / (1.0 + d / 3.0)

    keys = ("olympiads", "bullying", "staff", "building", "exam", "location")
    active = [k for k in keys if prefs.get(k)]
    if not active:
        return 0.0, {}

    parts: Dict[str, float] = {}
    if "olympiads" in active:
        parts["olympiads"] = olympiads
    if "bullying" in active:
        parts["bullying"] = bullying
    if "staff" in active:
        parts["staff"] = staff
    if "building" in active:
        parts["building"] = building
    if "exam" in active:
        parts["exam"] = exam
    if "location" in active:
        parts["location"] = loc_score

    total = sum(parts.values()) / len(parts)
    return total, parts
