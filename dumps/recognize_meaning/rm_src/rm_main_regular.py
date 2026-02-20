"""
================================================================================
ОБРАБОТКА ОТЗЫВОВ О ШКОЛАХ (БЕСПЛАТНАЯ ВЕРСИЯ)
================================================================================

Этот скрипт обрабатывает отзывы о школах, извлекая ключевые темы и определяя
тональность БЕЗ использования платных API.

ОСОБЕННОСТИ:
- Структурированный формат вывода (topics + overall sentiment)
- Использование rating для определения тональности (если доступен)
- Тематические признаки качества для агрегации по школам
- Категоризация тем по ключевым словам
- Полностью бесплатно и быстро

ВЫХОДНОЙ ФОРМАТ:
{
  "topics": {
    "учителя": "pos",
    "еда": "neg",
    "ремонт": "pos"
  },
  "overall": "pos"
}

ТЕМАТИЧЕСКИЕ ПРИЗНАКИ КАЧЕСТВА (для агрегации по школам):
- topic_cnt_<topic> - количество отзывов по теме
- topic_neg_share_<topic> - доля негативных отзывов по теме
- topic_sentiment_<topic> - средняя тональность по теме (-1 до +1)
- topic_recent_neg_share_<topic> - доля негативных в свежих отзывах (12 мес)

================================================================================
"""

import os
import json
import re
from datetime import datetime, timedelta
from collections import defaultdict

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
RM_ROOT = os.path.dirname(CURRENT_DIR)
DATA_DIR = os.path.join(RM_ROOT, 'rm_data')
INPUT_DIR = os.path.join(DATA_DIR, 'rm_input')
OUTPUT_DIR = os.path.join(DATA_DIR, 'rm_output')
INPUT_REVIEW_FILE = os.path.join(INPUT_DIR, 'rm_input_data.json')
OUTPUT_REVIEW_FILE = os.path.join(OUTPUT_DIR, 'rm_output_data.json')

# Категории тем для извлечения main_idea
# ВАЖНО: ключевые слова должны быть в базовой форме, поиск учитывает падежи и множественное число
THEME_CATEGORIES = {
    'ремонт': ['ремонт', 'стены', 'трещины', 'туалет', 'мозаик', 'асфальт', 'потолок', 'пол', 'окна', 'двери', 'отопление', 'тепло'],
    'учителя': [
        'учитель', 'учителя', 'учителей', 'учителю', 'учителем',  # падежи слова "учитель"
        'преподаватель', 'преподаватели', 'преподавателей', 'преподавателю', 'преподавателем',  # падежи слова "преподаватель"
        'педагог', 'педагоги', 'педагогов', 'педагогу', 'педагогом',  # падежи слова "педагог"
        'классный руководитель', 'классная руководительница',  # фразы
        'предмет', 'урок', 'уроки', 'обучение', 'преподавание', 'репетитор'
    ],
    'еда': ['еда', 'корм', 'столовая', 'питание', 'отрав', 'обед', 'завтрак', 'меню'],
    'администрация': ['директор', 'завуч', 'руководитель', 'администрация', 'управление'],
    'буллинг': ['травля', 'буллинг', 'обиж', 'бьют', 'конфликт', 'ссора'],
    'инфраструктура': ['парковк', 'пространств', 'спортзал', 'бассейн', 'стадион', 'площадка', 'кабинет', 'кабинеты', 'оборудование'],
    'охрана': ['охрана', 'безопасность', 'пропуск', 'вход', 'выход'],
    'уборка': ['уборка', 'чистота', 'грязно', 'мусор', 'санитар']
}

# Слова-индикаторы положительной тональности (только слова, не фразы)
POSITIVE_WORDS = [
    'хорош', 'отличн', 'прекрасн', 'замечательн', 'великолепн', 'супер', 'классн',
    'нравится', 'доволен', 'рекомендую', 'спасибо', 'благодар', 'люблю',
    'лучш', 'профессионал', 'качествен', 'удобн', 'комфортн'
]

# Слова-индикаторы отрицательной тональности (только слова, без дубликатов)
NEGATIVE_WORDS = [
    'плох', 'ужасн', 'кошмар', 'отвратительн', 'недоволен', 'жалоб', 'проблем',
    'нельзя', 'ужас', 'плохо', 'неудобн', 'некачествен', 'непрофессионал',
    'разочарован'
]

