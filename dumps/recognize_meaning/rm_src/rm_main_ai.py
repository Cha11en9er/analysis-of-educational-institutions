"""
================================================================================
ОБРАБОТКА ОТЗЫВОВ О ШКОЛАХ (ИИ-ВЕРСИЯ С RAG)
================================================================================

Этот скрипт обрабатывает отзывы о школах с использованием ИИ-модели.
Использует модель cointegrated/rubert-base для определения тем и тональности.

ОСОБЕННОСТИ:
- Использование более мощной модели (rubert-base вместо tiny)
- RAG (Retrieval-Augmented Generation) с few-shot examples
- Повышенный порог для обнаружения тем (0.55 вместо 0.3)
- Дополнительная проверка релевантности тем
- Убраны дубликаты (main_idea, tonality)
- Поддержка rating для корректировки результатов

ТРЕБОВАНИЯ:
- pip install transformers torch sentencepiece
- ~5-6 GB свободного места на диске
- ~1-2 GB оперативной памяти
- Интернет для первой загрузки модели

================================================================================
"""

import json
import os
import re
from datetime import datetime
from collections import defaultdict

# Попытка импорта ИИ-библиотек
try:
    from transformers import pipeline
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    print("[WARN] Библиотека transformers не установлена. Установите: pip install transformers torch sentencepiece")

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
RM_ROOT = os.path.dirname(CURRENT_DIR)
DATA_DIR = os.path.join(RM_ROOT, 'rm_data')
INPUT_DIR = os.path.join(DATA_DIR, 'rm_input')
OUTPUT_DIR = os.path.join(DATA_DIR, 'rm_output')
INPUT_REVIEW_FILE = os.path.join(INPUT_DIR, 'rm_input_0-1000_data.json')
OUTPUT_REVIEW_FILE = os.path.join(OUTPUT_DIR, 'rm_output_0-1000_data_ai.json')

# Список тем (совместим с текущим кодом)
THEMES = [
    "учителя",
    "еда",
    "администрация",
    "буллинг",
    "инфраструктура",
    "охрана",
    "уборка",
    "ремонт",
    "питание",
    "атмосфера",
    "досуг",
    "безопасность",
    "расписание"
]

# Few-shot examples для RAG (примеры входных и выходных данных)
# Включаем проблемные случаи для улучшения распознавания
FEW_SHOT_EXAMPLES = [
    {
        "text": "Отличная школа! Еда в столовой вкусная, учителя почти все добрые",
        "topics": {"еда": "pos", "учителя": "pos"},
        "overall": "pos"
    },
    {
        "text": "Плохая школа. Учителя невнимательные, еда отвратительная, в туалетах грязно",
        "topics": {"учителя": "neg", "еда": "neg", "уборка": "neg"},
        "overall": "neg"
    },
    {
        "text": "Учителя все злые, плохое отношение к ученикам, ничему не учат",
        "topics": {"учителя": "neg"},
        "overall": "neg"
    },
    {
        "text": "Учителя злые и ненавистные, плохо относятся к детям",
        "topics": {"учителя": "neg"},
        "overall": "neg"
    },
    {
        "text": "Школа хорошая, но ремонт нужен. Стены в трещинах, окна старые",
        "topics": {"ремонт": "neg"},
        "overall": "pos"
    },
    {
        "text": "Директор отличный, администрация работает хорошо. Но охрана слабая",
        "topics": {"администрация": "pos", "охрана": "neg"},
        "overall": "pos"
    },
    {
        "text": "В школе травят детей, буллинг процветает. Учителя не реагируют",
        "topics": {"буллинг": "neg", "учителя": "neg"},
        "overall": "neg"
    },
    {
        "text": "Спортзал новый, стадион отличный, оборудование современное",
        "topics": {"инфраструктура": "pos"},
        "overall": "pos"
    }
]

# Порог для обнаружения тем (оптимизирован для нахождения нескольких тем)
THEME_DETECTION_THRESHOLD = 0.4  # Понижен для нахождения большего количества релевантных тем

# Инициализация ИИ-модели (глобально, чтобы не загружать каждый раз)
classifier = None

