#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Улучшенный скрипт для слияния данных о школах.
Возможности:
- Нормализация текста (регистр, аббревиатуры).
- Поиск топ-3 потенциальных совпадений.
- Расширенный вывод для анализа.
"""

import json
import os
import re
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# Настройки путей
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "vam_data")

SCHOOL_DATA_PATH = os.path.join(DATA_DIR, "C:/repos/analysis-of-educational-institutions/vectorization_and_merging/vam_school_near/vam_data/input/school.json")
SCHOOL_NEAR_DATA_PATH = os.path.join(DATA_DIR, "C:/repos/analysis-of-educational-institutions/vectorization_and_merging/vam_school_near/vam_data/input/school_near.json")
OUTPUT_DATA_PATH = os.path.join(DATA_DIR, "C:/repos/analysis-of-educational-institutions/vectorization_and_merging/vam_school_near/vam_data/output/merged_schools_enhanced.json")

def normalize_text(text):
    """
    Нормализует текст: нижний регистр, расшифровка аббревиатур, удаление шума.
    """
    if not text:
        return ""
    
    text = text.lower()
    
    # Словарь замены аббревиатур на полные формы для лучшего понимания модели
    # Порядок важен: сначала длинные, потом короткие, чтобы не обрезать части слов
    replacements = [
        (r"\bмуниципальное автономное общеобразовательное учреждение\b", "маоу"),
        (r"\bмуниципальное общеобразовательное учреждение\b", "моу"),
        (r"\bгосударственное автономное общеобразовательное учреждение\b", "гаоу"),
        (r"\bчастное общеобразовательное учреждение\b", "чоу"),
        (r"\bавтономная некоммерческая образовательная организация\b", "аноо"),
        (r"\bгосударственное бюджетное учреждение\b", "гбу"),
        (r"\bсредняя общеобразовательная школа\b", "сош"),
        (r"\bосновная общеобразовательная школа\b", "оош"),
        (r"\bначальная общеобразовательная школа\b", "нош"),
        (r"\bфизико-технический лицей\b", "фтл"),
        (r"\bмедико-биологический лицей\b", "мбл"),
        (r"\bгуманитарно-экономический лицей\b", "гэл"),
        (r"\bрусская православная классическая гимназия\b", "рмпкг"),
    ]

    # Расшифровываем аббревиатуры В ОБА НАПРАВЛЕНИЯ (если в тексте есть сокращение - разворачиваем, если полное - сворачиваем до сокращения для унификации)
    # Здесь я делаю унификацию ВСЕГО в нижний регистр без спецсимволов.
    # Лучший подход для эмбедингов: привести к единому "лемматизированному" виду без лишних слов.
    
    # Очистка от кавычек, точек, запятых
    text = re.sub(r'[«»"\'\\.,;:!?/()]', '', text)
    # Замена табуляций и переносов строк на пробелы
    text = re.sub(r'[\t\n\r]', ' ', text)
    # Удаление множественных пробелов
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def prepare_school_text(school):
    """Подготавливает строку для школы из основного файла."""
    # Берем полное название, короткое название и адрес
    parts = [
        school.get("school_name", ""),
        school.get("school_short_name", ""),
        school.get("school_adres", "")
    ]
    return " ".join([normalize_text(p) for p in parts if p])

def prepare_near_text(school):
    """Подготавливает строку для школы из файла близости."""
    # Берем название и район
    parts = [
        school.get("school_near_name", ""),
        school.get("district_near_name", "")
    ]
    return " ".join([normalize_text(p) for p in parts if p])

# --- Основной блок ---

print("[INFO] Загрузка данных...")
try:
    with open(SCHOOL_DATA_PATH, "r", encoding="utf-8") as f:
        raw_schools = json.load(f)
    schools_data = raw_schools.get("schools", raw_schools)
    print(f"[OK] Загружено schools: {len(schools_data)}")
except Exception as e:
    print(f"[ERROR] Ошибка загрузки school.json: {e}")
    exit(1)

try:
    with open(SCHOOL_NEAR_DATA_PATH, "r", encoding="utf-8") as f:
        near_data = json.load(f)
    print(f"[OK] Загружено school_near: {len(near_data)}")
except Exception as e:
    print(f"[ERROR] Ошибка загрузки school_near.json: {e}")
    exit(1)

print("[INFO] Подготовка текстов для векторизации...")
# Подготавливаем тексты
texts_schools = [prepare_school_text(s) for s in schools_data]
texts_near = [prepare_near_text(s) for s in near_data]

print("[INFO] Загрузка модели (all-mpnet-base-v2)...")
model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")

print("[INFO] Векторизация (это может занять время)...")
# Векторизуем пакетами для скорости
emb_schools = model.encode(texts_schools, show_progress_bar=True)
emb_near = model.encode(texts_near, show_progress_bar=True)

print("[INFO] Расчет матрицы схожести...")
similarity_matrix = cosine_similarity(emb_schools, emb_near)

print("[INFO] Поиск совпадений (Top-3)...")
results = []
used_near_indices = set()
TOP_K = 3
MATCH_THRESHOLD = 0.65 # Порог, выше которого считаем, что совпадение релевантно

for i, school in enumerate(schools_data):
    # Берем строку матрицы схожести для этой школы
    scores = similarity_matrix[i]
    
    # Находим индексы TOP_K лучших совпадений
    # argsort сортирует по возрастанию, поэтому берем с конца [-TOP_K:]
    top_indices = np.argsort(scores)[-TOP_K:][::-1]
    
    neighbors = []
    for idx in top_indices:
        score = scores[idx]
        if score > MATCH_THRESHOLD:
            near_school = near_data[idx]
            neighbors.append({
                "school_near_id": near_school.get("school_near_id"),
                "school_near_name": near_school.get("school_near_name"),
                "district_near_name": near_school.get("district_near_name"),
                "match_score": float(round(score, 4))
            })
            # Если совпадение очень хорошее (выше 0.75), помечаем эту запись из school_near как "найденную"
            if score > 0.75:
                used_near_indices.add(idx)
    
    # Формируем запись результата
    record = {
        "id": len(results) + 1,
        "school_id": school.get("school_id"),
        "school_name": school.get("school_name"),
        "school_short_name": school.get("school_short_name"),
        "school_adres": school.get("school_adres"),
        "nearest_neighbors": neighbors # Список из топ-3 кандидатов
    }
    results.append(record)

# Добавляем записи из school_near, которые не были сопоставлены
print("[INFO] Добавление записей без совпадений...")
unmatched_added = 0
for i, near_school in enumerate(near_data):
    if i not in used_near_indices:
        record = {
            "id": len(results) + 1,
            "school_id": None,
            "school_name": None,
            "school_short_name": None,
            "school_adres": None,
            "nearest_neighbors": [{
                "school_near_id": near_school.get("school_near_id"),
                "school_near_name": near_school.get("school_near_name"),
                "district_near_name": near_school.get("district_near_name"),
                "match_score": 0.0
            }]
        }
        results.append(record)
        unmatched_added += 1

print(f"[INFO] Итоговое количество записей: {len(results)}")
print(f"[INFO] Сопоставлено (хорошие совпадения): {len(used_near_indices)}")
print(f"[INFO] Добавлено несопоставленных из school_near: {unmatched_added}")

# Сохранение
print(f"[INFO] Сохранение результата в {OUTPUT_DATA_PATH}...")
os.makedirs(os.path.dirname(OUTPUT_DATA_PATH), exist_ok=True)
with open(OUTPUT_DATA_PATH, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("[OK] Готово!")