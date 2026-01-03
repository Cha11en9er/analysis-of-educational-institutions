#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для извлечения уникальных школ из CSV файла и сохранения в JSON.
"""

import csv
import json
import os
from typing import Set, Dict, List

# Пути к файлам
CSV_FILE = os.path.join(os.path.dirname(__file__), '..', 'ans_data', 'ans_stage1_adres_near_school.csv')
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'ans_data', 'school_near.json')


def extract_unique_schools(csv_file: str) -> List[Dict[str, any]]:
    """
    Извлекает уникальные школы из CSV файла.
    
    Args:
        csv_file: Путь к CSV файлу
        
    Returns:
        Список словарей с уникальными школами
    """
    schools = []
    seen_schools: Set[tuple] = set()  # Для отслеживания дубликатов
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            # Читаем CSV с разделителем ';'
            reader = csv.DictReader(f, delimiter=';')
            
            for row in reader:
                # Извлекаем название школы и район
                school_name = row.get('Краткое наименование ОУ', '').strip()
                district_name = row.get('Район', '').strip()
                
                # Пропускаем пустые строки
                if not school_name or not district_name:
                    continue
                
                # Создаем ключ для проверки дубликатов
                school_key = (school_name, district_name)
                
                # Добавляем только если такой комбинации еще не было
                if school_key not in seen_schools:
                    seen_schools.add(school_key)
                    schools.append({
                        "school_near_id": len(schools) + 1,  # Сплошная нумерация начиная с 1
                        "school_near_name": school_name,
                        "district_near_name": district_name
                    })
        
        print(f"[OK] Извлечено уникальных школ: {len(schools)}")
        return schools
        
    except FileNotFoundError:
        print(f"[ERROR] Файл не найден: {csv_file}")
        return []
    except Exception as e:
        print(f"[ERROR] Ошибка при чтении CSV файла: {e}")
        return []


def save_to_json(schools: List[Dict[str, any]], output_file: str):
    """
    Сохраняет список школ в JSON файл.
    
    Args:
        schools: Список словарей с школами
        output_file: Путь к выходному JSON файлу
    """
    try:
        # Создаем директорию, если её нет
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # Сохраняем в JSON с красивым форматированием
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(schools, f, ensure_ascii=False, indent=2)
        
        print(f"[OK] Данные сохранены в файл: {output_file}")
        
    except Exception as e:
        print(f"[ERROR] Ошибка при сохранении JSON файла: {e}")


def main():
    """Основная функция"""
    print("[INFO] Начало извлечения школ из CSV файла")
    print(f"[INFO] Входной файл: {CSV_FILE}")
    print(f"[INFO] Выходной файл: {OUTPUT_FILE}")
    print()
    
    # Извлекаем уникальные школы
    schools = extract_unique_schools(CSV_FILE)
    
    if schools:
        # Сохраняем в JSON
        save_to_json(schools, OUTPUT_FILE)
        
        # Выводим примеры первых нескольких школ
        print()
        print("[INFO] Примеры извлеченных школ:")
        for i, school in enumerate(schools[:5], 1):
            print(f"  {i}. ID: {school['school_near_id']}, {school['school_near_name']} - {school['district_near_name']}")
        if len(schools) > 5:
            print(f"  ... и еще {len(schools) - 5} школ")
    else:
        print("[WARN] Не удалось извлечь школы из CSV файла")


if __name__ == "__main__":
    main()

