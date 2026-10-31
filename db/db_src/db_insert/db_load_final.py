#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Единый загрузчик БД `sa` из актуальных данных (заменяет db_insert_data_school.py
и db_insert_data_review.py, которые читали устаревшие источники).

Источники:
  - school_data/final_school_data.json                        -> sa.school + sa.rating + sa.link
  - review_data/rd_2_stage/rd_separately/
        school_reviews_separately_{id}.json                   -> тело отзыва (текст/дата/лайки)
  - review_data/rd_2_stage_analys/rd_separately_analyzed/
        school_reviews_separately_{id}_analyz.json            -> topics/overall по review_id

Запуск из корня репозитория (на сервере — в venv):
  python db/db_src/db_insert/db_load_final.py [--truncate]

Идемпотентен: с --truncate пересоздаёт содержимое таблиц с нуля.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from psycopg2.extras import Json, execute_batch

from db_config_sa import get_connection

SCRIPT_DIR = Path(__file__).resolve().parent
DB_ROOT = SCRIPT_DIR.parent.parent
PROJECT_ROOT = DB_ROOT.parent

FINAL_SCHOOLS_JSON = PROJECT_ROOT / "school_data" / "final_school_data.json"
REVIEWS_SEP_DIR = PROJECT_ROOT / "review_data" / "rd_2_stage" / "rd_separately"
REVIEWS_ANALYZ_DIR = (
    PROJECT_ROOT / "review_data" / "rd_2_stage_analys" / "rd_separately_analyzed"
)
SEP_PATTERN = re.compile(r"school_reviews_separately_(\d+)\.json$")
ANALYZ_PATTERN = re.compile(r"school_reviews_separately_(\d+)_analyz\.json$")

# Дубликаты зданий (см. school_data/prepare_final_data.py, REVIEW_ALIAS_IDS):
# отзывы id-дубликата относятся к основной школе. school_id отзывов ремапится,
# иначе FK sa.review -> sa.school нарушается (в final_school_data.json их нет).
REVIEW_ALIAS_IDS: dict[int, int] = {
    70: 64,
    23: 167,
    175: 171,
    159: 33,
    124: 155,
    115: 80,
}


def truthy(value: Any) -> bool | None:
    if value is None:
        return None
    return value == 1 or value is True or value == "1"


def load_school_rows() -> tuple[list[tuple], list[tuple], list[tuple]]:
    """Возвращает (школы, рейтинги, ссылки) для батч-вставки."""
    schools: list[tuple] = []
    ratings: list[tuple] = []
    links: list[tuple] = []

    data = json.loads(FINAL_SCHOOLS_JSON.read_text(encoding="utf-8"))
    for raw in data:
        sid = int(raw["id"])
        lat, lon = raw.get("latitude"), raw.get("longitude")
        if lat is None or lon is None:
            print(f"  ! школа {sid} без координат — пропущена", file=sys.stderr)
            continue

        building_info = {
            "area_sqm": raw.get("area_sqm"),
            "cadastral_number": raw.get("cadastral_number"),
            "capacity_source": raw.get("capacity_source"),
            "administrative_district": raw.get("administrative_district"),
            "has_second_shift": raw.get("has_second_shift"),
        }
        schools.append(
            (
                sid,
                raw.get("name_2gis"),
                raw.get("short_name"),
                raw["address"],
                raw.get("building_type"),
                raw.get("floors"),
                raw.get("underground_floors"),
                raw.get("wall_material"),
                raw.get("reconstruction_year"),
                raw.get("year_built"),
                raw.get("capacity_students"),
                Json(building_info),
                truthy(raw.get("fok")),
                truthy(raw.get("pool")),
                truthy(raw.get("stadium")),
                truthy(raw.get("sports_ground")),
                raw.get("city") or "Саратов",
                raw.get("rating_total"),
                raw.get("ege_average_score"),
                raw.get("ege_year"),
                raw.get("university_admission_percent"),
                raw.get("university_admission_year"),
                raw.get("olympiad_winners_count"),
                Json(raw.get("top_tags") or []),
                raw.get("administrative_district"),
                raw.get("rating_ege"),
                raw.get("rating_olympiads"),
                raw.get("rating_teachers"),
                raw.get("rating_mto"),
                raw.get("rating_psychological_climate"),
                raw.get("rating_sports_infrastructure"),
                raw.get("rating_profiles"),
                raw.get("ownership") or "public",
                f"SRID=4326;POINT({float(lon)} {float(lat)})",
            )
        )

        if raw.get("rating_2gis") is not None or raw.get("rating_yandex") is not None:
            ratings.append((sid, raw.get("rating_2gis"), raw.get("rating_yandex")))

        if any(
            raw.get(k)
            for k in (
                "link_yandex",
                "reviews_link_yandex",
                "link_2gis",
                "reviews_link_2gis",
                "link_gosuslugi",
            )
        ):
            links.append(
                (
                    sid,
                    raw.get("link_yandex"),
                    raw.get("reviews_link_yandex"),
                    raw.get("link_2gis"),
                    raw.get("reviews_link_2gis"),
                    raw.get("link_gosuslugi"),
                )
            )
    return schools, ratings, links