# Фразы-индикаторы отрицательной тональности (отдельно для поиска по подстроке)
NEGATIVE_PHRASES = [
    'не рекомендую', 'не советую', 'не нравится', 'не доволен', 'не довольна'
]

def get_sentiment_from_rating(rating):
    """
    Определяет тональность из рейтинга (1-5).
    Возвращает: 1 (положительный), -1 (отрицательный), 0 (нейтральный)
    """
    if rating is None:
        return None
    
    try:
        rating = int(rating)
        if rating >= 4:
            return 1  # Положительный
        elif rating <= 2:
            return -1  # Отрицательный
        else:
            return 0  # Нейтральный
    except (ValueError, TypeError):
        return None

def analyze_text_sentiment(text):
    """
    Анализирует тональность текста на основе словарей.
    Возвращает: 1 (положительный), -1 (отрицательный), 0 (нейтральный)
    """
    if not text:
        return 0
    
    text_lower = text.lower()
    
    # Подсчет положительных слов
    positive_score = sum(1 for word in POSITIVE_WORDS if word in text_lower)
    
    # Подсчет отрицательных слов
    negative_score = sum(1 for word in NEGATIVE_WORDS if word in text_lower)
    
    # Проверка отрицательных фраз
    for phrase in NEGATIVE_PHRASES:
        if phrase in text_lower:
            negative_score += 2
    
    # Проверка отрицаний перед положительными словами
    negation_pattern = r'\b(не|нет|ничего|никогда)\s+\w*\s*(?:' + '|'.join(POSITIVE_WORDS[:5]) + r')'
    if re.search(negation_pattern, text_lower):
        negative_score += 2
    
    # Определение тональности
    if positive_score > negative_score:
        return 1
    elif negative_score > positive_score:
        return -1
    else:
        return 0

