import pandas as pd
import json
import numpy as np
from typing import Set

excel_file_name = 'Здания школ.xlsx'
json_file_name = 'sd_2_stage_schools.json'

# --- Настройки ---
# Имя входного Excel-файла
excel_file_path = f'C:/repos/analysis-of-educational-institutions/school_data/sd_2_stage/{excel_file_name}'
# Имя выходного JSON-файла
json_file_path = f'C:/repos/analysis-of-educational-institutions/school_data/sd_2_stage/{json_file_name}'
# Лист Excel для чтения
excel_sheet_name = 'Информация о школах Саратова'



# ID школ, которые нужно включить (остальные отфильтровываются)
ALLOWED_SCHOOL_IDS: Set[str] = {
    *[str(i) for i in range(1, 110)],
    "110", "111",
    "115", "117",
    "122", "124",
    "130",
    "153", "154", "155", "156", "157", "158", "159",
    "160", "161", "162", "163", "164", "165",
    "167", "168", "169",
    "170", "171",
    "173", "175"
}

# --- Словарь для переименования столбцов ---
column_mapping = {
    "ID": "id",
    "Название на 2ГИС": "name_2gis",
    "Короткое название": "short_name",
    "Адрес": "address",
    "Тип здания": "building_type",
    "S, м2": "area_sqm",
    "Этажей": "floors",
    "Подз/э": "underground_floors",
    "Матер": "material",
    "г/пост": "year_built",
    "реконструкция": "reconstruction_year",
    "вместимость": "capacity",
    "ФОК": "has_sports_complex",
    "бассейн": "has_pool",
    "стадион": "has_stadium",
    "спортплощадка": "has_sports_ground",
    "Широта": "latitude",
    "Долгота": "longitude",
    "Кадастровый номер": "cadastral_number",
    "Рейтинг 2ГИС": "rating_2gis",
    "Рейтинг Яндекс": "rating_yandex",
    "Ссылка на Яндекс": "link_yandex",
    "Ссылка на отзывы Яндекс": "reviews_link_yandex",
    "Ссылка на 2ГИС": "link_2gis",
    "Ссылка на отзывы 2ГИС": "reviews_link_2gis"
}

try:
    # Шаг 1: Чтение данных из Excel (конкретный лист)
    df = pd.read_excel(excel_file_path, sheet_name=excel_sheet_name)

    # Шаг 2: Переименование столбцов согласно словарю
    df.rename(columns=column_mapping, inplace=True)

    # Шаг 2.1: Оставляем только школы с разрешёнными ID
    df['id'] = pd.to_numeric(df['id'], errors='coerce')
    # Сначала убираем строки с пустым id, иначе astype(int) падает на NaN
    df = df[df['id'].notna()].copy()
    df = df[df['id'].astype(int).astype(str).isin(ALLOWED_SCHOOL_IDS)].copy()

    # --- НОВЫЙ БЛОК: Преобразование данных и типов ---

    # Шаг 3: Преобразование "есть" в 1 для всех релевантных столбцов
    boolean_like_cols = ['has_sports_complex', 'has_pool', 'has_stadium', 'has_sports_ground']
    for col in boolean_like_cols:
        if col in df.columns:
            df[col] = df[col].replace({'есть': 1, 'Есть': 1}) # Добавил 'Есть' на всякий случай

    # Шаг 4: Коррекция типов данных
    # 4.1. Столбцы, которые должны быть целыми числами (если они не пустые)
    # Используем 'Int64' (с большой буквы), чтобы разрешить хранение пустых значений (null/NA)
    integer_columns = [
        'id', 'floors', 'underground_floors', 'year_built', 
        'reconstruction_year', 'capacity'
    ] + boolean_like_cols # Добавляем сюда же столбцы "есть/нет"

    for col in integer_columns:
        if col in df.columns:
            # Преобразуем в числовой тип, ошибки (например, текст) превратятся в NaN
            df[col] = pd.to_numeric(df[col], errors='coerce')
            # Преобразуем в nullable integer, который поддерживает NaN/NA
            df[col] = df[col].astype('Int64')

    # 4.2. Столбцы, которые должны быть числами с плавающей точкой
    float_columns = ['area_sqm', 'rating_2gis', 'rating_yandex']
    for col in float_columns:
        if col in df.columns:
            # Заменяем запятые на точки для корректного преобразования и конвертируем
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(',', '.', regex=False),
                errors='coerce'
            )

    # --- КОНЕЦ НОВОГО БЛОКА ---

    # Шаг 5: Обработка пустых ячеек (NaN/NaT/NA -> None) для корректного JSON
    # Pandas 1.0+ использует pd.NA для nullable типов. to_dict его правильно обработает.
    # Но для совместимости и обработки NaN во float столбцах лучше оставить замену.
    df = df.replace({np.nan: None, pd.NaT: None})

    # Шаг 6: Преобразование DataFrame в список словарей
    data_list = df.to_dict(orient='records')

    # Шаг 7: Добавление структурированных геокоординат
    processed_list = []
    for record in data_list:
        lat = record.get('latitude')
        lon = record.get('longitude')

        if pd.notna(lat) and pd.notna(lon):
            record['location'] = {
                'type': 'Point',
                'coordinates': [lon, lat] # Стандарт GeoJSON: [долгота, широта]
            }
        else:
            record['location'] = None
        
        processed_list.append(record)

    # Шаг 8: Запись результата в JSON-файл
    with open(json_file_path, 'w', encoding='utf-8') as json_file:
        json.dump(processed_list, json_file, ensure_ascii=False, indent=4)

    print(f"Файл '{json_file_path}' успешно создан!")

except FileNotFoundError:
    print(f"Ошибка: файл '{excel_file_path}' не найден.")
except Exception as e:
    print(f"Произошла ошибка: {e}")
