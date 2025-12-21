# Подготовка данных для анализа --------------------------------
import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
from collections import Counter
import re
from sklearn.feature_extraction.text import TfidfVectorizer
import seaborn as sns
import json
import os

# Загрузка данных из JSON файла
input_file = os.path.join(os.path.dirname(__file__), '..', 'fa_data', 'fa_input', 'fa_input_data_id_3.json')
with open(input_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Преобразование в DataFrame
df = pd.DataFrame(data['reviews'])  # ваши отзывы

# Парсинг дат
df['date'] = pd.to_datetime(df['date'])
df['year_month'] = df['date'].dt.to_period('M')
df['year'] = df['date'].dt.year

# Нормализация tonality для анализа
tonality_map = {'Положительный': 1, 'Отрицательный': -1, 'Нейтральный': 0, 'Средний': 0}
df['sentiment_score'] = df['tonality'].map(tonality_map)
# подготовили данные для анализа --------------------------------

# средний рейтинг и тональность по месяцам --------------------------------
monthly_stats = df.groupby('year_month').agg({
    'rating': ['mean', 'count'],
    'sentiment_score': 'mean',
    'likes_count': 'mean'
}).round(2)

monthly_stats.columns = ['avg_rating', 'review_count', 'avg_sentiment', 'avg_likes']
monthly_stats['avg_rating'] = monthly_stats['avg_rating'].fillna(0)

# Визуализация
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10))

monthly_stats['avg_rating'].plot(ax=ax1, marker='o', linewidth=2)
ax1.set_title('Средний рейтинг по месяцам')
ax1.grid(True)

monthly_stats['avg_sentiment'].plot(ax=ax2, marker='s', linewidth=2, color='red')
ax2.set_title('Средняя тональность отзывов (1=положительная, -1=отрицательная)')
ax2.grid(True)

plt.tight_layout()
plt.show()
# средний рейтинг и тональность по месяцам --------------------------------

# Анализ тем main_idea по месяцам --------------------------------
def extract_keywords(texts, top_n=10):
    """Извлечение ключевых слов из main_idea"""
    # Если документов меньше 2, используем min_df=1
    min_df_value = min(2, max(1, len(texts) - 1)) if len(texts) > 1 else 1
    
    # Фильтруем пустые тексты
    texts_filtered = [str(text).strip() for text in texts if str(text).strip()]
    
    if len(texts_filtered) == 0:
        return []
    
    try:
        vectorizer = TfidfVectorizer(max_features=100, stop_words='english', 
                                    ngram_range=(1,2), min_df=min_df_value)
        tfidf_matrix = vectorizer.fit_transform(texts_filtered)
        feature_names = vectorizer.get_feature_names_out()
        
        if len(feature_names) == 0:
            return []
        
        # Средний TF-IDF score для каждого слова
        mean_scores = np.mean(tfidf_matrix.toarray(), axis=0)
        top_indices = mean_scores.argsort()[-top_n:][::-1]
        
        return [(feature_names[i], mean_scores[i]) for i in top_indices]
    except ValueError:
        # Если все еще ошибка, возвращаем пустой список
        return []

# Группировка по месяцам
monthly_themes = df.groupby('year_month')['main_idea'].apply(list).reset_index()

themes_evolution = []
for idx, row in monthly_themes.iterrows():
    month = row['year_month']
    texts = row['main_idea']
    if len(texts) > 0:
        keywords = extract_keywords(texts, top_n=8)
        themes_evolution.append({
            'month': month,
            'review_count': len(texts),
            'top_themes': keywords[:5]
        })

themes_df = pd.DataFrame(themes_evolution)
# анализ тем main_idea по месяцам --------------------------------

# Категоризация тем + временная эволюция --------------------------------
# Создание категорий тем
theme_categories = {
    'ремонт': ['ремонт', 'стены', 'трещины', 'туалет', 'мозаик', 'асфальт'],
    'учителя': ['учитель', 'преподаватель', 'педагог', 'классный'],
    'еда': ['еда', 'корм', 'столовая', 'питание', 'отрав'],
    'администрация': ['директор', 'завуч', 'руководитель'],
    'буллинг': ['травля', 'буллинг', 'обиж', 'бьют'],
    'инфраструктура': ['парковк', 'место', 'пространств', 'класс']
}