def recognize_review_free(review_text, rating=None):
    """
    БЕСПЛАТНАЯ версия обработки отзывов.
    Возвращает структурированный формат с topics и overall sentiment.
    УБРАНА нейтральная оценка - только "pos" или "neg".
    
    Args:
        review_text: Текст отзыва
        rating: Рейтинг отзыва (1-5), если доступен
        
    Returns:
        dict с полями:
        - topics: dict {topic: "pos"/"neg"} (без "neutral")
        - overall: "pos"/"neg" (без "neutral")
    """
    # Проверка на None
    if review_text is None:
        return {
            "topics": {},
            "overall": "pos"
        }
    
    # Преобразуем в строку, если нужно
    if not isinstance(review_text, str):
        review_text = str(review_text) if review_text is not None else ""
    
    if not review_text.strip():
        return {
            "topics": {},
            "overall": "pos"  # По умолчанию положительный
        }
    
    review_lower = review_text.lower()
    topics = {}
    
    # Извлекаем темы и их тональность
    for category, keywords in THEME_CATEGORIES.items():
        # Ищем ключевые слова с учетом падежей и множественного числа
        found_keywords = []
        for kw in keywords:
            # Для многословных фраз (например, "классный руководитель")
            if ' ' in kw:
                # Ищем фразу целиком
                pattern = r'(?:^|[^а-яё])' + re.escape(kw) + r'(?=[^а-яё]|$)'
                if re.search(pattern, review_lower):
                    found_keywords.append(kw)
            else:
                # Для одиночных слов ищем слово, начинающееся с ключевого слова
                # Это позволяет находить слова в разных падежах (учитель, учителя, учителей)
                # Паттерн: начало строки или не-буква, затем ключевое слово + возможные окончания, затем не-буква или конец
                # Используем более гибкий поиск: слово должно начинаться с ключевого слова
                pattern = r'(?:^|[^а-яё])' + re.escape(kw) + r'[а-яё]*(?=[^а-яё]|$)'
                if re.search(pattern, review_lower):
                    found_keywords.append(kw)
        
        if found_keywords:
            # Находим контекст вокруг найденных ключевых слов
            sentences = re.split(r'[.!?]\s+', review_text)
            relevant_sentences = []
            
            for sentence in sentences:
                sentence_lower = sentence.lower()
                # Проверяем, что в предложении есть хотя бы одно ключевое слово
                # Используем тот же паттерн, что и при поиске ключевых слов (без \b, т.к. не работает с русским)
                found_in_sentence = False
                for kw in found_keywords:
                    if ' ' in kw:
                        # Для фраз ищем точное совпадение
                        if kw in sentence_lower:
                            found_in_sentence = True
                            break
                    else:
                        # Для одиночных слов используем тот же паттерн
                        pattern = r'(?:^|[^а-яё])' + re.escape(kw) + r'[а-яё]*(?=[^а-яё]|$)'
                        if re.search(pattern, sentence_lower):
                            found_in_sentence = True
                            break
                
                if found_in_sentence:
                    relevant_sentences.append(sentence)
            
            if relevant_sentences:
                context_text = ' '.join(relevant_sentences)
            else:
                # Если не нашли предложений, используем весь текст
                context_text = review_text
            
            # Анализируем тональность для этой категории
            sentiment = analyze_text_sentiment(context_text)
            
            # УБРАНА нейтральная оценка - только pos или neg
            # Улучшенный анализ с учетом контекста
            context_lower = context_text.lower()
            
            # Расширенный список индикаторов для более точного определения
            positive_indicators = [
                'хорош', 'отличн', 'прекрасн', 'замечательн', 'преобразил', 'улучшил', 
                'нравится', 'доволен', 'рекомендую', 'лучш', 'качествен', 'профессионал',
                'успех', 'рад', 'спасибо', 'благодар'
            ]
            negative_indicators = [
                'плох', 'ужасн', 'проблем', 'не нравится', 'недоволен', 'жалоб',
                'отрав', 'нельзя', 'не рекомендую', 'разочарован'
            ]
            
            # Подсчитываем индикаторы в контексте
            positive_count = sum(1 for ind in positive_indicators if ind in context_lower)
            negative_count = sum(1 for ind in negative_indicators if ind in context_lower)
            
            # Определяем предварительную тональность на основе sentiment и индикаторов
            if sentiment > 0 or (sentiment == 0 and positive_count > negative_count):
                topic_sentiment = "pos"
            elif sentiment < 0 or (sentiment == 0 and negative_count > positive_count):
                topic_sentiment = "neg"
            else:
                # Если неопределенно (sentiment == 0 и равное количество индикаторов)
                topic_sentiment = "pos"  # По умолчанию положительный
            
            # ВАЖНО: Корректируем тональность на основе rating (приоритет rating)
            # Это исправляет случаи, когда алгоритм неправильно определяет тональность
            # 
            # Пример проблемы: отзыв с rating=1, текст "площадка старая и маленькая"
            # Алгоритм может определить "инфраструктура": "pos" из-за недостатка 
            # отрицательных слов в словаре, но rating=1 явно указывает на негатив.
            # 
            # Правило: rating <= 2 → все темы "neg" (если нет явных положительных индикаторов)
            #          rating >= 4 → все темы "pos" (если нет явных отрицательных индикаторов)
            #          rating == 3  → оставляем как есть
            if rating is not None:
                try:
                    rating_int = int(rating)
                    # Определяем знак из rating
                    if rating_int <= 2:
                        # Низкий рейтинг (1-2) → все темы негативные
                        # Исключение: если есть очень явные положительные индикаторы
                        if positive_count >= 3 and negative_count == 0:
                            # Явно положительный контекст - оставляем как есть
                            pass
                        else:
                            topic_sentiment = "neg"
                    elif rating_int >= 4:
                        # Высокий рейтинг (4-5) → темы положительные
                        # Исключение: если есть очень явные отрицательные индикаторы
                        if negative_count >= 3 and positive_count == 0:
                            # Явно отрицательный контекст - оставляем как есть
                            pass
                        else:
                            topic_sentiment = "pos"
                    # rating == 3: оставляем как есть (нейтральный)
                except (ValueError, TypeError):
                    # Если rating не распознан, оставляем как есть
                    pass
            
            topics[category] = topic_sentiment
    
    # Определяем общую тональность
    # ПРИОРИТЕТ: rating > анализ текста
    # УБРАНА нейтральная оценка
    if rating is not None:
        sentiment = get_sentiment_from_rating(rating)
        if sentiment is not None:
            if sentiment > 0:
                overall = "pos"
            elif sentiment < 0:
                overall = "neg"
            else:
                # rating == 3 (нейтральный) - склоняемся к положительному
                overall = "pos"
        else:
            # Если rating не распознан, используем анализ текста
            sentiment = analyze_text_sentiment(review_text)
            overall = "pos" if sentiment >= 0 else "neg"  # >= 0 → pos
    else:
        # Нет rating - используем анализ текста
        sentiment = analyze_text_sentiment(review_text)
        overall = "pos" if sentiment >= 0 else "neg"  # >= 0 → pos
    
    return {
        "topics": topics,
        "overall": overall
    }

