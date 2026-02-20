#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт вставки данных о школах в новую схему БД `sa`.

Берём данные из:
    `school_data/sd_2_stage/sd_2_stage_schools.json`

И заполняем таблицу:
    sa.school
"""

import json
import os
from typing import Any, Dict, List, Tuple, Optional

import psycopg2
from psycopg2.extras import execute_batch, Json

from db_config_sa import get_connection

# Пути к файлам
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
PROJECT_ROOT = os.path.dirname(DB_ROOT)

SCHOOLS_JSON_PATH = os.path.join(
    PROJECT_ROOT,
    "school_data",
    "sd_2_stage",
    "sd_2_stage_schools.json",
)


def load_schools(path: str) -> List[Dict[str, Any]]:
    """
    Загружаем список школ из JSON.

    Формат элемента (пример):
        {
            "id": 1,
            "name_2gis": "...",
            "short_name": "...",
            "address": "...",
            "building_type": "...",
            "area_sqm": 1139.8,
            "floors": 2,
            "underground_floors": null,
            "material": "смеш",
            "year_built": 1980,
            "reconstruction_year": null,
            "capacity": null,
            "has_sports_complex": null,
            "has_pool": null,
            "has_stadium": null,
            "has_sports_ground": 1,
            "latitude": 51.509919,
            "longitude": 45.987625,
            "cadastral_number": "64:48:000000:15467",
            "rating_2gis": null,
            "rating_yandex": 4.7,
            "link_yandex": "...",
            "reviews_link_yandex": "...",
            "link_2gis": null,
            "reviews_link_2gis": null,
            "location": {
                "type": "Point",
                "coordinates": [45.987625, 51.509919]
            }
        }
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def bool_from_int_or_none(value: Any) -> Optional[bool]:
    """
    Преобразуем значения 0/1/None (и строки '0'/'1') в bool/None.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    try:
        iv = int(value)
    except (TypeError, ValueError):
        return None
    if iv == 1:
        return True
    if iv == 0:
        return False
    return None


def prepare_school_row(s: Dict[str, Any]) -> Tuple:
    """
    Готовим кортеж значений для вставки в sa.school.

    sa.school (
        school_id INTEGER PRIMARY KEY,
        name_2gis TEXT,
        name_ym TEXT,
        school_address TEXT NOT NULL,
        building_type TEXT,
        floors INTEGER NOT NULL,
        floor_under INTEGER,
        material TEXT,
        reconstruction_year INTEGER,
        year_built INTEGER NOT NULL,
        capacity INTEGER,
        building_info JSONB NOT NULL,  -- area_sqm, cadastral_number
        has_sports_complex BOOLEAN,
        has_pool BOOLEAN,
        has_stadium BOOLEAN,
        has_sports_ground BOOLEAN,
        location GEOGRAPHY(Point, 4326) NOT NULL
    )
    """
    school_id = s.get("id")

    name_2gis = s.get("name_2gis")

    # В схеме есть поле name_ym (название на Яндекс.Картах).
    # В JSON его нет, поэтому можно:
    #  - либо оставить NULL,
    #  - либо использовать short_name как приближённый вариант.
    # Здесь оставляем NULL, чтобы не подменять семантику.
    name_ym = s.get("short_name")

    address = s.get("address")
    building_type = s.get("building_type")

    floors = s.get("floors")
    floor_under = s.get("underground_floors")
    material = s.get("material")
    reconstruction_year = s.get("reconstruction_year")
    year_built = s.get("year_built")
    capacity = s.get("capacity")

    # building_info — JSONB с дополнительной информацией по зданию.
    building_info = {
        "area_sqm": s.get("area_sqm"),
        "cadastral_number": s.get("cadastral_number"),
    }

    has_sports_complex = bool_from_int_or_none(s.get("has_sports_complex"))
    has_pool = bool_from_int_or_none(s.get("has_pool"))
    has_stadium = bool_from_int_or_none(s.get("has_stadium"))
    has_sports_ground = bool_from_int_or_none(s.get("has_sports_ground"))

    # Координаты: в JSON есть и latitude/longitude, и GeoJSON location.
    # Для надёжности берём сначала location.coordinates, если нет — latitude/longitude.
    lon = None
    lat = None

    loc = s.get("location")
    if isinstance(loc, dict):
        coords = loc.get("coordinates")
        if (
            isinstance(coords, list)
            and len(coords) == 2
            and isinstance(coords[0], (int, float))
            and isinstance(coords[1], (int, float))
        ):
            lon, lat = coords[0], coords[1]

    if lon is None or lat is None:
        lon = s.get("longitude")
        lat = s.get("latitude")

    if lon is None or lat is None:
        raise ValueError(f"Нет координат для школы id={school_id}")

    return (
        school_id,
        name_2gis,
        name_ym,
        address,
        building_type,
        floors,
        floor_under,
        material,
        reconstruction_year,
        year_built,
        capacity,
        Json(building_info),
        has_sports_complex,
        has_pool,
        has_stadium,
        has_sports_ground,
        lon,
        lat,
    )


def insert_schools(schools: List[Dict[str, Any]], batch_size: int = 500) -> None:
    """
    Вставляем школы в таблицу sa.school.

    Для поля location используем PostGIS-функции:
        ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography
    """
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            insert_sql = """
                INSERT INTO sa.school (
                    school_id,
                    name_2gis,
                    name_ym,
                    school_address,
                    building_type,
                    floors,
                    floor_under,
                    material,
                    reconstruction_year,
                    year_built,
                    capacity,
                    building_info,
                    has_sports_complex,
                    has_pool,
                    has_stadium,
                    has_sports_ground,
                    location
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                )
                ON CONFLICT (school_id) DO UPDATE SET
                    name_2gis = EXCLUDED.name_2gis,
                    name_ym = EXCLUDED.name_ym,
                    school_address = EXCLUDED.school_address,
                    building_type = EXCLUDED.building_type,
                    floors = EXCLUDED.floors,
                    floor_under = EXCLUDED.floor_under,
                    material = EXCLUDED.material,
                    reconstruction_year = EXCLUDED.reconstruction_year,
                    year_built = EXCLUDED.year_built,
                    capacity = EXCLUDED.capacity,
                    building_info = EXCLUDED.building_info,
                    has_sports_complex = EXCLUDED.has_sports_complex,
                    has_pool = EXCLUDED.has_pool,
                    has_stadium = EXCLUDED.has_stadium,
                    has_sports_ground = EXCLUDED.has_sports_ground,
                    location = EXCLUDED.location,
                    updated_at = CURRENT_TIMESTAMP;
            """

            data = [prepare_school_row(s) for s in schools]
            execute_batch(cur, insert_sql, data, page_size=batch_size)

        conn.commit()
        print(f"[OK] Вставлено/обновлено школ: {len(schools)}")
    except Exception as e:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def main():
    """
    Точка входа:
    1. Читаем JSON с полным списком школ.
    2. Готовим данные под схему sa.school.
    3. Вставляем батчами с UPSERT (ON CONFLICT ... DO UPDATE).
    """
    schools = load_schools(SCHOOLS_JSON_PATH)
    if not schools:
        print("[WARN] В JSON со школами нет данных")
        return

    insert_schools(schools)


if __name__ == "__main__":
    main()