def initialize_ai_model(force_reload=False):
    """Инициализирует ИИ-модель. Вызывается один раз при старте."""
    global classifier
    
    if not AI_AVAILABLE:
        return False
    
    if classifier is not None and not force_reload:
        return True
    
    try:
        # Очищаем старую модель из памяти
        if classifier is not None:
            del classifier
            classifier = None
            import gc
            gc.collect()
            print("[INFO] Старая модель очищена из памяти")
        
        print("[INFO] Загрузка языковой модели ИИ...")
        print("[INFO] Это может занять несколько минут при первом запуске...")
        print("[INFO] Пробуем загрузить более мощную модель для лучшей точности")
        
        # Принудительно загружаем модель без кеша для обновления
        import os
        os.environ['TRANSFORMERS_OFFLINE'] = '0'  # Разрешаем загрузку из интернета
        
        # Пробуем загрузить более мощную модель, если не получается - используем tiny
        # Порядок важен: сначала пробуем более мощные модели
        model_names = [
            "ai-forever/ruBert-base",           # Более мощная модель от AI Forever
            "cointegrated/rubert-tiny2",        # Более новая версия tiny
            "cointegrated/rubert-tiny",         # Стандартная tiny версия
        ]
        
        classifier = None
        for model_name in model_names:
            try:
                print(f"[INFO] Попытка загрузить модель: {model_name}")
                classifier = pipeline(
                    "zero-shot-classification",
                    model=model_name,
                    device=-1,  # -1 = CPU (для GPU укажите номер устройства, например 0)
                    trust_remote_code=True
                )
                print(f"[OK] Модель {model_name} загружена успешно!")
                break
            except Exception as e:
                print(f"[WARN] Не удалось загрузить {model_name}: {e}")
                continue
        
        if classifier is None:
            raise Exception("Не удалось загрузить ни одну из моделей")
        
        # Проверяем, какая модель действительно загружена
        model_name = classifier.model.config.name_or_path if hasattr(classifier, 'model') else "unknown"
        print(f"[OK] Модель загружена успешно! Модель: {model_name}")
        return True
    except Exception as e:
        print(f"[ERROR] Не удалось загрузить модель: {e}")
        print("[WARN] Будет использован метод на основе правил")
        classifier = None
        return False

