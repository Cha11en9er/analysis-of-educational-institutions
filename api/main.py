#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API школ: по умолчанию читает JSON (school_data/final_school_data.json).
DATA_SOURCE=db — старый режим PostgreSQL.
"""

from __future__ import annotations

import json as json_lib
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

_api_dir = str(Path(__file__).resolve().parent)
if _api_dir not in sys.path:
    sys.path.insert(0, _api_dir)

from json_data import (  # noqa: E402
    filter_schools_for_map,
    get_school_raw,
    load_reviews_topics,
    load_schools_raw,
    review_analysis_school_ids,
    school_to_detail,
    school_to_map_item,
)
from preference_scoring import load_preference_bundle, score_school_row  # noqa: E402

_repo_root = Path(__file__).resolve().parent.parent
load_dotenv(_repo_root / ".env")
load_dotenv()

# json | db  — сейчас по умолчанию json (БД на сервере ещё не готова)
DATA_SOURCE = (os.getenv("DATA_SOURCE") or "json").strip().lower()

app = FastAPI(title="Schools API", version="1.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://uchgrad.ru",
        "https://www.uchgrad.ru",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}


def use_json() -> bool:
    return DATA_SOURCE != "db"


def get_db_connection():
    try:
        import psycopg2
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"psycopg2 не установлен: {e}") from e
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка подключения к БД: {str(e)}") from e


def apply_preference_scores(
    schools: list[dict[str, Any]],
    *,
    pref_olympiads: bool,
    pref_bullying: bool,
    pref_staff: bool,
    pref_building: bool,
    pref_exam: bool,
    pref_location: bool,
    user_lat: Optional[float],
    user_lon: Optional[float],
) -> list[dict[str, Any]]:
    prefs = {
        "olympiads": pref_olympiads,
        "bullying": pref_bullying,
        "staff": pref_staff,
        "building": pref_building,
        "exam": pref_exam,
        "location": pref_location,
    }
    if not any(prefs.values()):
        for sch in schools:
            sch["preference_score"] = None
            sch["preference_breakdown"] = None
        return schools

    if pref_location and (user_lat is None or user_lon is None):
        raise HTTPException(
            status_code=400,
            detail="Для приоритета «близость» укажите user_lat и user_lon",
        )

    try:
        bundle = load_preference_bundle()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось загрузить данные для подбора: {str(e)}",
        ) from e

    for sch in schools:
        sid = sch["school_id"]
        coords = sch.get("location") and sch["location"].get("coordinates")
        lat = lon = None
        if coords and len(coords) == 2:
            lon, lat = float(coords[0]), float(coords[1])
        total, breakdown = score_school_row(
            sid, lat, lon, prefs, user_lat, user_lon, bundle
        )
        sch["preference_score"] = round(total * 100.0, 1)
        sch["preference_breakdown"] = {k: round(v * 100.0, 1) for k, v in breakdown.items()}
    schools.sort(key=lambda x: x["preference_score"], reverse=True)
    return schools


@app.get("/")
async def root():
    return {
        "message": "Schools API",
        "version": "1.2.0",
        "data_source": "json" if use_json() else "db",
    }


@app.get("/api/config")
async def public_config():
    """
    Публичные настройки для фронта.
    YANDEX_API_KEY для JS Maps и так светится в браузере — ограничение ключа: HTTP Referrer.
    """
    key = (os.getenv("YANDEX_API_KEY") or os.getenv("REACT_APP_YANDEX_API_KEY") or "").strip()
    return {
        "yandex_api_key": key or None,
        "data_source": "json" if use_json() else "db",
    }


@app.get("/schools")
async def get_schools():
    if use_json():
        schools = [
            {
                "school_id": int(s["id"]),
                "name_2gis": s.get("name_2gis"),
                "name_ym": s.get("short_name"),
                "school_address": s.get("address"),
            }
            for s in load_schools_raw()
            if s.get("id") is not None
        ]
        schools.sort(key=lambda x: x["school_id"])
        return {"schools": schools}

    conn = None
    try:
        import psycopg2

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT school_id, name_2gis, name_ym, school_address FROM sa.school ORDER BY school_id"
        )
        rows = cursor.fetchall()
        schools = [
            {
                "school_id": row[0],
                "name_2gis": row[1],
                "name_ym": row[2],
                "school_address": row[3],
            }
            for row in rows
        ]
        cursor.close()
        return {"schools": schools}
    except Exception as e:
        if "psycopg2" in type(e).__module__:
            raise HTTPException(status_code=500, detail=f"Ошибка БД: {str(e)}") from e
        raise
    finally:
        if conn:
            conn.close()


@app.get("/api/schools/map")
async def get_schools_for_map(
    search: Optional[str] = Query(None),
    year_min: Optional[int] = Query(None, ge=1800, le=2100),
    year_max: Optional[int] = Query(None, ge=1800, le=2100),
    rating_min: Optional[float] = Query(None, ge=1.0, le=5.0),
    rating_max: Optional[float] = Query(None, ge=1.0, le=5.0),
    has_pool: Optional[bool] = Query(None),
    has_stadium: Optional[bool] = Query(None),
    has_sports_ground: Optional[bool] = Query(None),
    has_sports_complex: Optional[bool] = Query(None),
    pref_olympiads: bool = Query(False),
    pref_bullying: bool = Query(False),
    pref_staff: bool = Query(False),
    pref_building: bool = Query(False),
    pref_exam: bool = Query(False),
    pref_location: bool = Query(False),
    user_lat: Optional[float] = Query(None, ge=-90, le=90),
    user_lon: Optional[float] = Query(None, ge=-180, le=180),
):
    if year_min is not None and year_max is not None and year_min > year_max:
        raise HTTPException(
            status_code=400,
            detail="Год постройки: начальное значение не может быть больше конечного",
        )
    if rating_min is not None and rating_max is not None and rating_min > rating_max:
        raise HTTPException(
            status_code=400,
            detail="Рейтинг: минимальное значение не может быть больше максимального",
        )

    if use_json():
        try:
            schools = filter_schools_for_map(
                search=search,
                year_min=year_min,
                year_max=year_max,
                rating_min=rating_min,
                rating_max=rating_max,
                has_pool=has_pool,
                has_stadium=has_stadium,
                has_sports_ground=has_sports_ground,
                has_sports_complex=has_sports_complex,
            )
        except FileNotFoundError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

        schools = apply_preference_scores(
            schools,
            pref_olympiads=pref_olympiads,
            pref_bullying=pref_bullying,
            pref_staff=pref_staff,
            pref_building=pref_building,
            pref_exam=pref_exam,
            pref_location=pref_location,
            user_lat=user_lat,
            user_lon=user_lon,
        )
        return {"schools": schools, "count": len(schools), "data_source": "json"}

    # --- PostgreSQL ---
    import psycopg2

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT
                s.school_id, s.name_2gis, s.name_ym, s.school_address, s.year_built,
                s.has_sports_complex, s.has_pool, s.has_stadium, s.has_sports_ground,
                ST_X(s.location::geometry) AS lon, ST_Y(s.location::geometry) AS lat,
                r.rating_yandex, s.rating_total, s.ege_average_score,
                s.olympiad_winners_count
            FROM sa.school s
            LEFT JOIN sa.rating r ON r.school_id = s.school_id
            WHERE 1=1
        """
        params: list[Any] = []
        if year_min is not None:
            query += " AND s.year_built >= %s"
            params.append(year_min)
        if year_max is not None:
            query += " AND s.year_built <= %s"
            params.append(year_max)
        if rating_min is not None:
            query += " AND r.rating_yandex >= %s"
            params.append(rating_min)
        if rating_max is not None:
            query += " AND r.rating_yandex <= %s"
            params.append(rating_max)
        if has_pool is not None:
            query += " AND s.has_pool = %s"
            params.append(has_pool)
        if has_stadium is not None:
            query += " AND s.has_stadium = %s"
            params.append(has_stadium)
        if has_sports_ground is not None:
            query += " AND s.has_sports_ground = %s"
            params.append(has_sports_ground)
        if has_sports_complex is not None:
            query += " AND s.has_sports_complex = %s"
            params.append(has_sports_complex)
        if search and search.strip():
            search_term = f"%{search.strip()}%"
            query += " AND (s.name_2gis ILIKE %s OR s.name_ym ILIKE %s OR s.school_address ILIKE %s)"
            params.extend([search_term, search_term, search_term])
        query += " ORDER BY s.school_id"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        schools = []
        for row in rows:
            lon, lat = row[9], row[10]
            rating = row[11]
            schools.append(
                {
                    "school_id": row[0],
                    "name_2gis": row[1],
                    "name_ym": row[2],
                    "school_address": row[3],
                    "year_built": row[4],
                    "has_sports_complex": row[5],
                    "has_pool": row[6],
                    "has_stadium": row[7],
                    "has_sports_ground": row[8],
                    "location": {
                        "type": "Point",
                        "coordinates": (
                            [float(lon), float(lat)]
                            if lon is not None and lat is not None
                            else None
                        ),
                    },
                    "rating_yandex": float(rating) if rating is not None else None,
                    "rating_total": float(row[12]) if row[12] is not None else None,
                    "ege_average_score": float(row[13]) if row[13] is not None else None,
                    "olympiad_winners_count": row[14],
                }
            )
        cursor.close()

        bundle = load_preference_bundle()
        # Наличие анализа отзывов определяем по analyz-файлам (тот же критерий,
        # что и в json-режиме), а не по bundle.final_review_school_ids — папка
        # rd_3_stage, на которую ссылается preference_scoring, не используется.
        analyz_ids = review_analysis_school_ids()
        for sch in schools:
            sch["has_review_analysis"] = sch["school_id"] in analyz_ids

        schools = apply_preference_scores(
            schools,
            pref_olympiads=pref_olympiads,
            pref_bullying=pref_bullying,
            pref_staff=pref_staff,
            pref_building=pref_building,
            pref_exam=pref_exam,
            pref_location=pref_location,
            user_lat=user_lat,
            user_lon=user_lon,
        )
        return {"schools": schools, "count": len(schools), "data_source": "db"}
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Ошибка БД: {str(e)}") from e
    finally:
        if conn:
            conn.close()


