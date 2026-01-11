#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для создания объектов базы данных PostgreSQL.
Создаёт схему и таблицу для хранения отзывов об образовательных учреждениях.
"""

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Параметры подключения к БД (из переменных окружения или значения по умолчанию)
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD')
}

#ca - comment analysis

# Названия схемы и таблицы
DB_SCHEMA = 'ca'
DB_TABLE = 'review' 


def get_connection():
    """Создаёт и возвращает подключение к базе данных"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        print(f"[OK] Подключение к БД установлено: {DB_CONFIG['database']}")
        return conn
    except psycopg2.Error as e:
        print(f"[ERROR] Ошибка подключения к БД: {e}")
        raise


def create_schema(conn, schema_name: str):
    """Создаёт схему базы данных, если она не существует"""
    try:
        with conn.cursor() as cursor:
            # Создаём схему, если её нет
            cursor.execute(
                sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                    sql.Identifier(schema_name)
                )
            )
            print(f"[OK] Схема '{schema_name}' создана или уже существует")
    except psycopg2.Error as e:
        print(f"[ERROR] Ошибка при создании схемы: {e}")
        raise


def create_table(conn, schema_name: str, table_name: str):
    """Создаёт таблицу для хранения отзывов"""
    try:
        with conn.cursor() as cursor:
            # SQL для создания таблицы
            create_table_query = sql.SQL("""
                CREATE TABLE IF NOT EXISTS {}.{} (
                    review_id SERIAL PRIMARY KEY,
                    school_id INTEGER,
                    review_date DATE,
                    review_text TEXT,
                    review_topics TEXT,
                    review_overall TEXT,
                    review_likes INTEGER,
                    review_dislikes INTEGER,
                    review_rating INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """).format(
                sql.Identifier(schema_name),
                sql.Identifier(table_name)
            )
            
            cursor.execute(create_table_query)
            print(f"[OK] Таблица '{schema_name}.{table_name}' создана или уже существует")
            
    except psycopg2.Error as e:
        print(f"[ERROR] Ошибка при создании таблицы: {e}")
        raise


def drop_table_if_exists(conn, schema_name: str, table_name: str):
    """Удаляет таблицу, если она существует (для пересоздания)"""
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                sql.SQL("DROP TABLE IF EXISTS {}.{} CASCADE").format(
                    sql.Identifier(schema_name),
                    sql.Identifier(table_name)
                )
            )
            print(f"[OK] Таблица '{schema_name}.{table_name}' удалена (если существовала)")
    except psycopg2.Error as e:
        print(f"[ERROR] Ошибка при удалении таблицы: {e}")
        raise


def alter_table_allow_nulls(conn, schema_name: str, table_name: str):
    """Убирает ограничения NOT NULL с полей, которые могут быть null"""
    try:
        with conn.cursor() as cursor:
            # Убираем NOT NULL со всех полей, которые могут быть null в JSON
            # Список всех полей, которые должны допускать NULL
            columns_to_alter = [
                'school_id',
                'review_date',
                'review_text',
                'review_topics',
                'review_overall',
                'review_likes',
                'review_dislikes',
                'review_rating'
            ]
            
            for column in columns_to_alter:
                try:
                    query = sql.SQL("ALTER TABLE {}.{} ALTER COLUMN {} DROP NOT NULL").format(
                        sql.Identifier(schema_name),
                        sql.Identifier(table_name),
                        sql.Identifier(column)
                    )
                    cursor.execute(query)
                    print(f"[OK] Убрано ограничение NOT NULL с колонки {column}")
                except psycopg2.Error as e:
                    # Игнорируем ошибки, если ограничение уже отсутствует
                    error_msg = str(e).lower()
                    if "does not exist" not in error_msg and "column" not in error_msg:
                        print(f"[WARN] Не удалось убрать ограничение с {column}: {e}")
    except psycopg2.Error as e:
        print(f"[ERROR] Ошибка при изменении таблицы: {e}")
        # Не поднимаем исключение, так как это не критично


def main(drop_existing: bool = False):
    """
    Основная функция для создания объектов БД
    
    Args:
        drop_existing: Если True, удаляет существующую таблицу перед созданием
    """
    conn = None
    try:
        print("[INFO] Начало создания объектов базы данных")
        print(f"[INFO] Схема: {DB_SCHEMA}")
        print(f"[INFO] Таблица: {DB_TABLE}")
        print()
        
        # Подключаемся к БД
        conn = get_connection()
        
        # Создаём схему
        create_schema(conn, DB_SCHEMA)
        
        # Удаляем таблицу, если нужно
        if drop_existing:
            drop_table_if_exists(conn, DB_SCHEMA, DB_TABLE)
        
        # Создаём таблицу
        create_table(conn, DB_SCHEMA, DB_TABLE)
        
        # Убираем NOT NULL ограничения, если таблица уже существовала
        alter_table_allow_nulls(conn, DB_SCHEMA, DB_TABLE)
        
        print()
        print("[OK] Все объекты базы данных успешно созданы!")
        
    except Exception as e:
        print(f"[ERROR] Критическая ошибка: {e}")
        raise
    finally:
        if conn:
            conn.close()
            print("[INFO] Подключение к БД закрыто")


if __name__ == "__main__":
    import sys
    # Если передан аргумент --drop, удаляем существующую таблицу
    drop_existing = '--drop' in sys.argv
    main(drop_existing=drop_existing)

