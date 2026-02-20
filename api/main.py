#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Простое API на FastAPI для работы с данными школ и отзывов из PostgreSQL.
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from datetime import date
import psycopg2
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

app = FastAPI(title="Schools API", version="1.0.0")

# Настройка CORS для работы с React приложением
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Параметры подключения к БД
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD')
}


def get_db_connection():
    """Создает подключение к базе данных"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Ошибка подключения к БД: {str(e)}")


@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {"message": "Schools API", "version": "1.1.0"}


@app.get("/schools")
async def get_schools():
    """Получить список всех школ из sa.school"""
    conn = None
    try:
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
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Ошибка БД: {str(e)}")
    finally:
        if conn:
            conn.close()


# --- Эндпоинт для страницы карты (sa.school + фильтры) ---

@app.get("/api/schools/map")
async def get_schools_for_map(
    search: Optional[str] = Query(None, description="Строка поиска (передаётся на бэк для будущей реализации)"),
    year_min: Optional[int] = Query(None, ge=1800, le=2100, description="Год постройки от"),
    year_max: Optional[int] = Query(None, ge=1800, le=2100, description="Год постройки до"),
    rating_min: Optional[float] = Query(None, ge=1.0, le=5.0, description="Рейтинг Яндекс от"),
    rating_max: Optional[float] = Query(None, ge=1.0, le=5.0, description="Рейтинг Яндекс до"),
    has_pool: Optional[bool] = Query(None, description="Наличие бассейна"),
    has_stadium: Optional[bool] = Query(None, description="Наличие стадиона/футбольного поля"),
    has_sports_ground: Optional[bool] = Query(None, description="Наличие спорт площадки"),
    has_sports_complex: Optional[bool] = Query(None, description="Наличие спорткомплекса"),
):
    """
    Список школ для карты из sa.school с опциональной фильтрацией.
    Возвращает поля для отображения на карте и в фильтрах, включая location в формате GeoJSON.
    Рейтинг берётся из sa.rating (rating_yandex).
    """
    # Проверка диапазона года
    if year_min is not None and year_max is not None and year_min > year_max:
        raise HTTPException(
            status_code=400,
            detail="Год постройки: начальное значение не может быть больше конечного"
        )
    if rating_min is not None and rating_max is not None and rating_min > rating_max:
        raise HTTPException(
            status_code=400,
            detail="Рейтинг: минимальное значение не может быть больше максимального"
        )

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Базовый запрос: sa.school + рейтинг из sa.rating. Координаты из PostGIS.
        query = """
            SELECT
                s.school_id,
                s.name_2gis,
                s.name_ym,
                s.school_address,
                s.year_built,
                s.has_sports_complex,
                s.has_pool,
                s.has_stadium,
                s.has_sports_ground,
                ST_X(s.location::geometry) AS lon,
                ST_Y(s.location::geometry) AS lat,
                r.rating_yandex
            FROM sa.school s
            LEFT JOIN sa.rating r ON r.school_id = s.school_id
            WHERE 1=1
        """
        params = []

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

        # Поиск: пока просто передаём на бэк; можно добавить ILIKE по name_2gis, name_ym, school_address
        if search and search.strip():
            search_term = f"%{search.strip()}%"
            query += " AND (s.name_2gis ILIKE %s OR s.name_ym ILIKE %s OR s.school_address ILIKE %s)"
            params.extend([search_term, search_term, search_term])

        query += " ORDER BY s.school_id"
        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Порядок колонок: school_id, name_2gis, name_ym, school_address, year_built,
        # has_sports_complex, has_pool, has_stadium, has_sports_ground, lon, lat, rating_yandex (0–11)
        schools = []
        for row in rows:
            lon, lat = row[9], row[10]
            rating = row[11]
            schools.append({
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
                    "coordinates": [float(lon), float(lat)] if lon is not None and lat is not None else None,
                },
                "rating_yandex": float(rating) if rating is not None else None,
            })

        cursor.close()
        return {"schools": schools, "count": len(schools)}
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Ошибка БД: {str(e)}")
    finally:
        if conn:
            conn.close()


@app.get("/schools/{school_id}/reviews")
async def get_school_reviews(
    school_id: int,
    date_start: Optional[date] = Query(None, description="Начальная дата (YYYY-MM-DD)"),
    date_end: Optional[date] = Query(None, description="Конечная дата (YYYY-MM-DD)")
):
    """Получить отзывы по школе с фильтрацией по датам"""
    import json as json_lib
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # sa.review: review_id, school_id, review_date, review_text, likes_count, dislikes_count, review_rating, topics, overall
        query = """
            SELECT
                review_id,
                school_id,
                review_date,
                review_text,
                likes_count,
                dislikes_count,
                review_rating,
                topics,
                overall
            FROM sa.review
            WHERE school_id = %s
        """
        params = [school_id]
        if date_start is not None:
            query += " AND (review_date >= %s OR review_date IS NULL)"
            params.append(date_start)
        if date_end is not None:
            query += " AND (review_date <= %s OR review_date IS NULL)"
            params.append(date_end)
        query += " ORDER BY review_date DESC NULLS LAST, review_id"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        reviews = []
        for row in rows:
            try:
                topics = None
                if row[7] is not None:
                    if isinstance(row[7], str) and row[7].strip():
                        try:
                            topics = json_lib.loads(row[7])
                        except (json_lib.JSONDecodeError, TypeError):
                            topics = None
                    else:
                        topics = row[7]

                review_date_str = None
                if row[2] is not None:
                    review_date_str = row[2].isoformat() if hasattr(row[2], "isoformat") else str(row[2])

                review_rating = None
                if row[6] is not None and row[6] != "":
                    try:
                        review_rating = int(row[6])
                    except (ValueError, TypeError):
                        review_rating = None

                def _int_or_none(val):
                    if val is None:
                        return None
                    try:
                        return int(val)
                    except (ValueError, TypeError):
                        return None

                review = {
                    "review_id": row[0],
                    "school_id": str(row[1]) if row[1] is not None else None,
                    "date": review_date_str,
                    "review_date": review_date_str,
                    "text": row[3] if row[3] is not None else None,
                    "review_text": row[3] if row[3] is not None else None,
                    "topics": topics,
                    "review_topic": topics,
                    "overall": row[8] if row[8] is not None else None,
                    "review_overall": row[8] if row[8] is not None else None,
                    "review_likes": _int_or_none(row[4]),
                    "review_dislikes": _int_or_none(row[5]),
                    "review_rating": review_rating,
                }
                reviews.append(review)
            except Exception as e:
                print(f"[WARN] Ошибка обработки записи review_id={row[0]}: {e}")
                continue

        cursor.close()
        return {"reviews": reviews}
        
    except psycopg2.Error as e:
        import traceback
        error_detail = f"Ошибка БД: {str(e)}"
        print(f"[ERROR] {error_detail}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_detail)
    except Exception as e:
        import traceback
        error_detail = f"Неожиданная ошибка: {str(e)}"
        print(f"[ERROR] {error_detail}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_detail)
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    try:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except ImportError:
        print("Для запуска сервера необходимо установить uvicorn:")
        print("pip install uvicorn[standard]")
        print("\nИли запустите через uvicorn напрямую:")
        print("uvicorn api.main:app --reload")

