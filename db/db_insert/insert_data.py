#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для заполнения таблицы базы данных PostgreSQL данными из JSON файла.
"""

import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_batch
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
DATA_FILE = os.getenv('DATA_FILE', 'db/db_data/input/db_input_test_data.json')


def get_connection():
    """Создаёт и возвращает подключение к базе данных"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print(f"[OK] Подключение к БД установлено: {DB_CONFIG['database']}")
        return conn
    except psycopg2.Error as e:
        print(f"[ERROR] Ошибка подключения к БД: {e}")
        raise


def load_json_data(file_path: str) -> Dict[str, Any]:
    """Загружает данные из JSON файла"""
    try:
        # Если путь относительный, делаем его абсолютным относительно корня проекта
        if not os.path.isabs(file_path):
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            file_path = os.path.join(project_root, file_path)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"[OK] Данные загружены из файла: {file_path}")
        return data
    except FileNotFoundError:
        print(f"[ERROR] Файл не найден: {file_path}")
        raise
    except json.JSONDecodeError as e:
        print(f"[ERROR] Ошибка парсинга JSON: {e}")
        raise


def prepare_review_data(review: Dict[str, Any]) -> tuple:
    """
    Подготавливает данные отзыва для вставки в таблицу ca.review
    """
    return (
        # school_id FK
        review.get('school_id', ''),
        # date (строка вида "11 декабря 2020")
        review.get('date', ''),
        # orig_text
        review.get('text', ''),
        # rec_text
        review.get('main_idea', ''),
        # tonality
        review.get('sentiment', '')
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
                    school_id,
                    date,
                    orig_text,
                    rec_text,
                    tonality
                ) VALUES (%s, %s, %s, %s, %s)
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


def get_table_count(conn, schema_name: str, table_name: str) -> int:
    """Возвращает количество записей в таблице"""
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                    sql.Identifier(schema_name),
                    sql.Identifier(table_name)
                )
            )
            count = cursor.fetchone()[0]
            return count
    except psycopg2.Error as e:
        print(f"[WARN] Не удалось получить количество записей: {e}")
        return 0


def main(data_file: str = None):
    """
    Основная функция для вставки данных в БД
    
    Args:
        data_file: Путь к JSON файлу с данными (если None, используется DATA_FILE)
    """
    conn = None
    try:
        # Определяем файл с данными
        file_path = data_file or DATA_FILE
        
        print("[INFO] Начало вставки данных в базу данных")
        print(f"[INFO] Схема: {DB_SCHEMA}")
        print(f"[INFO] Таблица: {DB_TABLE}")
        print(f"[INFO] Файл с данными: {file_path}")
        print()
        
        # Загружаем данные из JSON
        data = load_json_data(file_path)
        
        # Извлекаем метаданные и отзывы
        resource = data.get('resource', '')
        parse_date = data.get('parse_date', '')
        reviews = data.get('reviews', [])
        
        if not reviews:
            print("[WARN] Нет отзывов для вставки")
            return
        
        print(f"[INFO] Найдено отзывов: {len(reviews)}")
        print(f"[INFO] Источник: {resource}")
        print(f"[INFO] Дата парсинга: {parse_date}")
        print()
        
        # Подключаемся к БД
        conn = get_connection()
        
        # Получаем текущее количество записей
        count_before = get_table_count(conn, DB_SCHEMA, DB_TABLE)
        print(f"[INFO] Записей в таблице до вставки: {count_before}")
        
        # Вставляем данные
        insert_reviews(conn, DB_SCHEMA, DB_TABLE, reviews)
        
        # Получаем новое количество записей
        count_after = get_table_count(conn, DB_SCHEMA, DB_TABLE)
        print(f"[INFO] Записей в таблице после вставки: {count_after}")
        print(f"[INFO] Добавлено записей: {count_after - count_before}")
        
        print()
        print("[OK] Данные успешно вставлены в базу данных!")
        
    except Exception as e:
        print(f"[ERROR] Критическая ошибка: {e}")
        raise
    finally:
        if conn:
            conn.close()
            print("[INFO] Подключение к БД закрыто")


if __name__ == "__main__":
    import sys
    
    # Парсим аргументы командной строки
    data_file = None
    if len(sys.argv) > 1:
        data_file = sys.argv[1]
    
    main(data_file=data_file)