def aggregate_school_metrics(reviews_data):
    """
    Агрегирует тематические признаки качества по школам.
    
    ФОРМИРУЕМЫЕ МЕТРИКИ (для каждой темы и школы):
    
    1. topic_cnt_<topic> (int):
       - Количество отзывов, в которых упоминается данная тема
       - Формула: количество отзывов с полем topics[<topic>]
       - Пример: topic_cnt_учителя = 25 означает, что 25 отзывов упоминали учителей
       
    2. topic_neg_share_<topic> (float, 0.0-1.0):
       - Доля негативных отзывов среди всех отзывов по теме
       - Формула: количество отзывов с topics[<topic>] == "neg" / topic_cnt_<topic>
       - Пример: topic_neg_share_учителя = 0.08 означает, что 8% отзывов об учителях негативные
       - 0.0 = все отзывы положительные, 1.0 = все отзывы негативные
       
    3. topic_sentiment_<topic> (float, -1.0 до +1.0):
       - Средняя тональность отзывов по теме
       - Формула: сумма sentiment_num / topic_cnt_<topic>
       - где sentiment_num: +1 для "pos", -1 для "neg"
       - Пример: topic_sentiment_учителя = 0.24 означает слабоположительную тональность
       - +1.0 = все отзывы положительные, -1.0 = все отзывы негативные, 0.0 = смешанные
    
    ГОДОВЫЕ МЕТРИКИ (yearly_school_metrics):
    - Ключ: "{school_id}_{year}" (например, "67_2022", "67_2023", "67_2024", "67_2025")
    - Период: 2022, 2023, 2024, 2025
    - Структура каждого элемента (плоский формат, как в school_metrics):
      {
        "year": 2022,
        "school_id": "67",
        "topic_cnt_учителя": 5,              // количество отзывов по теме за год
        "topic_neg_share_учителя": 0.2,      // доля негативных отзывов (0.0-1.0)
        "topic_pos_cnt_учителя": 4,          // количество положительных отзывов
        "topic_neg_cnt_учителя": 1,          // количество негативных отзывов
        "topic_sentiment_учителя": 0.6,      // средняя тональность (-1.0 до +1.0)
        "topic_cnt_еда": 3,
        "topic_neg_share_еда": 0.33,
        "topic_pos_cnt_еда": 2,
        "topic_neg_cnt_еда": 1,
        "topic_sentiment_еда": -0.33,
        ...
      }
    - Формат идентичен school_metrics, но с дополнительными полями year и school_id
    - Все темы присутствуют в каждой записи (если тема не упоминалась, значения = 0 или None)
    
    Args:
        reviews_data: список обработанных отзывов с полями topics, overall, date, school_id
        
    Returns:
        tuple: (school_metrics, yearly_school_metrics, overall_school_metrics)
        - school_metrics: dict {school_id: {topic_cnt_<topic>: int, topic_neg_share_<topic>: float, ...}}
        - yearly_school_metrics: list [{year: int, school_id: str, topic_<topic>_cnt: int, ...}, ...]
        - overall_school_metrics: list [{school_id: str, topic_<topic>_cnt: int, ...}, ...] - общая сводка по всем годам
    """
    # Метрики по всем школам (общие)
    school_metrics = defaultdict(lambda: defaultdict(lambda: {
        'total': 0,
        'negative': 0,
        'positive': 0,
        'sentiment_sum': 0
    }))
    
    # Метрики по годам (2022, 2023, 2024, 2025)
    yearly_metrics = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {
        'total': 0,
        'negative': 0,
        'positive': 0,  # Количество положительных отзывов
        'sentiment_sum': 0
    })))
    
    # Годы для анализа
    target_years = [2022, 2023, 2024, 2025]
    
    for review in reviews_data:
        # Проверяем, что review не None
        if review is None:
            continue
        
        school_id = review.get('school_id')
        if not school_id:
            continue
        
        # Парсим дату
        review_year = None
        date_str = review.get('date', '')
        if date_str:
            try:
                review_date = datetime.strptime(date_str, '%Y-%m-%d')
                review_year = review_date.year
            except (ValueError, TypeError):
                review_year = None
        
        review_id = review.get('review_id', '')
        topics = review.get('topics', {})
        
        # Проверяем, что topics это словарь
        if not isinstance(topics, dict):
            topics = {}
        
        overall = review.get('overall', 'pos')
        
        # Преобразуем overall в числовое значение (только pos/neg)
        overall_num = 1 if overall == 'pos' else -1
        
        # Обрабатываем каждую тему
        for topic, sentiment in topics.items():
            # Пропускаем, если sentiment не "pos" или "neg"
            if sentiment not in ['pos', 'neg']:
                continue
            
            # Общие метрики (по всем годам)
            metrics = school_metrics[school_id][topic]
            metrics['total'] += 1
            
            if sentiment == 'neg':
                metrics['negative'] += 1
            elif sentiment == 'pos':
                metrics['positive'] = metrics.get('positive', 0) + 1
            
            sentiment_num = 1 if sentiment == 'pos' else -1
            metrics['sentiment_sum'] += sentiment_num
            
            # Годовые метрики (только для целевых годов)
            if review_year in target_years:
                year_metrics = yearly_metrics[school_id][review_year][topic]
                year_metrics['total'] += 1
                
                if sentiment == 'neg':
                    year_metrics['negative'] += 1
                elif sentiment == 'pos':
                    year_metrics['positive'] += 1
                
                year_metrics['sentiment_sum'] += sentiment_num
    
    # Формируем итоговые метрики (общие)
    result = {}
    for school_id, topics_dict in school_metrics.items():
        school_result = {}
        for topic, metrics in topics_dict.items():
            total = metrics['total']
            if total > 0:
                school_result[f'topic_cnt_{topic}'] = total
                school_result[f'topic_neg_share_{topic}'] = metrics['negative'] / total
                school_result[f'topic_pos_cnt_{topic}'] = metrics.get('positive', 0)
                school_result[f'topic_neg_cnt_{topic}'] = metrics['negative']
                school_result[f'topic_sentiment_{topic}'] = metrics['sentiment_sum'] / total
            else:
                school_result[f'topic_cnt_{topic}'] = 0
                school_result[f'topic_neg_share_{topic}'] = None
                school_result[f'topic_pos_cnt_{topic}'] = 0
                school_result[f'topic_neg_cnt_{topic}'] = 0
                school_result[f'topic_sentiment_{topic}'] = None
        
        result[school_id] = school_result
    
    # Формируем годовые метрики в плоском формате (как school_metrics)
    # Получаем все возможные темы из всех школ для единообразия
    all_topics = set()
    for school_id, years_dict in yearly_metrics.items():
        for year, topics_dict in years_dict.items():
            all_topics.update(topics_dict.keys())
    
    # Если нет тем в yearly_metrics, берем из THEME_CATEGORIES
    if not all_topics:
        all_topics = set(THEME_CATEGORIES.keys())
    
    all_topics = sorted(all_topics)
    
    yearly_result = []
    for school_id, years_dict in yearly_metrics.items():
        for year in sorted(years_dict.keys()):  # Сортируем годы для консистентности
            year_data = {
                'year': year,
                'school_id': school_id
            }
            
            # Добавляем метрики по каждой теме в плоском формате
            # Добавляем все темы, даже если они не упоминались в этом году
            topics_dict = years_dict[year]
            for topic in all_topics:
                if topic in topics_dict:
                    metrics = topics_dict[topic]
                    total = metrics['total']
                    if total > 0:
                        year_data[f'topic_{topic}_cnt'] = total
                        year_data[f'topic_{topic}_neg_share'] = metrics['negative'] / total
                        year_data[f'topic_{topic}_pos_cnt'] = metrics['positive']
                        year_data[f'topic_{topic}_neg_cnt'] = metrics['negative']
                        year_data[f'topic_{topic}_sentiment'] = metrics['sentiment_sum'] / total
                    else:
                        year_data[f'topic_{topic}_cnt'] = 0
                        year_data[f'topic_{topic}_neg_share'] = None
                        year_data[f'topic_{topic}_pos_cnt'] = 0
                        year_data[f'topic_{topic}_neg_cnt'] = 0
                        year_data[f'topic_{topic}_sentiment'] = None
                else:
                    # Если тема не упоминалась в этом году для этой школы
                    year_data[f'topic_{topic}_cnt'] = 0
                    year_data[f'topic_{topic}_neg_share'] = None
                    year_data[f'topic_{topic}_pos_cnt'] = 0
                    year_data[f'topic_{topic}_neg_cnt'] = 0
                    year_data[f'topic_{topic}_sentiment'] = None
            
            yearly_result.append(year_data)
    
    # Сортируем по school_id и year для удобства
    yearly_result.sort(key=lambda x: (x['school_id'], x['year']))
    
    # Формируем общую сводку для каждой школы (в том же формате, что и yearly_result, но без года)
    overall_result = []
    for school_id, school_result in result.items():
        overall_data = {
            'school_id': school_id
        }
        
        # Добавляем метрики по каждой теме в том же формате, что и yearly_result
        for topic in all_topics:
            topic_key = f'topic_cnt_{topic}'
            if topic_key in school_result:
                overall_data[f'topic_{topic}_cnt'] = school_result[topic_key]
                overall_data[f'topic_{topic}_neg_share'] = school_result.get(f'topic_neg_share_{topic}')
                overall_data[f'topic_{topic}_pos_cnt'] = school_result.get(f'topic_pos_cnt_{topic}', 0)
                overall_data[f'topic_{topic}_neg_cnt'] = school_result.get(f'topic_neg_cnt_{topic}', 0)
                overall_data[f'topic_{topic}_sentiment'] = school_result.get(f'topic_sentiment_{topic}')
            else:
                # Если тема не упоминалась для этой школы
                overall_data[f'topic_{topic}_cnt'] = 0
                overall_data[f'topic_{topic}_neg_share'] = None
                overall_data[f'topic_{topic}_pos_cnt'] = 0
                overall_data[f'topic_{topic}_neg_cnt'] = 0
                overall_data[f'topic_{topic}_sentiment'] = None
        
        overall_result.append(overall_data)
    
    # Сортируем по school_id для удобства
    overall_result.sort(key=lambda x: x['school_id'])
    
    return result, yearly_result, overall_result

