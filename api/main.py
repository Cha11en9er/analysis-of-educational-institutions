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
        
        # Вызываем функцию из БД
        cursor.execute("SELECT * FROM ca.get_schools()")
        rows = cursor.fetchall()
        
        # Получаем названия колонок
        columns = [desc[0] for desc in cursor.description]
        
        # Формируем результат
        schools = []
        for row in rows:
            school = dict(zip(columns, row))
            schools.append(school)
        
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
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Если даты не указаны, используем значения по умолчанию
        if date_start is None:
            date_start = date(2000, 1, 1)  # Очень старая дата
        if date_end is None:
            date_end = date(2100, 12, 31)  # Очень будущая дата
        
        # Вызываем функцию из БД
        cursor.execute(
            "SELECT ca.get_school_reviews_json(%s, %s, %s)",
            (school_id, date_start, date_end)
        )
        result = cursor.fetchone()[0]
        
        cursor.close()
        
        # Если результат None (нет отзывов), возвращаем пустой массив
        if result is None:
            return {"reviews": []}
        
        return {"reviews": result}
        
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Ошибка БД: {str(e)}")
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