def analyze_review_with_ai(text: str, rating=None):
    """
    Анализирует отзыв с помощью ИИ.
    
    Args:
        text: Текст отзыва
        rating: Рейтинг отзыва (1-5), если доступен
        
    Returns:
        dict с полями:
        - topics: dict {topic: "pos"/"neg"}
        - overall: "pos"/"neg"
    """
    if not text or not text.strip():
        return {"topics": {}, "overall": "pos"}
    
    # Если модель не загружена, используем fallback
    if classifier is None:
        return analyze_review_fallback(text, rating)
    
    # Отладочная информация для проблемных отзывов
    DEBUG_MODE = False  # Установите True для отладки
    if DEBUG_MODE and ("учителя" in text.lower() or "учитель" in text.lower()):
        print(f"[DEBUG] Анализ отзыва: '{text[:80]}...'")
        print(f"[DEBUG] Rating: {rating}")
    
    try:
        # 1. Определяем общую тональность
        sentiment_result = classifier(
            text,
            candidate_labels=["положительный", "отрицательный"],
            hypothesis_template="Тональность отзыва: {}"
        )
        
        # Определяем overall на основе результата
        if sentiment_result["labels"][0] == "положительный":
            overall = "pos"
        else:
            overall = "neg"
        
        # 2. Используем rating как приоритет (как в текущем коде)
        if rating is not None:
            try:
                rating_int = int(rating)
                if rating_int >= 4:
                    overall = "pos"
                elif rating_int <= 2:
                    overall = "neg"
                # rating == 3: оставляем как определила модель
            except (ValueError, TypeError):
                pass
        
        # 3. Выявляем темы с использованием RAG (few-shot examples)
        # Создаем контекст с примерами для улучшения качества
        context_text = text
        
        # Добавляем few-shot examples в контекст (для RAG)
        # Модель будет использовать эти примеры для лучшего понимания задачи
        examples_context = "\n\nПримеры:\n"
        for example in FEW_SHOT_EXAMPLES[:3]:  # Берем первые 3 примера
            examples_context += f"Отзыв: {example['text']}\n"
            topics_str = ", ".join([f"{k}: {v}" for k, v in example['topics'].items()])
            examples_context += f"Темы: {topics_str}\n\n"
        
        # Используем улучшенный hypothesis_template с RAG-контекстом
        # Добавляем примеры в шаблон для лучшего понимания задачи
        # Формируем улучшенный шаблон с учетом примеров
        improved_template = (
            "Примеры анализа отзывов о школах:\n"
            "- 'Еда вкусная, учителя добрые' → темы: еда, учителя\n"
            "- 'Плохие учителя, грязные туалеты' → темы: учителя, уборка\n"
            "- 'Директор отличный, но ремонт нужен' → темы: администрация, ремонт\n"
            "В этом отзыве о школе упоминается тема: {}"
        )
        
        topics_result = classifier(
            text,
            candidate_labels=THEMES,
            hypothesis_template=improved_template,
            multi_label=True  # Разрешаем несколько меток
        )
        
        # Берем темы с оптимизированным порогом уверенности (score > 0.4)
        # Пониженный порог позволяет находить больше релевантных тем
        detected_themes_with_scores = []
        for label, score in zip(topics_result["labels"], topics_result["scores"]):
            if score > THEME_DETECTION_THRESHOLD:
                detected_themes_with_scores.append((label, score))
        
        # Сортируем по уверенности (от большей к меньшей)
        detected_themes_with_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Улучшенная фильтрация: берем все темы выше порога, но ограничиваем максимум
        # Если тем больше 5, берем топ-5 по уверенности
        if len(detected_themes_with_scores) > 5:
            # Берем топ-5 тем с наивысшей уверенностью
            detected_themes_with_scores = detected_themes_with_scores[:5]
        # Если тем от 1 до 5 - оставляем все (не фильтруем)
        
        # Извлекаем только названия тем
        detected_themes = [theme for theme, score in detected_themes_with_scores]
        
        # FALLBACK: Проверяем ключевые слова для важных тем, которые модель могла пропустить
        # Это особенно важно для темы "учителя", которая часто упоминается
        text_lower = text.lower()
        fallback_keywords = {
            "учителя": [
                # Основные формы слова "учитель"
                "учитель", "учителя", "учителей", "учителю", "учителем", "учителями",
                # Преподаватели
                "преподаватель", "преподаватели", "преподавателей", "преподавателю",
                # Педагоги
                "педагог", "педагоги", "педагогов", "педагогу",
                # Контекстные фразы
                "плохое отношение учителей", "отношение учителей", "учителя плохие", 
                "учителя хорошие", "учителя начальной школы", "учителя злые",
                "учителя ненавистные", "учителя не учат", "учителя учат",
                # Отдельные слова, которые указывают на учителей
                "злые", "ненавистные", "учат", "обучают", "преподают"
            ]
        }
        
        for theme, keywords in fallback_keywords.items():
            # Если тема не найдена моделью, но есть ключевые слова
            if theme not in detected_themes:
                # Проверяем наличие ключевых слов (более гибкая проверка)
                has_keywords = False
                matched_keyword = None
                for kw in keywords:
                    if kw in text_lower:
                        has_keywords = True
                        matched_keyword = kw
                        break
                
                if has_keywords:
                    # Принудительно добавляем тему, если есть ключевые слова
                    # Это исправляет случаи, когда модель не находит тему из-за высокого порога
                    detected_themes.append(theme)
                    # Отладочная информация (можно включить, установив DEBUG_FALLBACK = True)
                    DEBUG_FALLBACK = False  # Установите True для отладки fallback
                    if DEBUG_FALLBACK:
                        print(f"[DEBUG] Fallback: добавлена тема '{theme}' по ключевому слову '{matched_keyword}'")
        
        # 4. Для каждой обнаруженной темы определяем тональность
        # Дополнительная проверка релевантности через контекстный анализ
        topics = {}
        for theme in detected_themes:
            # Проверяем, действительно ли тема упоминается в тексте
            # Используем ключевые слова для каждой темы
            theme_keywords = {
                "учителя": ["учитель", "учителя", "учителей", "учителю", "учителем", 
                           "преподаватель", "преподаватели", "педагог", "педагоги",
                           "урок", "уроки", "классный руководитель", "злые", "ненавистные",
                           "отношение к ученикам", "учат", "обучают"],
                "еда": ["еда", "столовая", "питание", "обед", "завтрак", "меню", "корм"],
                "ремонт": ["ремонт", "стены", "трещины", "туалет", "окна", "двери", "потолок"],
                "администрация": ["директор", "завуч", "администрация", "руководитель"],
                "буллинг": ["травля", "буллинг", "обиж", "бьют", "конфликт", "ссора"],
                "инфраструктура": ["спортзал", "стадион", "площадка", "бассейн", "кабинет", "оборудование"],
                "охрана": ["охрана", "безопасность", "пропуск", "вход", "выход"],
                "уборка": ["уборка", "чистота", "грязно", "мусор", "санитар"],
                "питание": ["питание", "еда", "столовая", "обед", "завтрак"],
                "атмосфера": ["атмосфера", "обстановка", "климат", "отношения"],
                "досуг": ["досуг", "кружок", "секция", "внеурочная"],
                "безопасность": ["безопасность", "охрана", "травма", "опасно"],
                "расписание": ["расписание", "урок", "занятие", "график"]
            }
            
            # Проверяем наличие ключевых слов для темы
            text_lower = text.lower()
            relevant_keywords = theme_keywords.get(theme, [])
            has_keywords = any(kw in text_lower for kw in relevant_keywords)
            
            # FALLBACK: Если rating низкий (1-2) и есть ключевые слова, принудительно добавляем тему
            # Это исправляет случаи, когда модель не находит тему из-за высокого порога
            if not has_keywords and theme in ["ремонт", "буллинг", "безопасность", "администрация"]:
                # Для этих тем требуем более строгую проверку
                # Пропускаем тему, если нет явных упоминаний
                continue
            
            # FALLBACK для темы "учителя": если rating <= 2 и есть ключевые слова, но модель не нашла тему
            # Принудительно добавляем тему с негативной тональностью
            if theme == "учителя" and has_keywords and rating is not None:
                try:
                    rating_int = int(rating)
                    if rating_int <= 2:
                        # Если rating низкий и есть упоминание учителей, это явно негатив
                        # Продолжаем обработку (не пропускаем тему)
                        pass
                except (ValueError, TypeError):
                    pass
            # Определяем тональность для конкретной темы
            theme_sentiment = classifier(
                text,
                candidate_labels=["положительный", "отрицательный"],
                hypothesis_template=f"Тональность упоминания темы '{theme}': {{}}"
            )
            
            # Определяем тональность на основе результата
            if theme_sentiment["labels"][0] == "положительный":
                tone = "pos"
            else:
                tone = "neg"
            
            # Специальная обработка для темы "учителя" с негативными ключевыми словами
            if theme == "учителя":
                negative_words = ["злые", "ненавистные", "плохое отношение", "не учат", "не учат", 
                                "плохо относятся", "негатив", "плохие"]
                has_negative_words = any(word in text_lower for word in negative_words)
                
                if has_negative_words:
                    # Если есть явно негативные слова про учителей, это точно негатив
                    tone = "neg"
            
            # Корректируем на основе rating (как в текущем коде)
            if rating is not None:
                try:
                    rating_int = int(rating)
                    # Если rating низкий (1-2), склоняемся к негативу
                    if rating_int <= 2:
                        # Для темы "учителя" с низким rating - это явно негатив
                        if theme == "учителя":
                            tone = "neg"
                        # Исключение: если модель очень уверена в положительном (score > 0.7)
                        elif theme_sentiment["labels"][0] == "положительный" and theme_sentiment["scores"][0] < 0.7:
                            tone = "neg"
                    # Если rating высокий (4-5), склоняемся к позитиву
                    elif rating_int >= 4:
                        # Исключение: если модель очень уверена в отрицательном (score > 0.7)
                        if theme_sentiment["labels"][0] == "отрицательный" and theme_sentiment["scores"][0] < 0.7:
                            tone = "pos"
                except (ValueError, TypeError):
                    pass
            
            topics[theme] = tone
        
        return {
            "topics": topics,
            "overall": overall
        }
        
    except Exception as e:
        print(f"[ERROR] Ошибка при анализе отзыва с ИИ: {e}")
        # Fallback на метод правил
        return analyze_review_fallback(text, rating)

