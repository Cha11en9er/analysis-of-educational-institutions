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
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'education_db'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres')
}

# Названия схемы и таблицы
DB_SCHEMA = os.getenv('DB_SCHEMA', 'education_schema')
DB_TABLE = os.getenv('DB_TABLE', 'reviews_table')
DB_ID = os.getenv('DB_ID', 'review_id')  # Название столбца ID

# Путь к JSON файлу с данными
DATA_FILE = os.getenv('DATA_FILE', 'recognize_meaning/rm_data/rm_output/rm_output_data.json')


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


def prepare_review_data(review: Dict[str, Any], resource: str, parse_date: str) -> tuple:
    """
    Подготавливает данные отзыва для вставки в БД
    
    Args:
        review: Словарь с данными отзыва
        resource: Источник данных (например, 'yandex_maps', '2gis')
        parse_date: Дата парсинга
    
    Returns:
        Кортеж с данными для вставки
    """
    return (
        review.get('school_id', ''),
        review.get('date', ''),
        review.get('text', ''),
        review.get('likes_count', 0) or 0,
        review.get('dislikes_count', 0) or 0,
        review.get('rating'),  # Может быть None
        review.get('main_idea', ''),
        review.get('sentiment', ''),
        resource,
        parse_date
    )


def insert_reviews(conn, schema_name: str, table_name: str, reviews: List[Dict[str, Any]], 
                   resource: str, parse_date: str, batch_size: int = 100):
    """
    Вставляет отзывы в таблицу базы данных
    
    Args:
        conn: Подключение к БД
        schema_name: Название схемы
        table_name: Название таблицы
        reviews: Список отзывов для вставки
        resource: Источник данных
        parse_date: Дата парсинга
        batch_size: Размер батча для batch insert
    """
    try:
        with conn.cursor() as cursor:
            # SQL запрос для вставки данных
            insert_query = sql.SQL("""
                INSERT INTO {}.{} (
                    school_id, date, text, likes_count, dislikes_count, 
                    rating, main_idea, sentiment, resource, parse_date
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """).format(
                sql.Identifier(schema_name),
                sql.Identifier(table_name)
            )
            
            # Подготавливаем данные для вставки
            data_to_insert = [
                prepare_review_data(review, resource, parse_date)
                for review in reviews
            ]
            
            # Выполняем batch insert
            execute_batch(cursor, insert_query, data_to_insert, page_size=batch_size)
            
            conn.commit()
            print(f"[OK] Вставлено отзывов: {len(reviews)}")
            
    except psycopg2.Error as e:
        conn.rollback()
        print(f"[ERROR] Ошибка при вставке данных: {e}")
        raise


def insert_reviews_with_update(conn, schema_name: str, table_name: str, 
                               reviews: List[Dict[str, Any]], resource: str, parse_date: str,
                               batch_size: int = 100):
    """
    Вставляет отзывы с обновлением существующих по уникальному ключу (school_id + text начало)
    Использует UPSERT (INSERT ... ON CONFLICT ... UPDATE)
    
    Args:
        conn: Подключение к БД
        schema_name: Название схемы
        table_name: Название таблицы
        reviews: Список отзывов для вставки
        resource: Источник данных
        parse_date: Дата парсинга
        batch_size: Размер батча для batch insert
    """
    try:
        with conn.cursor() as cursor:
            # SQL запрос для вставки/обновления данных
            # Используем первые 100 символов текста как часть уникального ключа
            insert_query = sql.SQL("""
                INSERT INTO {}.{} (
                    school_id, date, text, likes_count, dislikes_count, 
                    rating, main_idea, sentiment, resource, parse_date, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (school_id, text) 
                DO UPDATE SET
                    date = EXCLUDED.date,
                    likes_count = EXCLUDED.likes_count,
                    dislikes_count = EXCLUDED.dislikes_count,
                    rating = EXCLUDED.rating,
                    main_idea = EXCLUDED.main_idea,
                    sentiment = EXCLUDED.sentiment,
                    resource = EXCLUDED.resource,
                    parse_date = EXCLUDED.parse_date,
                    updated_at = CURRENT_TIMESTAMP
            """).format(
                sql.Identifier(schema_name),
                sql.Identifier(table_name)
            )
            
            # Подготавливаем данные для вставки
            data_to_insert = [
                prepare_review_data(review, resource, parse_date)
                for review in reviews
            ]
            
            # Выполняем batch insert
            execute_batch(cursor, insert_query, data_to_insert, page_size=batch_size)
            
            conn.commit()
            print(f"[OK] Обработано отзывов: {len(reviews)} (вставлено/обновлено)")
            
    except psycopg2.IntegrityError as e:
        # Если нет уникального индекса, используем простую вставку
        print(f"[WARN] Конфликт при вставке (возможно, нет уникального индекса): {e}")
        print("[INFO] Используем простую вставку без обновления")
        insert_reviews(conn, schema_name, table_name, reviews, resource, parse_date, batch_size)
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


def main(data_file: str = None, use_upsert: bool = False):
    """
    Основная функция для вставки данных в БД
    
    Args:
        data_file: Путь к JSON файлу с данными (если None, используется DATA_FILE)
        use_upsert: Если True, использует UPSERT (обновление существующих записей)
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
        if use_upsert:
            insert_reviews_with_update(conn, DB_SCHEMA, DB_TABLE, reviews, resource, parse_date)
        else:
            insert_reviews(conn, DB_SCHEMA, DB_TABLE, reviews, resource, parse_date)
        
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
    use_upsert = False
    
    if len(sys.argv) > 1:
        data_file = sys.argv[1]
    if '--upsert' in sys.argv:
        use_upsert = True
    
    main(data_file=data_file, use_upsert=use_upsert)

