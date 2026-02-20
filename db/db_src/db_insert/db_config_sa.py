#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Общий модуль для подключения к БД схемы `sa`.
Подключение берётся из переменных окружения (.env).
"""

import os

import psycopg2
from dotenv import load_dotenv

# Загружаем переменные окружения из .env рядом с корнем проекта
load_dotenv()

# Параметры подключения к БД
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}


def get_connection():
    """
    Создаёт и возвращает подключение к базе данных PostgreSQL.

    Возвращает:
        psycopg2.extensions.connection: активное подключение.
    """
    return psycopg2.connect(**DB_CONFIG)


__all__ = ["get_connection", "DB_CONFIG"]