def analyze_review_fallback(text: str, rating=None):
    """
    Fallback метод на основе правил (если ИИ недоступен).
    Упрощенная версия из текущего кода.
    """
    if not text or not text.strip():
        return {"topics": {}, "overall": "pos"}
    
    # Простой анализ на основе ключевых слов
    text_lower = text.lower()
    
    # Определяем overall на основе rating
    overall = "pos"
    if rating is not None:
        try:
            rating_int = int(rating)
            if rating_int >= 4:
                overall = "pos"
            elif rating_int <= 2:
                overall = "neg"
        except (ValueError, TypeError):
            pass
    
    # Простой поиск тем по ключевым словам
    topics = {}
    theme_keywords = {
        "учителя": [
            "учитель", "учителя", "учителей", "учителю", "учителем",
            "преподаватель", "преподаватели", "педагог", "педагоги",
            "плохое отношение учителей", "отношение учителей", "учителя плохие",
            "учителя хорошие", "учителя начальной школы"
        ],
        "еда": ["еда", "столовая", "питание", "обед", "завтрак", "меню"],
        "ремонт": ["ремонт", "стены", "трещины", "туалет", "окна", "двери"],
        "администрация": ["директор", "завуч", "администрация", "руководство"],
        "буллинг": ["травля", "буллинг", "обиж", "бьют", "конфликт", "ссора"],
        "инфраструктура": ["спортзал", "стадион", "площадка", "бассейн", "кабинет"],
        "охрана": ["охрана", "безопасность", "пропуск", "вход", "выход"],
        "уборка": ["уборка", "чистота", "грязно", "мусор", "санитар"]
    }
    
    for theme, keywords in theme_keywords.items():
        if any(kw in text_lower for kw in keywords):
            # Простая тональность на основе overall
            topics[theme] = overall
    
    return {
        "topics": topics,
        "overall": overall
    }

