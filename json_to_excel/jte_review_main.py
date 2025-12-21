import json
import pandas as pd

# 1️⃣ Читаем JSON-файл
with open('C:/repos/analysis-of-educational-institutions/global_data/compare_review.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

reviews = data['reviews']
df = pd.DataFrame(reviews)

df = df.fillna('')

df.to_excel('C:/repos/analysis-of-educational-institutions/global_data/schools_reviews.xlsx', index=False, sheet_name='Информация об отзывах школ Саратова')