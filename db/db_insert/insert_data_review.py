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
    Все поля могут быть null, пустые строки преобразуются в None
    """
    import json as json_lib
    
    # Вспомогательная функция для преобразования пустых строк в None
    def to_none_if_empty(value):
        if value is None or (isinstance(value, str) and value.strip() == ''):
            return None
        return value
    
    # Преобразуем school_id в integer (может быть null)
    school_id = review.get('school_id')
    if school_id:
        try:
            school_id = int(school_id) if isinstance(school_id, str) else school_id
        except (ValueError, TypeError):
            school_id = None
    else:
        school_id = None
    
    # Преобразуем date (может быть null или пустая строка)
    review_date = to_none_if_empty(review.get('date'))
    
    # Преобразуем text (может быть null или пустая строка)
    review_text = to_none_if_empty(review.get('text'))
    
    # Преобразуем topics в JSON строку
    # Сохраняем даже пустой объект {}, так как это флаг отсутствия отзывов
    topics = review.get('topics', {})
    if topics is not None and topics != {}:
        review_topics = json_lib.dumps(topics, ensure_ascii=False)
    elif topics == {}:
        # Пустой объект сохраняем как "{}"
        review_topics = "{}"
    else:
        review_topics = None
    
    # Преобразуем overall (может быть null или пустая строка)
    review_overall = to_none_if_empty(review.get('overall'))
    
    # Преобразуем числовые поля (могут быть null)
    likes_count = review.get('likes_count')
    dislikes_count = review.get('dislikes_count')
    rating = review.get('rating')
    
    # Преобразуем в None, если значения пустые или невалидные
    likes_count = None if likes_count is None else (int(likes_count) if likes_count != '' else None)
    dislikes_count = None if dislikes_count is None else (int(dislikes_count) if dislikes_count != '' else None)
    rating = None if rating is None else (int(rating) if rating != '' else None)
    
    return (
        school_id,                    # school_id INTEGER
        review_date,                  # review_date DATE (может быть None)
        review_text,                  # review_text TEXT (может быть None)
        review_topics,                # review_topics TEXT (JSON, может быть None или "{}")
        review_overall,               # review_overall TEXT (может быть None)
        likes_count,                  # review_likes INTEGER (может быть None)
        dislikes_count,              # review_dislikes INTEGER (может быть None)
        rating                        # review_rating INTEGER (может быть None)
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
                    review_date,
                    review_text,
                    review_topics,
                    review_overall,
                    review_likes,
                    review_dislikes,
                    review_rating
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
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