def load_review_rows() -> list[tuple]:
    """Мержит сырые отзывы с темами анализа по (school_id, review_id)."""
    schools_all = {
        int(s["id"]) for s in json.loads(FINAL_SCHOOLS_JSON.read_text(encoding="utf-8"))
    }
    rows: list[tuple] = []
    analyz_ids = {
        int(m.group(1))
        for p in REVIEWS_ANALYZ_DIR.glob("school_reviews_separately_*_analyz.json")
        if (m := ANALYZ_PATTERN.match(p.name))
    }

    for sep_path in sorted(REVIEWS_SEP_DIR.glob("school_reviews_separately_*.json")):
        m = SEP_PATTERN.match(sep_path.name)
        if not m:
            continue
        school_id = int(m.group(1))

        topics_by_rid: dict[str, dict] = {}
        overall_by_rid: dict[str, str] = {}
        if school_id in analyz_ids:
            analyz = json.loads(
                (REVIEWS_ANALYZ_DIR / f"school_reviews_separately_{school_id}_analyz.json").read_text(
                    encoding="utf-8-sig"
                )
            )
            items = analyz if isinstance(analyz, list) else analyz.get("reviews", [])
            for item in items:
                if not isinstance(item, dict):
                    continue
                rid = str(item.get("review_id"))
                topics_by_rid[rid] = item.get("topics") or {}
                overall_by_rid[rid] = item.get("overall") or ""

        sep = json.loads(sep_path.read_text(encoding="utf-8-sig"))
        for r in sep:
            rid = str(r.get("review_id"))
            text = (r.get("text") or "").strip() or None
            date = (r.get("date") or "").strip() or None
            if not text and not date:  # CHECK-констрейнт БД
                continue
            if school_id in REVIEW_ALIAS_IDS:
                school_id_mapped = REVIEW_ALIAS_IDS[school_id]
            elif school_id not in schools_all:
                continue  # школы нет в final_school_data.json — отзыв некуда крепить
            else:
                school_id_mapped = school_id
            rating = r.get("rating")
            rating = str(rating).strip() if rating is not None else ""
            likes = r.get("likes_count")
            dislikes = r.get("dislikes_count")
            rows.append(
                (
                    int(rid),
                    school_id_mapped,
                    date,
                    text,
                    int(likes) if likes is not None and str(likes).strip().isdigit() else 0,
                    int(dislikes) if dislikes is not None and str(dislikes).strip().isdigit() else 0,
                    int(rating) if rating.isdigit() and 1 <= int(rating) <= 5 else None,
                    Json(topics_by_rid.get(rid, {})),
                    overall_by_rid.get(rid) or None,
                )
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--truncate", action="store_true", help="Очистить таблицы перед загрузкой")
    args = parser.parse_args()

    schools, ratings, links = load_school_rows()
    reviews = load_review_rows()
    print(f"К загрузке: школ {len(schools)}, рейтингов {len(ratings)}, ссылок {len(links)}, отзывов {len(reviews)}")

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                if args.truncate:
                    cur.execute("TRUNCATE sa.review, sa.rating, sa.link, sa.school CASCADE")
                    print("Таблицы очищены (TRUNCATE)")

                execute_batch(
                    cur,
                    """
                    INSERT INTO sa.school (
                        school_id, name_2gis, name_ym, school_address, building_type,
                        floors, floor_under, material, reconstruction_year, year_built,
                        capacity, building_info,
                        has_sports_complex, has_pool, has_stadium, has_sports_ground,
                        city, rating_total, ege_average_score, ege_year,
                        university_admission_percent, university_admission_year,
                        olympiad_winners_count, top_tags, administrative_district,
                        rating_ege, rating_olympiads, rating_teachers, rating_mto,
                        rating_psychological_climate, rating_sports_infrastructure,
                        rating_profiles, ownership, location
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                              %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                              ST_GeogFromText(%s))
                    ON CONFLICT (school_id) DO UPDATE SET
                        name_2gis=EXCLUDED.name_2gis, name_ym=EXCLUDED.name_ym,
                        school_address=EXCLUDED.school_address, building_type=EXCLUDED.building_type,
                        floors=EXCLUDED.floors, floor_under=EXCLUDED.floor_under,
                        material=EXCLUDED.material, reconstruction_year=EXCLUDED.reconstruction_year,
                        year_built=EXCLUDED.year_built, capacity=EXCLUDED.capacity,
                        building_info=EXCLUDED.building_info,
                        has_sports_complex=EXCLUDED.has_sports_complex, has_pool=EXCLUDED.has_pool,
                        has_stadium=EXCLUDED.has_stadium, has_sports_ground=EXCLUDED.has_sports_ground,
                        city=EXCLUDED.city,
                        rating_total=EXCLUDED.rating_total,
                        ege_average_score=EXCLUDED.ege_average_score, ege_year=EXCLUDED.ege_year,
                        university_admission_percent=EXCLUDED.university_admission_percent,
                        university_admission_year=EXCLUDED.university_admission_year,
                        olympiad_winners_count=EXCLUDED.olympiad_winners_count,
                        top_tags=EXCLUDED.top_tags,
                        administrative_district=EXCLUDED.administrative_district,
                        rating_ege=EXCLUDED.rating_ege, rating_olympiads=EXCLUDED.rating_olympiads,
                        rating_teachers=EXCLUDED.rating_teachers, rating_mto=EXCLUDED.rating_mto,
                        rating_psychological_climate=EXCLUDED.rating_psychological_climate,
                        rating_sports_infrastructure=EXCLUDED.rating_sports_infrastructure,
                        rating_profiles=EXCLUDED.rating_profiles,
                        ownership=EXCLUDED.ownership,
                        location=EXCLUDED.location, updated_at=CURRENT_TIMESTAMP
                    """,
                    schools,
                )
                execute_batch(
                    cur,
                    """
                    INSERT INTO sa.rating (school_id, rating_2gis, rating_yandex)
                    VALUES (%s,%s,%s)
                    ON CONFLICT (school_id) DO UPDATE SET
                        rating_2gis=EXCLUDED.rating_2gis, rating_yandex=EXCLUDED.rating_yandex,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    ratings,
                )
                execute_batch(
                    cur,
                    """
                    INSERT INTO sa.link (
                        school_id, link_yandex, review_link_ym, link_2gis,
                        review_link_2gis, link_gosuslugi
                    ) VALUES (%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (school_id) DO UPDATE SET
                        link_yandex=EXCLUDED.link_yandex, review_link_ym=EXCLUDED.review_link_ym,
                        link_2gis=EXCLUDED.link_2gis, review_link_2gis=EXCLUDED.review_link_2gis,
                        link_gosuslugi=EXCLUDED.link_gosuslugi, updated_at=CURRENT_TIMESTAMP
                    """,
                    links,
                )
                execute_batch(
                    cur,
                    """
                    INSERT INTO sa.review (
                        review_id, school_id, review_date, review_text,
                        likes_count, dislikes_count, review_rating, topics, overall
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (review_id) DO UPDATE SET
                        school_id=EXCLUDED.school_id, review_date=EXCLUDED.review_date,
                        review_text=EXCLUDED.review_text, likes_count=EXCLUDED.likes_count,
                        dislikes_count=EXCLUDED.dislikes_count, review_rating=EXCLUDED.review_rating,
                        topics=EXCLUDED.topics, overall=EXCLUDED.overall,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    reviews,
                )
        print("Загрузка завершена успешно.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
