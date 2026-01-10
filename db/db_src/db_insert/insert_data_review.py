#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для заполнения таблицы базы данных PostgreSQL данными из JSON файла.
"""

import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_batch, Json
import json
import os
from dotenv import load_dotenv
from typing import List, Dict, Any

# Загрузка переменных окружения
load_dotenv()

# Параметры подключения к БД
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD')
}

# Названия схемы и таблицы
DB_SCHEMA = 'ca'
DB_TABLE = 'review'

# Путь к JSON файлу с данными
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
PROJECT_ROOT = os.path.dirname(DB_ROOT)
DATA_FILE = os.path.join(PROJECT_ROOT, "recognize_meaning", "rm_data", "rm_output", "rm_output_data.json")


def get_connection():
    """Создаёт и возвращает подключение к базе данных"""
    conn = psycopg2.connect(**DB_CONFIG)
    return conn


def load_json_data(file_path: str) -> Dict[str, Any]:
    """Загружает данные из JSON файла"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data


def prepare_review_data(review: Dict[str, Any]) -> tuple:
    """
    Подготавливает данные отзыва для вставки в таблицу ca.review.
    Обрабатывает случай, когда у школы нет отзывов (date и text равны null).
    """
    # Обрабатываем date: если null в JSON или пустая строка, передаём None в БД
    date_value = review.get('date')
    if date_value is None or (isinstance(date_value, str) and date_value.strip() == ''):
        date_value = None
    
    # Обрабатываем text: если null в JSON или пустая строка, передаём None в БД
    text_value = review.get('text')
    if text_value is None or (isinstance(text_value, str) and text_value.strip() == ''):
        text_value = None
    
    # Обрабатываем topics: если пустой словарь или отсутствует, используем пустой JSONB
    topics_value = review.get('topics', {})
    if not topics_value or topics_value is None:
        topics_value = {}
    
    # Обрабатываем overall: по умолчанию 'pos' если отсутствует или пустое
    overall_value = review.get('overall', 'pos')
    if overall_value is None or (isinstance(overall_value, str) and overall_value.strip() == ''):
        overall_value = 'pos'
    
    return (
        review.get('review_id', ''),
        review.get('school_id', ''),
        date_value,  # Может быть None
        text_value,  # Может быть None
        Json(topics_value),  # Преобразуем словарь в JSONB
        overall_value  # По умолчанию 'pos' если отсутствует
    )


def insert_reviews(conn, schema_name: str, table_name: str, reviews: List[Dict[str, Any]],
                   batch_size: int = 100):
    """
    Вставляет отзывы в таблицу базы данных
    
    Args:
        conn: Подключение к БД
        schema_name: Название схемы
        table_name: Название таблицы
        reviews: Список отзывов для вставки
        batch_size: Размер батча для batch insert
    """
    try:
        with conn.cursor() as cursor:
            # SQL запрос для вставки данных в таблицу ca.review
            insert_query = sql.SQL("""
                INSERT INTO {}.{} (
                    review_id,
                    school_id,
                    date,
                    text,
                    topics,
                    overall
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """).format(
                sql.Identifier(schema_name),
                sql.Identifier(table_name)
            )
            
            # Подготавливаем данные для вставки
            data_to_insert = [prepare_review_data(review) for review in reviews]
            
            # Выполняем batch insert
            execute_batch(cursor, insert_query, data_to_insert, page_size=batch_size)
            
            conn.commit()
            print(f"[OK] Вставлено отзывов: {len(reviews)}")
            
    except psycopg2.Error as e:
        conn.rollback()
        print(f"[ERROR] Ошибка при вставке данных: {e}")
        raise


def main(data_file: str = None):
    """
    Основная функция для вставки данных в БД
    
    Args:
        data_file: Путь к JSON файлу с данными (если None, используется DATA_FILE)
    """
    conn = None
    try:
        file_path = data_file or DATA_FILE
        data = load_json_data(file_path)
        reviews = data.get('reviews', [])
        
        if not reviews:
            return
        
        conn = get_connection()
        insert_reviews(conn, DB_SCHEMA, DB_TABLE, reviews)
        
    except Exception as e:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    import sys
    
    data_file = None
    if len(sys.argv) > 1:
        data_file = sys.argv[1]
    
    main(data_file=data_file)

