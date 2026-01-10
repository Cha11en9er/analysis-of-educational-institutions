#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для фильтрации школ из ym_full_schools_data.json.

Оставляет только те объекты, где в поле "adres" есть слово "Саратов".
Убирает школы из других населённых пунктов (посёлки, сёла и т.д.).

Результат сохраняется в ym_reviews_schools_all_data.json
"""

import json
import os
from typing import List, Dict, Any

# Пути относительно текущего файла
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
YM_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", ".."))
DATA_DIR = os.path.join(YM_ROOT, "ym_data")
OUTPUT_DIR = os.path.join(DATA_DIR, "ym_output")
INPUT_FILE = os.path.join(OUTPUT_DIR, "ym_full_school_data.json")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "ym_full_school_data_clear.json")


def is_in_saratov(adres: str) -> bool:
    """
    Проверяет, находится ли школа в городе Саратове по адресу.
    
    Оставляет только адреса, где "Саратов" - это город (например, ", Саратов" или в конце).
    Исключает адреса из "Саратовской области" (сёла, посёлки и т.д.).
    
    Args:
        adres: Адрес школы
        
    Returns:
        True, если адрес указывает на город Саратов
    """
    if not adres:
        return False
    
    adres_lower = adres.lower().strip()
    
    # Проверяем наличие ", Саратов" (запятая перед Саратовом) - это указывает на город
    if ", саратов" in adres_lower:
        return True
    
    # Проверяем, начинается ли адрес с "Саратов" (с запятой после или без) - это тоже город
    if adres_lower.startswith("саратов,") or adres_lower.startswith("саратов "):
        return True
    
    # Проверяем, заканчивается ли адрес на "Саратов" (с пробелом или без)
    if adres_lower.endswith("саратов") or adres_lower.endswith("саратов."):
        return True
    
    # Исключаем адреса, которые содержат "Саратовская область" но не содержат ", Саратов"
    # и не начинаются/заканчиваются на "Саратов" - это адреса из области, не из города
    if "саратовская область" in adres_lower:
        # Если есть "Саратовская область" но нет признаков города - это не город
        has_city_marker = (
            ", саратов" in adres_lower or
            adres_lower.startswith("саратов,") or
            adres_lower.startswith("саратов ") or
            adres_lower.endswith("саратов") or
            adres_lower.endswith("саратов.")
        )
        if not has_city_marker:
            return False
    
    # Исключаем адреса с указанием на сёла, посёлки, станции и т.д.
    # если они не в городе Саратове (нет ", Саратов" и не заканчивается на "Саратов")
    exclusion_keywords = [
        "село ",
        "посёлок ",
        "рабочий посёлок ",
        "станция ",
        "хутор ",
        "деревня ",
        "д. ",
        "с. ",
        "п. "
    ]
    
    has_exclusion = any(keyword in adres_lower for keyword in exclusion_keywords)
    if has_exclusion:
        # Если есть исключающие ключевые слова, но нет признаков города - это не город
        has_city_marker = (
            ", саратов" in adres_lower or
            adres_lower.startswith("саратов,") or
            adres_lower.startswith("саратов ") or
            adres_lower.endswith("саратов") or
            adres_lower.endswith("саратов.")
        )
        if not has_city_marker:
            return False
    
    # Проверяем, содержит ли адрес просто "Саратов" (может быть в любом месте, но не в составе "Саратовская область")
    # Это последняя проверка для адресов вида "Саратов, ..." или "... Саратов"
    if "саратов" in adres_lower and "саратовская область" not in adres_lower:
        # Если есть "Саратов" и нет "Саратовская область", вероятно это город
        return True
    
    # Во всех остальных случаях - не город Саратов
    return False


def filter_schools(input_file: str, output_file: str) -> None:
    """
    Читает JSON файл, фильтрует школы по адресу (только Саратов) и сохраняет результат.
    
    Args:
        input_file: Путь к входному JSON файлу
        output_file: Путь к выходному JSON файлу
    """
    # Читаем входной файл
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] Файл не найден: {input_file}")
        return
    except json.JSONDecodeError as e:
        print(f"[ERROR] Ошибка парсинга JSON ({input_file}): {e}")
        return
    
    schools = data.get("data", [])
    if not isinstance(schools, list):
        print(f"[ERROR] Неверный формат JSON: поле 'data' должно быть списком")
        return
    
    print(f"[INFO] Всего школ в исходном файле: {len(schools)}")
    
    # Фильтруем школы по адресу (только Саратов)
    filtered_schools: List[Dict[str, Any]] = []
    skipped_count = 0
    
    for school in schools:
        adres = school.get("adres", "")
        school_id = school.get("id", "unknown")
        name = school.get("name", "")
        
        if is_in_saratov(adres):
            filtered_schools.append(school)
        else:
            skipped_count += 1
            print(f"[SKIP] Школа id={school_id}, name='{name}', adres='{adres}' - не в Саратове")
    
    print(f"[INFO] Отфильтровано школ в Саратове: {len(filtered_schools)}")
    print(f"[INFO] Пропущено школ (не в Саратове): {skipped_count}")
    
    # Формируем выходную структуру
    output_data = {
        "source": data.get("source", "yandex_maps"),
        "topic": data.get("topic", "Школы Саратова"),
        "data": filtered_schools
    }
    
    # Сохраняем результат
    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=4)
        print(f"[OK] Результат сохранён в: {output_file}")
    except Exception as e:
        print(f"[ERROR] Не удалось сохранить файл {output_file}: {e}")


def main():
    """Основная функция"""
    print("[INFO] Старт фильтрации школ по адресу (только Саратов)")
    print(f"[INFO] Входной файл: {INPUT_FILE}")
    print(f"[INFO] Выходной файл: {OUTPUT_FILE}")
    print()
    
    filter_schools(INPUT_FILE, OUTPUT_FILE)
    
    print("\n[INFO] Работа завершена")


if __name__ == "__main__":
    main()