def categorize_themes(main_idea, categories):
    """Классификация main_idea по категориям"""
    main_idea_lower = main_idea.lower()
    cat_scores = {}
    for cat, keywords in categories.items():
        score = sum(1 for kw in keywords if kw in main_idea_lower)
        cat_scores[cat] = score
    return cat_scores

# Применение к данным
df['theme_scores'] = df['main_idea'].apply(lambda x: categorize_themes(x, theme_categories))

# Преобразование в длинный формат для анализа
theme_evolution = []
for idx, row in df.iterrows():
    for theme, score in row['theme_scores'].items():
        if score > 0:
            theme_evolution.append({
                'date': row['date'],
                'year_month': row['year_month'],
                'theme': theme,
                'sentiment': row['sentiment_score'],
                'rating': row['rating'],
                'likes': row['likes_count']
            })

theme_df = pd.DataFrame(theme_evolution)
monthly_theme_trends = theme_df.groupby(['year_month', 'theme']).agg({
    'rating': 'mean',
    'sentiment': 'mean',
    'likes': 'mean'
}).reset_index()
# категоризация тем + временная эволюция --------------------------------

# тепловая карта изменений тем по месяцам --------------------------------
pivot_sentiment = monthly_theme_trends.pivot(
    index='year_month', columns='theme', values='sentiment'
).fillna(0)

plt.figure(figsize=(14, 8))
sns.heatmap(pivot_sentiment, annot=True, cmap='RdYlGn', center=0, 
            fmt='.2f', cbar_kws={'label': 'Средняя тональность'})
plt.title('Эволюция тональности тем по месяцам')
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
# тепловая карта изменений тем по месяцам --------------------------------

# интерактивная визуализация тем по месяцам plotly --------------------------------
from scipy.stats import zscore
from sklearn.linear_model import LinearRegression

# Детекция резких изменений в рейтинге
monthly_stats['rating_zscore'] = zscore(monthly_stats['avg_rating'].fillna(0))

# Нахождение точек изменений (аномалий)
change_points = monthly_stats[abs(monthly_stats['rating_zscore']) > 1.5]

print("Точки резких изменений:")
print(change_points[['avg_rating', 'review_count', 'avg_sentiment']])

# Анализ отзывов в точках изменений
for idx, cp in change_points.iterrows():
    month_reviews = df[df['year_month'] == cp.name]
    print(f"\n=== {cp.name} ===")
    print("Топ main_idea:")
    print(month_reviews['main_idea'].value_counts().head())
# интерактивная визуализация тем по месяцам plotly --------------------------------

# финальный отчёт --------------------------------
def generate_summary():
    summary = f"""
    📊 АНАЛИЗ ОТЗЫВОВ ШКОЛЫ №2
    
    Общая статистика:
    • Всего отзывов: {len(df)}
    • Средний рейтинг: {df['rating'].mean():.1f}
    • Положительных: {len(df[df['sentiment_score']==1])} ({len(df[df['sentiment_score']==1])/len(df)*100:.0f}%)
    
    🕒 Ключевые тренды:
    """
    
    # Топ изменения
    recent_trend = monthly_stats['avg_rating'].iloc[-6:].mean() - monthly_stats['avg_rating'].iloc[:-6].mean()
    summary += f"• Тренд за последние 6м: {'📈 улучшение' if recent_trend>0 else '📉 ухудшение'} на {recent_trend:.1f} баллов"
    
    # Популярные темы
    all_themes = Counter()
    for ideas in df['main_idea'].str.split(',').tolist():
        all_themes.update([idea.strip() for idea in ideas if idea.strip()])
    
    summary += f"\n• Топ темы: {dict(all_themes.most_common(5))}"
    
    print(summary)

generate_summary()
# финальный отчёт --------------------------------