@app.get("/api/schools/{school_id}")
async def get_school_by_id(school_id: int):
    if use_json():
        raw = get_school_raw(school_id)
        if raw is None:
            raise HTTPException(status_code=404, detail="Школа не найдена")
        return school_to_detail(raw)

    import psycopg2

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                s.school_id, s.name_2gis, s.name_ym, s.school_address, s.building_type,
                s.floors, s.year_built, s.reconstruction_year,
                s.has_sports_complex, s.has_pool, s.has_stadium, s.has_sports_ground,
                ST_X(s.location::geometry) AS lon, ST_Y(s.location::geometry) AS lat,
                l.link_2gis, l.link_yandex, l.link_gosuslugi,
                r.rating_yandex, r.rating_2gis,
                s.city, s.rating_total, s.ege_average_score, s.ege_year,
                s.university_admission_percent, s.university_admission_year,
                s.olympiad_winners_count, s.top_tags, s.administrative_district,
                s.rating_ege, s.rating_olympiads, s.rating_teachers, s.rating_mto,
                s.rating_psychological_climate, s.rating_sports_infrastructure,
                s.rating_profiles,
                s.capacity, s.building_info->>'area_sqm' AS area_sqm, s.material
            FROM sa.school s
            LEFT JOIN sa.link l ON l.school_id = s.school_id
            LEFT JOIN sa.rating r ON r.school_id = s.school_id
            WHERE s.school_id = %s
            """,
            (school_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        if not row:
            raise HTTPException(status_code=404, detail="Школа не найдена")
        lon, lat = row[12], row[13]
        top_tags = row[26]
        if isinstance(top_tags, str) and top_tags.strip():
            try:
                top_tags = json_lib.loads(top_tags)
            except (json_lib.JSONDecodeError, TypeError):
                top_tags = []
        if not isinstance(top_tags, list):
            top_tags = []

        def _num(v):
            return float(v) if v is not None else None

        return {
            "school_id": row[0],
            "name_2gis": row[1],
            "name_ym": row[2],
            "school_address": row[3],
            "building_type": row[4],
            "floors": row[5],
            "year_built": row[6],
            "reconstruction_year": row[7],
            "has_sports_complex": row[8],
            "has_pool": row[9],
            "has_stadium": row[10],
            "has_sports_ground": row[11],
            "location": {
                "type": "Point",
                "coordinates": (
                    [float(lon), float(lat)] if lon is not None and lat is not None else None
                ),
            },
            "link_2gis": row[14],
            "link_yandex": row[15],
            "link_gosuslugi": row[16],
            "rating_yandex": _num(row[17]),
            "rating_2gis": _num(row[18]),
            "has_review_analysis": school_id in review_analysis_school_ids(),
            "city": row[19],
            "rating_total": _num(row[20]),
            "ege_average_score": _num(row[21]),
            "ege_year": row[22],
            "university_admission_percent": _num(row[23]),
            "university_admission_year": row[24],
            "olympiad_winners_count": row[25],
            "top_tags": top_tags,
            "administrative_district": row[27],
            "rating_ege": _num(row[28]),
            "rating_olympiads": _num(row[29]),
            "rating_teachers": _num(row[30]),
            "rating_mto": _num(row[31]),
            "rating_psychological_climate": _num(row[32]),
            "rating_sports_infrastructure": _num(row[33]),
            "rating_profiles": _num(row[34]),
            "capacity": row[35],
            "area_sqm": _num(row[36]),
            "wall_material": row[37],
        }
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Ошибка БД: {str(e)}") from e
    finally:
        if conn:
            conn.close()


@app.get("/api/schools/{school_id}/reviews/topics")
async def get_school_reviews_topics(school_id: int):
    if use_json():
        return {"reviews": load_reviews_topics(school_id), "data_source": "json"}

    import psycopg2

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT review_date, topics
            FROM sa.review
            WHERE school_id = %s AND review_date IS NOT NULL
            ORDER BY review_date
            """,
            (school_id,),
        )
        rows = cursor.fetchall()
        reviews = []
        for row in rows:
            topics = None
            if row[1] is not None:
                if isinstance(row[1], str) and row[1].strip():
                    try:
                        topics = json_lib.loads(row[1])
                    except (json_lib.JSONDecodeError, TypeError):
                        topics = {}
                else:
                    topics = row[1] if isinstance(row[1], dict) else {}
            reviews.append(
                {
                    "review_date": row[0].isoformat()
                    if hasattr(row[0], "isoformat")
                    else str(row[0]),
                    "topics": topics or {},
                }
            )
        cursor.close()
        return {"reviews": reviews, "data_source": "db"}
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Ошибка БД: {str(e)}") from e
    finally:
        if conn:
            conn.close()


