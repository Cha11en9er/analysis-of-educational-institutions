import json
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
VAM_ROOT = os.path.dirname(CURRENT_DIR)
DATA_DIR = os.path.join(VAM_ROOT, "vam_data")
INPUT_DIR = os.path.join(DATA_DIR, "vam_data_input")
OUTPUT_DIR = os.path.join(DATA_DIR, "vam_data_output")
TWO_GIS_DATA_PATH = os.path.join(INPUT_DIR, "vam_2gis_input_data.json")
YANDEX_MAPS_DATA_PATH = os.path.join(INPUT_DIR, "vam_ym_input_data.json")
OUTPUT_DATA_PATH = os.path.join(OUTPUT_DIR, "gold_vam_output_data.json")

# Загружаем JSON
with open(TWO_GIS_DATA_PATH, "r", encoding="utf-8") as f:
    data1_raw = json.load(f)

with open(YANDEX_MAPS_DATA_PATH, "r", encoding="utf-8") as f:
    data2_raw = json.load(f)

# В обоих файлах данные лежат внутри ключа "data"
data1 = data1_raw.get("data", data1_raw)
data2 = data2_raw.get("data", data2_raw)

# Модель для векторизации
model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")

def prepare_text(school):
    parts = [
        school.get("name", ""),
        school.get("adres", ""),
    ]
    return " ".join(p for p in parts if p)

# Векторизуем
emb1 = model.encode([prepare_text(x) for x in data1])
emb2 = model.encode([prepare_text(x) for x in data2])

def build_record(row_id, gis_school=None, ym_school=None, score=None):
    """Формирует итоговую запись."""

    # Только школа из Яндекс — возвращаем как есть, но с новым id.
    if gis_school is None and ym_school is not None:
        record = {**ym_school}
        record["id"] = row_id
        return record

    # Только школа из 2ГИС либо объединённая запись.
    record = {
        "id": row_id,
        "name": gis_school.get("name") if gis_school else None,
        "full_name": gis_school.get("full_name") if gis_school else None,
        "adres": gis_school.get("adres") if gis_school else None,
        "2gis_url": gis_school.get("url") if gis_school else None,
        "ym_url": ym_school.get("url") if ym_school else None,
        "cadastral_number": gis_school.get("cadastral_number") if gis_school else None,
    }

    if score is not None:
        record["match_score"] = float(score)

    if ym_school:
        record["yandex_id"] = ym_school.get("yandex_id")
        record["reviews_count"] = ym_school.get("reviews_count")

    return record


result = []
used_in_file2 = set()
row_id_counter = 1

for i, school1 in enumerate(data1):
    vec1 = emb1[i].reshape(1, -1)

    sims = cosine_similarity(vec1, emb2)[0]
    best_idx = int(np.argmax(sims))
    best_score = sims[best_idx]

    if best_score > 0.78:  # порог подбора
        school2 = data2[best_idx]
        used_in_file2.add(best_idx)

        record = build_record(row_id_counter, gis_school=school1, ym_school=school2, score=best_score)
        result.append(record)
    else:
        record = build_record(row_id_counter, gis_school=school1)
        result.append(record)

    row_id_counter += 1

# Добавляем те, что остались из 2-го файла
for i, school2 in enumerate(data2):
    if i not in used_in_file2:
        record = build_record(row_id_counter, ym_school=school2)
        result.append(record)
        row_id_counter += 1

# Сохраняем результат
with open(OUTPUT_DATA_PATH, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=4)