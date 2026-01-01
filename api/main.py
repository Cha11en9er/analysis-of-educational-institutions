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
    return {"message": "Schools API", "version": "1.0.0"}


@app.get("/schools")
async def get_schools():
    """Получить список всех школ"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Прямой запрос к таблице ca.school
        cursor.execute("SELECT school_id, school_name, school_adres FROM ca.school ORDER BY school_id")
        rows = cursor.fetchall()
        
        # Формируем результат
        schools = []
        for row in rows:
            schools.append({
                "school_id": row[0],
                "school_name": row[1],
                "school_adres": row[2]
            })
        
        cursor.close()
        return {"schools": schools}
        
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
        
        # Строим SQL запрос с фильтрацией
        query = """
            SELECT 
                review_id,
                school_id,
                review_date,
                review_text,
                review_topics,
                review_overall,
                review_likes,
                review_dislikes,
                review_rating
            FROM ca.review
            WHERE school_id = %s
        """
        params = [school_id]
        
        # Добавляем фильтрацию по датам, если указаны
        if date_start is not None:
            query += " AND (review_date >= %s OR review_date IS NULL)"
            params.append(date_start)
        
        if date_end is not None:
            query += " AND (review_date <= %s OR review_date IS NULL)"
            params.append(date_end)
        
        # Сортируем: сначала записи с датами (по убыванию), потом без дат
        query += " ORDER BY review_date DESC NULLS LAST, review_id"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Отладочная информация
        print(f"[DEBUG] Загружено отзывов: {len(rows)}")
        if rows:
            print(f"[DEBUG] Пример первой записи: review_id={rows[0][0]}, rating={rows[0][8]}, rating_type={type(rows[0][8])}")
            # Проверяем несколько записей
            for i in range(min(5, len(rows))):
                print(f"[DEBUG] Review {i+1}: id={rows[i][0]}, rating={rows[i][8]}, rating_type={type(rows[i][8])}")
        
        # Формируем результат
        reviews = []
        for row in rows:
            try:
                # Парсим review_topics из JSON строки
                topics = None
                if row[4] is not None:  # review_topics
                    try:
                        if isinstance(row[4], str):
                            # Если это строка, пытаемся распарсить JSON
                            if row[4].strip():  # Не пустая строка
                                topics = json_lib.loads(row[4])
                            else:
                                topics = {}
                        else:
                            topics = row[4]
                    except (json_lib.JSONDecodeError, TypeError) as e:
                        # Если не удалось распарсить, оставляем None
                        topics = None
                elif row[4] is None:
                    # Если поле null, topics остается None
                    topics = None
                
                # Форматируем дату
                review_date_str = None
                if row[2] is not None:  # review_date
                    if hasattr(row[2], 'isoformat'):
                        review_date_str = row[2].isoformat()
                    else:
                        review_date_str = str(row[2])
                
                # Обрабатываем числовые поля
                review_likes = None
                if row[6] is not None:
                    try:
                        review_likes = int(row[6])
                    except (ValueError, TypeError):
                        review_likes = None
                
                review_dislikes = None
                if row[7] is not None:
                    try:
                        review_dislikes = int(row[7])
                    except (ValueError, TypeError):
                        review_dislikes = None
                
                review_rating = None
                if row[8] is not None and row[8] != '':
                    try:
                        review_rating = int(row[8])
                    except (ValueError, TypeError):
                        review_rating = None
                
                review = {
                    "review_id": row[0],
                    "school_id": str(row[1]) if row[1] is not None else None,
                    "date": review_date_str,  # Для совместимости с фронтендом
                    "review_date": review_date_str,
                    "text": row[3] if row[3] is not None else None,  # Для совместимости с фронтендом
                    "review_text": row[3] if row[3] is not None else None,
                    "topics": topics,  # Для совместимости с фронтендом
                    "review_topic": topics,
                    "overall": row[5] if row[5] is not None else None,  # Для совместимости с фронтендом
                    "review_overall": row[5] if row[5] is not None else None,
                    "review_likes": review_likes,
                    "review_dislikes": review_dislikes,
                    "review_rating": review_rating
                }
                # Отладочная информация для первых нескольких отзывов
                if len(reviews) < 3:
                    print(f"[DEBUG] Review {review['review_id']}: rating={review['review_rating']}, type={type(review['review_rating'])}, likes={review['review_likes']}, dislikes={review['review_dislikes']}")
                    print(f"[DEBUG] Review {review['review_id']} full object keys: {list(review.keys())}")
                reviews.append(review)
            except Exception as e:
                # Логируем ошибку, но продолжаем обработку остальных записей
                print(f"[WARN] Ошибка обработки записи review_id={row[0]}: {e}")
                continue
        
        cursor.close()
        
        # Отладочная информация о финальном ответе
        if reviews:
            print(f"[DEBUG] Final response - first review keys: {list(reviews[0].keys())}")
            print(f"[DEBUG] Final response - first review has rating: {'review_rating' in reviews[0]}")
            print(f"[DEBUG] Final response - first review rating value: {reviews[0].get('review_rating')}")
        
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

