import json
import pandas as pd

# 1️⃣ Читаем JSON-файл
with open('C:/repos/analysis-of-educational-institutions/global_data/school_merge_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

schools = data['data']
df = pd.DataFrame(schools)

columns_to_keep = [
    'id',
    "2gis_full_name",
    'geocoords',
    "cadastral_number",
    '2gis_rating',
    "ym_rating",
    "ym_url",
    "ym_review_url",
    "2gis_url",
    "2gis_review_url"
]

df = df[columns_to_keep]

rename_mapping = {
    'id': 'ID',
    '2gis_full_name': 'Название на 2ГИС',
    'geocoords': 'Геокоординаты',
    'cadastral_number': 'Кадастровый номер',
    '2gis_rating': 'Рейтинг 2ГИС',
    'ym_rating': 'Рейтинг Яндекс',
    'ym_url': 'Ссылка на Яндекс',
    "ym_review_url": 'Ссылка на отзывы Яндекс',
    '2gis_url': 'Ссылка на 2ГИС',
    "2gis_review_url": 'Ссылка на отзывы 2ГИС'
}

df = df.rename(columns=rename_mapping)

# 6️⃣ Заменяем NaN на пустые строки, чтобы Excel выглядел аккуратно
df = df.fillna('')

df.to_excel('C:/repos/analysis-of-educational-institutions/global_data/schools_output.xlsx', index=False, sheet_name='Информация о школах Саратова')