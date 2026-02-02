#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обратное геокодирование (Reverse Geocoding)
Получение адреса по координатам через API Яндекс.Карт
"""

import requests
import json
import os
import re
from dotenv import load_dotenv
from typing import Dict, Optional, Tuple

load_dotenv()

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
GC_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
DATA_DIR = os.path.join(GC_ROOT, 'gc_data')
INPUT_DIR = os.path.join(DATA_DIR, 'gc_input')
OUTPUT_DIR = os.path.join(DATA_DIR, 'gc_output')

# Ваш ключ API от Яндекс.Карт
API_KEY = os.getenv("YANDEX_API_KEY")
BASE_URL = "https://geocode-maps.yandex.ru/1.x/"


def parse_coordinates(coord_string: str) -> Optional[Tuple[float, float]]:
    """
    Парсит координаты из строки в формате "(широта, долгота)" или "широта, долгота"
    
    Args:
        coord_string: Строка с координатами, например "(51.558543, 46.076468)" или "51.558543, 46.076468"
    
    Returns:
        Кортеж (широта, долгота) или None если не удалось распарсить
    """
    if not coord_string:
        return None
    
    # Убираем скобки и пробелы
    coord_string = coord_string.strip().strip('()').replace(' ', '')
    
    try:
        parts = coord_string.split(',')
        if len(parts) != 2:
            return None
        
        latitude = float(parts[0])
        longitude = float(parts[1])
        
        return (latitude, longitude)
    except (ValueError, AttributeError):
        return None


def reverse_geocode(latitude: float, longitude: float, kind: str = "house") -> Optional[Dict]:
    """
    Обратное геокодирование: получение адреса по координатам
    
    Args:
        latitude: Широта
        longitude: Долгота
        kind: Тип объекта для поиска (house, street, metro, district, locality)
              По умолчанию "house" - ищет ближайший дом
    
    Returns:
        Словарь с информацией об адресе или None при ошибке
        {
            "address": "полный адрес",
            "components": {...},  # компоненты адреса
            "latitude": float,
            "longitude": float
        }
    """
    if not API_KEY:
        raise RuntimeError("YANDEX_API_KEY не найден в окружении (.env)")
    
    # Формат для обратного геокодирования: долгота,широта
    geocode = f"{longitude},{latitude}"
    
    params = {
        "apikey": API_KEY,
        "geocode": geocode,
        "format": "json",
        "kind": kind,  # Тип объекта
        "results": 1,  # Только один результат
    }
    
    try:
        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        members = data.get("response", {}).get("GeoObjectCollection", {}).get("featureMember", [])
        if not members:
            return None
        
        geo_object = members[0].get("GeoObject", {})
        meta = geo_object.get("metaDataProperty", {}).get("GeocoderMetaData", {})
        
        # Полный адрес
        address = meta.get("text", "")
        
        # Компоненты адреса
        components = {}
        address_components = meta.get("Address", {}).get("Components", [])
        for component in address_components:
            component_kind = component.get("kind", "")
            component_name = component.get("name", "")
            components[component_kind] = component_name
        
        # Координаты точки
        point = geo_object.get("Point", {}).get("pos", "").split()
        if point:
            lon, lat = float(point[0]), float(point[1])
        else:
            lat, lon = latitude, longitude
        
        return {
            "address": address,
            "components": components,
            "latitude": lat,
            "longitude": lon,
            "precision": meta.get("precision", ""),  # Точность определения адреса
        }
    except Exception as e:
        print(f"Ошибка при обратном геокодировании: {e}")
        return None


def reverse_geocode_from_string(coord_string: str, kind: str = "house") -> Optional[Dict]:
    """
    Обратное геокодирование из строки с координатами
    
    Args:
        coord_string: Строка с координатами в формате "(широта, долгота)"
        kind: Тип объекта для поиска
    
    Returns:
        Словарь с информацией об адресе или None
    """
    coords = parse_coordinates(coord_string)
    if coords is None:
        print(f"Не удалось распарсить координаты: {coord_string}")
        return None
    
    latitude, longitude = coords
    return reverse_geocode(latitude, longitude, kind)


def process_schools_with_coordinates(input_file: str, output_file: str):
    """
    Обрабатывает JSON файл со школами, добавляя адреса по координатам
    
    Args:
        input_file: Путь к входному JSON файлу со школами (с полем coordinates)
        output_file: Путь к выходному JSON файлу
    """
    with open(input_file, 'r', encoding='utf-8') as f:
        schools = json.load(f)
    
    print(f"Обрабатываем {len(schools)} школ...\n")
    
    for i, school in enumerate(schools, 1):
        coord_string = school.get('coordinates')
        
        if not coord_string:
            print(f"[{i}/{len(schools)}] {school.get('school_near_name', 'Unknown')}: нет координат")
            school['address_from_coords'] = None
            continue
        
        print(f"[{i}/{len(schools)}] {school.get('school_near_name', 'Unknown')}")
        print(f"  Координаты: {coord_string}")
        
        # Пробуем сначала найти дом
        result = reverse_geocode_from_string(coord_string, kind="house")
        
        # Если не нашли дом, пробуем улицу
        if not result:
            result = reverse_geocode_from_string(coord_string, kind="street")
        
        if result:
            school['address_from_coords'] = result['address']
            school['address_components'] = result['components']
            school['address_precision'] = result['precision']
            print(f"  Адрес: {result['address']}")
        else:
            school['address_from_coords'] = None
            print(f"  Не удалось определить адрес")
        
        print()
    
    # Сохраняем результат
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(schools, f, ensure_ascii=False, indent=2)
    
    print(f"\n[OK] Результаты сохранены в файл: {output_file}")


def try_geocode_cadastral_number(cadastral_number: str) -> Optional[Dict]:
    """
    Пытается геокодировать кадастровый номер через API Яндекс.Карт
    
    ВАЖНО: API Яндекс.Карт НЕ поддерживает прямой поиск по кадастровым номерам.
    Кадастровый номер имеет формат: "64:48:000000:221028"
    (регион:округ:район:участок)
    
    Эта функция показывает, что вернет API при попытке использовать кадастровый номер.
    
    Args:
        cadastral_number: Кадастровый номер в формате "64:48:000000:221028"
    
    Returns:
        Результат запроса или None
    """
    if not API_KEY:
        raise RuntimeError("YANDEX_API_KEY не найден в окружении (.env)")
    
    print(f"Попытка геокодирования кадастрового номера: {cadastral_number}")
    print("(API Яндекс.Карт обычно не поддерживает кадастровые номера напрямую)")
    
    params = {
        "apikey": API_KEY,
        "geocode": cadastral_number,
        "format": "json",
        "results": 1,
    }
    
    try:
        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        members = data.get("response", {}).get("GeoObjectCollection", {}).get("featureMember", [])
        
        if not members:
            print("Результат: API не нашел объект по кадастровому номеру")
            return None
        
        geo_object = members[0].get("GeoObject", {})
        meta = geo_object.get("metaDataProperty", {}).get("GeocoderMetaData", {})
        address = meta.get("text", "")
        
        print(f"Результат: {address}")
        return {
            "address": address,
            "full_response": data
        }
    except Exception as e:
        print(f"Ошибка: {e}")
        return None


def main():
    """
    Пример использования:
    1. Обратное геокодирование одной точки
    2. Проверка кадастрового номера
    3. Обработка файла со школами
    """
    # Пример 1: Обратное геокодирование одной координаты
    print("=" * 60)
    print("Пример 1: Обратное геокодирование координат")
    print("=" * 60)
    
    test_coords = "(51.558543, 46.076468)"
    print(f"Координаты: {test_coords}")
    
    result = reverse_geocode_from_string(test_coords)
    if result:
        print(f"Адрес: {result['address']}")
        print(f"Компоненты: {result['components']}")
        print(f"Точность: {result['precision']}")
    else:
        print("Не удалось определить адрес")
    
    # Пример 2: Проверка кадастрового номера
    print("\n" + "=" * 60)
    print("Пример 2: Попытка геокодирования кадастрового номера")
    print("=" * 60)
    
    cadastral = "64:48:000000:221028"
    try_geocode_cadastral_number(cadastral)
    
    print("\n" + "=" * 60)
    print("Пример 3: Обработка файла со школами")
    print("=" * 60)
    
    # Пример 3: Обработка файла
    input_file = os.path.join(OUTPUT_DIR, 'gc_school_near_output_data.json')
    output_file = os.path.join(OUTPUT_DIR, 'gc_school_near_with_addresses.json')
    
    if os.path.exists(input_file):
        process_schools_with_coordinates(input_file, output_file)
    else:
        print(f"Файл {input_file} не найден. Пропускаем обработку файла.")


if __name__ == "__main__":
    main()