@app.get("/schools/{school_id}/reviews")
async def get_school_reviews(
    school_id: int,
    date_start: Optional[date] = Query(None),
    date_end: Optional[date] = Query(None),
):
    """Совместимость: в json-режиме отдаём topics+date из analyz-файлов."""
    if use_json():
        reviews = load_reviews_topics(school_id)
        if date_start is not None:
            reviews = [r for r in reviews if r["review_date"] >= date_start.isoformat()]
        if date_end is not None:
            reviews = [r for r in reviews if r["review_date"] <= date_end.isoformat()]
        return {"reviews": reviews, "data_source": "json"}

    raise HTTPException(
        status_code=501,
        detail="Эндпоинт /schools/{id}/reviews в режиме БД пока не переведён; используйте DATA_SOURCE=json",
    )


@app.get("/api/institutions")
async def get_institutions(
    kind: Optional[str] = Query(None),
    city: str = Query("Саратов"),
):
    """Слои учреждений вне школьного рейтинга (спорт/творческие/садики/вузы/СПО/интернаты)."""
    if use_json():
        raise HTTPException(status_code=501, detail="Слои учреждений доступны только в db-режиме")
    import psycopg2

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        sql = """
            SELECT institution_id, code_oo, kind, name, address, phone, site,
                   latitude, longitude, geocode_status
            FROM sa.institution
            WHERE city = %s AND latitude IS NOT NULL
        """
        params: list[Any] = [city]
        if kind:
            sql += " AND kind = %s"
            params.append(kind)
        cur.execute(sql + " ORDER BY kind, name", params)
        rows = cur.fetchall()
        items = [
            {
                "institution_id": r[0],
                "code_oo": r[1],
                "kind": r[2],
                "name": r[3],
                "address": r[4],
                "phone": r[5],
                "site": r[6],
                "location": {
                    "type": "Point",
                    "coordinates": [float(r[8]), float(r[7])]
                    if r[7] is not None and r[8] is not None
                    else None,
                },
            }
            for r in rows
        ]
        cur.close()
        return {"institutions": items, "count": len(items)}
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Ошибка БД: {str(e)}") from e
    finally:
        if conn:
            conn.close()


@app.get("/api/schools/{school_id}/catchment")
async def get_school_catchment(school_id: int):
    """Прикреплённые адреса школы (дома с координатами) для отрисовки зоны на карте."""
    if use_json():
        raise HTTPException(status_code=501, detail="Catchment доступен только в db-режиме")
    import psycopg2

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT a.address_id, a.district, a.street_norm, a.house_norm,
                   a.resolved, a.latitude, a.longitude
            FROM sa.school_address sa
            JOIN sa.address a ON a.address_id = sa.address_id
            WHERE sa.school_id = %s AND a.geocode_status = 'ok'
            ORDER BY a.street_norm, a.house_norm
            """,
            (school_id,),
        )
        rows = cur.fetchall()
        cur.close()
        points = [
            {
                "address_id": r[0],
                "district": r[1],
                "street": r[2],
                "house": r[3],
                "address": r[4] or f"{r[2]}, {r[3]}",
                "lat": float(r[5]),
                "lon": float(r[6]),
            }
            for r in rows
        ]
        return {"school_id": school_id, "points": points, "count": len(points)}
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Ошибка БД: {str(e)}") from e
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