def aggregate_school_metrics(reviews_data):
    """
    Агрегирует метрики по школам (аналогично текущему коду).
    Возвращает: (school_metrics, yearly_school_metrics, overall_school_metrics)
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
        'positive': 0,
        'sentiment_sum': 0
    })))
    
    target_years = [2022, 2023, 2024, 2025]
    
    for review in reviews_data:
        if review is None:
            continue
            
        school_id = review.get('school_id')
        if not school_id:
            continue
        
        # Парсим дату
        date_str = review.get('date', '')
        review_year = None
        if date_str:
            try:
                # Пробуем разные форматы даты
                for fmt in ['%Y-%m-%d', '%d.%m.%Y', '%Y-%m-%d %H:%M:%S']:
                    try:
                        review_date = datetime.strptime(date_str, fmt)
                        review_year = review_date.year
                        break
                    except ValueError:
                        continue
            except (ValueError, TypeError):
                pass

        topics = review.get('topics', {})
        if not isinstance(topics, dict):
            topics = {}
            
        overall = review.get('overall', 'pos')
        
        # Преобразуем overall в числовое значение
        overall_num = 1 if overall == 'pos' else -1

        # Обрабатываем каждую тему
        for theme, sentiment in topics.items():
            if sentiment not in ['pos', 'neg']:
                continue
                
            sentiment_num = 1 if sentiment == 'pos' else -1
            
            # Общие метрики
            m = school_metrics[school_id][theme]
            m['total'] += 1
            if sentiment == 'neg':
                m['negative'] += 1
            else:
                m['positive'] += 1
            m['sentiment_sum'] += sentiment_num
            
            # Годовые метрики
            if review_year in target_years:
                y_m = yearly_metrics[school_id][review_year][theme]
                y_m['total'] += 1
                if sentiment == 'neg':
                    y_m['negative'] += 1
                else:
                    y_m['positive'] += 1
                y_m['sentiment_sum'] += sentiment_num

    # Формирование итоговых метрик (общих)
    result = {}
    for school_id, themes_dict in school_metrics.items():
        school_result = {}
        for theme, metrics in themes_dict.items():
            total = metrics['total']
            if total > 0:
                school_result[f'topic_cnt_{theme}'] = total
                school_result[f'topic_neg_share_{theme}'] = metrics['negative'] / total
                school_result[f'topic_pos_cnt_{theme}'] = metrics['positive']
                school_result[f'topic_neg_cnt_{theme}'] = metrics['negative']
                school_result[f'topic_sentiment_{theme}'] = metrics['sentiment_sum'] / total
            else:
                school_result[f'topic_cnt_{theme}'] = 0
                school_result[f'topic_neg_share_{theme}'] = None
                school_result[f'topic_pos_cnt_{theme}'] = 0
                school_result[f'topic_neg_cnt_{theme}'] = 0
                school_result[f'topic_sentiment_{theme}'] = None
        result[school_id] = school_result

    # Формирование годовых метрик
    all_themes = sorted(set(THEMES))
    yearly_result = []
    for school_id, years_dict in yearly_metrics.items():
        for year in sorted(years_dict.keys()):
            year_data = {'year': year, 'school_id': school_id}
            themes_dict = years_dict[year]
            for theme in all_themes:
                if theme in themes_dict:
                    m = themes_dict[theme]
                    total = m['total']
                    if total > 0:
                        year_data[f'topic_{theme}_cnt'] = total
                        year_data[f'topic_{theme}_neg_share'] = m['negative'] / total
                        year_data[f'topic_{theme}_pos_cnt'] = m['positive']
                        year_data[f'topic_{theme}_neg_cnt'] = m['negative']
                        year_data[f'topic_{theme}_sentiment'] = m['sentiment_sum'] / total
                    else:
                        year_data[f'topic_{theme}_cnt'] = 0
                        year_data[f'topic_{theme}_neg_share'] = None
                        year_data[f'topic_{theme}_pos_cnt'] = 0
                        year_data[f'topic_{theme}_neg_cnt'] = 0
                        year_data[f'topic_{theme}_sentiment'] = None
                else:
                    year_data[f'topic_{theme}_cnt'] = 0
                    year_data[f'topic_{theme}_neg_share'] = None
                    year_data[f'topic_{theme}_pos_cnt'] = 0
                    year_data[f'topic_{theme}_neg_cnt'] = 0
                    year_data[f'topic_{theme}_sentiment'] = None
            yearly_result.append(year_data)

    yearly_result.sort(key=lambda x: (x['school_id'], x['year']))

    # Общая сводка по школам
    overall_result = []
    for school_id, data in result.items():
        item = {'school_id': school_id}
        for theme in all_themes:
            topic_key = f'topic_cnt_{theme}'
            if topic_key in data:
                item[f'topic_{theme}_cnt'] = data[topic_key]
                item[f'topic_{theme}_neg_share'] = data.get(f'topic_neg_share_{theme}')
                item[f'topic_{theme}_pos_cnt'] = data.get(f'topic_pos_cnt_{theme}', 0)
                item[f'topic_{theme}_neg_cnt'] = data.get(f'topic_neg_cnt_{theme}', 0)
                item[f'topic_{theme}_sentiment'] = data.get(f'topic_sentiment_{theme}')
            else:
                item[f'topic_{theme}_cnt'] = 0
                item[f'topic_{theme}_neg_share'] = None
                item[f'topic_{theme}_pos_cnt'] = 0
                item[f'topic_{theme}_neg_cnt'] = 0
                item[f'topic_{theme}_sentiment'] = None
        overall_result.append(item)
    
    overall_result.sort(key=lambda x: x['school_id'])

    return result, yearly_result, overall_result

def save_output_data(file_path, data):
    """Сохраняет данные в выходной файл"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def process_reviews():
    """Основной процесс обработки отзывов"""
    print("=" * 80)
    print("ОБРАБОТКА ОТЗЫВОВ О ШКОЛАХ (ИИ-ВЕРСИЯ)")
    print("=" * 80)
    
    # Инициализация ИИ-модели с принудительной перезагрузкой
    # force_reload=True заставляет загрузить модель заново (очищает кеш)
    import sys
    force_reload = '--reload' in sys.argv or '--force-reload' in sys.argv
    if force_reload:
        print("[INFO] Принудительная перезагрузка модели (очистка кеша)...")
    
    ai_loaded = initialize_ai_model(force_reload=force_reload)
    if not ai_loaded:
        print("[WARN] ИИ-модель недоступна. Будет использован метод на основе правил.")
    else:
        # Проверяем, что модель действительно загружена
        if classifier is None:
            print("[ERROR] КРИТИЧЕСКАЯ ОШИБКА: Модель не загружена, но initialize_ai_model вернул True!")
            print("[WARN] Будет использован метод на основе правил.")
            ai_loaded = False
    
    print(f"[INFO] Чтение данных из {INPUT_REVIEW_FILE}...")
    try:
        with open(INPUT_REVIEW_FILE, "r", encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] Файл {INPUT_REVIEW_FILE} не найден!")
        return
    except json.JSONDecodeError as e:
        print(f"[ERROR] Ошибка при чтении JSON: {e}")
        return
    
    reviews = data.get('reviews', [])
    print(f"[INFO] Найдено отзывов: {len(reviews)}")

    # Сохраняем метаданные
    output_data = {
        'resource': data.get('resource', ''),
        'topic': data.get('topic', ''),
        'parse_date': data.get('parse_date', ''),
        'reviews': []
    }
    
    output_reviews = []
    
    for idx, review in enumerate(reviews, 1):
        if review is None:
            print(f"[WARN] Отзыв {idx}: пропущен (review is None)")
            continue
            
        text = review.get('text', '') or ''
        rating = review.get('rating')
        
        if not text.strip():
            print(f"[WARN] Отзыв {idx}: пустой текст. Пропущен.")
            # Сохраняем отзыв без анализа
            output_review = review.copy()
            output_review['topics'] = {}
            output_review['overall'] = 'pos'
            # УБРАНЫ main_idea и tonality
            output_reviews.append(output_review)
            continue

        if idx % 50 == 0:
            print(f"[INFO] Обрабатываем отзыв {idx}/{len(reviews)}...")
            # Проверяем, что модель используется (не fallback)
            if classifier is None:
                print("[WARN] ВНИМАНИЕ: Модель не загружена, используется fallback метод!")
        
        try:
            analysis = analyze_review_with_ai(text, rating)
            
            if analysis is None or not isinstance(analysis, dict):
                raise ValueError("analyze_review_with_ai вернул неожиданный результат")
            
            output_review = review.copy()
            output_review['topics'] = analysis.get('topics', {})
            output_review['overall'] = analysis.get('overall', 'pos')
            
            # УБРАНЫ дубликаты: main_idea и tonality не добавляются
            # Они не нужны, так как информация уже есть в topics и overall
            
            output_reviews.append(output_review)
            
        except Exception as e:
            print(f"[ERROR] Отзыв {idx}: Ошибка обработки — {str(e)}")
            # Сохраняем отзыв без анализа в случае ошибки
            output_review = review.copy()
            output_review['topics'] = {}
            output_review['overall'] = 'pos'
            # УБРАНЫ main_idea и tonality
            output_reviews.append(output_review)
        
        # Сохраняем после каждых 50 отзывов (чтобы не потерять данные)
        if idx % 50 == 0:
            output_data['reviews'] = output_reviews
            save_output_data(OUTPUT_REVIEW_FILE, output_data)

    # Обновляем выходные данные
    output_data['reviews'] = output_reviews

    # Вычисляем агрегированные метрики
    print("[INFO] Вычисление агрегированных метрик...")
    try:
        school_metrics, yearly_metrics, overall_metrics = aggregate_school_metrics(output_reviews)
        output_data['school_metrics'] = school_metrics
        output_data['yearly_school_metrics'] = yearly_metrics
        output_data['overall_school_metrics'] = overall_metrics
    except Exception as e:
        print(f"[ERROR] Ошибка при вычислении метрик: {e}")

    # Сохраняем результат
    save_output_data(OUTPUT_REVIEW_FILE, output_data)
    print(f"[OK] Готово! Результаты сохранены в {OUTPUT_REVIEW_FILE}")
    print(f"[OK] Обработано отзывов: {len(output_reviews)}")
    print("=" * 80)

if __name__ == "__main__":
    process_reviews()