def process_reviews(input_file_path, output_file_path):
    """
    Обрабатывает отзывы и сохраняет результаты в выходной файл.
    
    Args:
        input_file_path: Путь к входному JSON файлу с отзывами
        output_file_path: Путь к выходному JSON файлу
    """
    # Читаем входной файл
    print(f"[INFO] Загрузка данных из: {input_file_path}")
    with open(input_file_path, "r", encoding='utf-8') as f:
        input_data = json.load(f)
    
    # Сохраняем метаданные из входного файла (если есть)
    output_data = {
        'resource': input_data.get('resource', ''),
        'topic': input_data.get('topic', ''),
        'parse_date': input_data.get('parse_date', ''),
        'reviews': []
    }
    
    # Обрабатываем каждый отзыв
    reviews = input_data.get('reviews', [])
    total_reviews = len(reviews)
    
    print(f"[INFO] Найдено отзывов для обработки: {total_reviews}")
    print(f"[INFO] Используется БЕСПЛАТНАЯ версия обработки (без API)")
    
    processed_reviews = []
    
    for idx, review_info in enumerate(reviews, 1):
        # Проверяем, что review_info не None
        if review_info is None:
            print(f"[WARN] Отзыв {idx}/{total_reviews}: пропущен (review_info is None)")
            continue
        
        review_text = review_info.get('text', '') or ''
        rating = review_info.get('rating')
        
        # Проверяем, что review_text не None
        if review_text is None:
            review_text = ''
        
        if not review_text:
            print(f"[WARN] Отзыв {idx}/{total_reviews}: пропущен (нет текста)")
            # Добавляем отзыв без анализа (по умолчанию положительный)
            output_review = review_info.copy()
            output_review['topics'] = {}
            output_review['overall'] = 'pos'
            output_data['reviews'].append(output_review)
            processed_reviews.append(output_review)
            continue
        
        if idx % 100 == 0:
            print(f"[INFO] Обработано {idx}/{total_reviews} отзывов...")
        
        try:
            # Обрабатываем отзыв
            analysis = recognize_review_free(review_text, rating)
            
            # Проверяем, что analysis не None и содержит нужные поля
            if analysis is None:
                raise ValueError("recognize_review_free вернул None")
            if not isinstance(analysis, dict):
                raise ValueError(f"recognize_review_free вернул не словарь: {type(analysis)}")
            if 'topics' not in analysis or 'overall' not in analysis:
                raise ValueError(f"Неполный результат анализа: {analysis}")
            
            # Создаём выходной отзыв с добавленными полями
            output_review = review_info.copy()
            output_review['topics'] = analysis.get('topics', {})
            output_review['overall'] = analysis.get('overall', 'pos')
            
            # Для обратной совместимости добавляем main_idea (строка)
            if analysis['topics']:
                main_idea_parts = []
                for topic, sentiment in analysis['topics'].items():
                    if sentiment == 'pos':
                        main_idea_parts.append(f"{topic} хороший")
                    elif sentiment == 'neg':
                        main_idea_parts.append(f"{topic} плохой")
                output_review['main_idea'] = ', '.join(main_idea_parts[:3])
            else:
                output_review['main_idea'] = "хорошая школа" if analysis['overall'] == 'pos' else "плохая школа"
            
            # Для обратной совместимости добавляем tonality
            tonality_map = {'pos': 'Положительный', 'neg': 'Отрицательный'}
            output_review['tonality'] = tonality_map.get(analysis['overall'], 'Положительный')
            
            output_data['reviews'].append(output_review)
            processed_reviews.append(output_review)
            
        except Exception as e:
            print(f"[ERROR] Ошибка при обработке отзыва {idx}/{total_reviews}: {e}")
            # Добавляем отзыв без анализа в случае ошибки (по умолчанию положительный)
            output_review = review_info.copy()
            output_review['topics'] = {}
            output_review['overall'] = 'pos'
            output_review['main_idea'] = ''
            output_review['tonality'] = 'Положительный'
            output_data['reviews'].append(output_review)
            processed_reviews.append(output_review)
        
        # Сохраняем после каждых 50 отзывов (чтобы не потерять данные)
        if idx % 50 == 0:
            save_output_data(output_file_path, output_data)
    
    # Вычисляем агрегированные метрики по школам
    print(f"[INFO] Вычисление агрегированных метрик по школам...")
    school_metrics, yearly_school_metrics, overall_school_metrics = aggregate_school_metrics(processed_reviews)
    output_data['school_metrics'] = school_metrics
    output_data['yearly_school_metrics'] = yearly_school_metrics
    output_data['overall_school_metrics'] = overall_school_metrics
    
    # Финальное сохранение
    save_output_data(output_file_path, output_data)
    
    print(f"[OK] Результаты сохранены в: {output_file_path}")
    print(f"[OK] Всего обработано отзывов: {len(output_data['reviews'])}")
    print(f"[OK] Обработано школ: {len(school_metrics)}")
    print(f"[OK] Создано годовых записей: {len(yearly_school_metrics)}")
    print(f"[OK] Создано общих сводок: {len(overall_school_metrics)}")

def save_output_data(output_file_path, output_data):
    """Сохраняет данные в выходной файл"""
    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
    with open(output_file_path, "w", encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    print("=" * 80)
    print("ОБРАБОТКА ОТЗЫВОВ О ШКОЛАХ (БЕСПЛАТНАЯ ВЕРСИЯ)")
    print("=" * 80)
    process_reviews(INPUT_REVIEW_FILE, OUTPUT_REVIEW_FILE)
    print("=" * 80)
    print("ОБРАБОТКА ЗАВЕРШЕНА")
    print("=" * 80)
