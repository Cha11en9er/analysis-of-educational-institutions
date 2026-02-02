#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для фильтрации отзывов из файла compare_review.json.
Оставляет только отзывы школ с указанными ID.
"""

import json
import os
import sys
from typing import List, Set

# Путь к входному файлу
INPUT_FILE = r'C:\repos\analysis-of-educational-institutions\global_data\compare_review.json'

# Путь к выходному файлу (можно изменить на тот же файл для перезаписи)
OUTPUT_FILE = r'C:\repos\analysis-of-educational-institutions\global_data\compare_review_clear.json'

# Список ID школ, отзывы которых нужно оставить
# Список основан на прикрепленном изображении (не все числа подряд, есть пропуски)
ALLOWED_SCHOOL_IDS: Set[str] = {
    # 1-109 (все подряд)
    *[str(i) for i in range(1, 110)],
    # 110-111
    "110", "111",
    # Пропущены 112, 113, 114, 116
    "115", "117",
    # Пропущены 118-121, 123
    "122", "124",
    # Пропущены 125-129
    "130",
    # Пропущены 131-152
    "153", "154", "155", "156", "157", "158", "159",
    "160", "161", "162", "163", "164", "165",
    # Пропущен 166
    "167", "168", "169",
    "170", "171",
    # Пропущен 172, 174
    "173", "175"
}


def load_reviews(file_path: str) -> dict:
    """Загружает отзывы из JSON файла"""
    print(f"[INFO] Загрузка данных из {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data


def get_unique_school_ids(reviews: List[dict]) -> Set[str]:
    """Получает все уникальные ID школ из отзывов"""
    school_ids = set()
    for review in reviews:
        school_id = review.get('school_id', '')
        if school_id is not None:
            school_ids.add(str(school_id))
    return school_ids


def filter_reviews_by_school_ids(reviews: List[dict], allowed_ids: Set[str]) -> List[dict]:
    """Фильтрует отзывы, оставляя только те, у которых school_id в списке разрешенных"""
    filtered_reviews = []
    removed_count = 0
    
    for review in reviews:
        school_id = review.get('school_id', '')
        # Преобразуем school_id в строку для сравнения
        school_id_str = str(school_id) if school_id is not None else ''
        
        if school_id_str in allowed_ids:
            filtered_reviews.append(review)
        else:
            removed_count += 1
    
    print(f"[INFO] Всего отзывов: {len(reviews)}")
    print(f"[INFO] Оставлено отзывов: {len(filtered_reviews)}")
    print(f"[INFO] Удалено отзывов: {removed_count}")
    
    return filtered_reviews


def save_reviews(data: dict, file_path: str):
    """Сохраняет отфильтрованные отзывы в JSON файл"""
    print(f"[INFO] Сохранение данных в {file_path}...")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"[OK] Данные успешно сохранены")


def main(allowed_ids: Set[str] = None):
    """
    Основная функция
    
    Args:
        allowed_ids: Множество разрешенных ID школ. Если None, используется ALLOWED_SCHOOL_IDS
    """
    if allowed_ids is None:
        allowed_ids = ALLOWED_SCHOOL_IDS
    
    try:
        # Загружаем данные
        data = load_reviews(INPUT_FILE)
        reviews = data.get('reviews', [])
        
        if not reviews:
            print("[WARN] Файл не содержит отзывов")
            return
        
        # Показываем все уникальные ID школ в файле (для проверки)
        unique_ids = get_unique_school_ids(reviews)
        print(f"[INFO] Всего уникальных ID школ в файле: {len(unique_ids)}")
        sorted_unique = sorted(unique_ids, key=lambda x: int(x) if x.isdigit() else 999)
        print(f"[INFO] ID школ в файле (первые 30): {sorted_unique[:30]}...")
        
        # Фильтруем отзывы
        filtered_reviews = filter_reviews_by_school_ids(reviews, allowed_ids)
        
        # Обновляем данные
        data['reviews'] = filtered_reviews
        
        # Сохраняем результат
        save_reviews(data, OUTPUT_FILE)
        
        print(f"\n[OK] Фильтрация завершена успешно!")
        # Сортируем ID для вывода (числа по значению, строки в конце)
        sorted_ids = sorted(allowed_ids, key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else 999))
        print(f"[INFO] Разрешенные ID школ (первые 20): {sorted_ids[:20]}...")
        print(f"[INFO] Всего разрешенных ID: {len(allowed_ids)}")
        
    except FileNotFoundError:
        print(f"[ERROR] Файл не найден: {INPUT_FILE}")
    except json.JSONDecodeError as e:
        print(f"[ERROR] Ошибка при чтении JSON: {e}")
    except Exception as e:
        print(f"[ERROR] Неожиданная ошибка: {e}")
        raise


if __name__ == "__main__":
    # Можно передать список ID через аргументы командной строки
    # Пример: python gd_delete_wrong_school_review.py 1 2 3 10 20
    if len(sys.argv) > 1:
        custom_ids = {str(arg) for arg in sys.argv[1:]}
        print(f"[INFO] Используются ID из аргументов командной строки: {sorted(custom_ids, key=lambda x: int(x) if x.isdigit() else 999)}")
        main(allowed_ids=custom_ids)
    else:
        main()
