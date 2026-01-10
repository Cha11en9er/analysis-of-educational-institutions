#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер отзывов школ 2ГИС на Selenium.
Читает ссылки из файла со списком школ и сохраняет все отзывы в один файл:

reviews: [{ school_id, date, text, likes_count }]

Сохраняет все отзывы в файл: 2gis_reviews_data/2gis_scools_reviews.json
"""

import json
import os
import re
import time
from datetime import datetime
from typing import Dict, Any, List

import pyautogui
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver import ActionChains


# Пути относительно текущего файла
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TGIS_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
DATA_DIR = os.path.join(TGIS_ROOT, "2gis_data")
OUTPUT_DIR = os.path.join(DATA_DIR, "tgis_output")
REVIEWS_OUTPUT_FILE = os.path.join(OUTPUT_DIR, "2gis_school_reviews.json")


def setup_driver() -> webdriver.Chrome:
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2,
    }
    chrome_options.add_experimental_option("prefs", prefs)
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


def convert_date_to_postgresql_format(date_str: str) -> str:
    """
    Преобразует дату из русского формата в формат YYYY-MM-DD для PostgreSQL.
    
    Примеры входных форматов:
    - "26 ноября 2015"
    - "1 сентября 2018"
    - "11 июня 2025, отредактирован"
    - "16 февраля 2024, отредактирован"
    - "" (пустая строка)
    
    Returns:
        Строка в формате YYYY-MM-DD или пустая строка, если дата не распознана
    """
    if not date_str or not date_str.strip():
        return ""
    
    # Убираем "отредактирован" и лишние пробелы
    date_str = date_str.strip()
    if ", отредактирован" in date_str:
        date_str = date_str.replace(", отредактирован", "").strip()
    
    # Словарь месяцев
    months = {
        'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
        'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
        'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
    }
    
    try:
        # Парсим формат "день месяц год"
        # Пример: "26 ноября 2015"
        parts = date_str.split()
        if len(parts) >= 3:
            day = int(parts[0])
            month_name = parts[1].lower()
            year = int(parts[2])
            
            if month_name in months:
                month = months[month_name]
                # Формируем дату в формате YYYY-MM-DD
                return f"{year:04d}-{month:02d}-{day:02d}"
    except (ValueError, IndexError):
        pass
    
    # Если не удалось распарсить, возвращаем пустую строку
    return ""


def wait_text_or_empty(driver: webdriver.Chrome, by: By, locator: str, timeout: int = 10) -> str:
    try:
        el = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, locator)))
        text = el.text.strip()
        return text
    except TimeoutException:
        return ""


def scroll_page_with_pyautogui(duration: float = 3.0, scroll_distance: int = 3000, scroll_step: int = 20) -> None:
    """
    Прокручивает страницу вниз с помощью pyautogui.
    Перемещает курсор в правую середину окна и медленно прокручивает вниз.
    
    Args:
        duration: Длительность прокрутки в секундах (по умолчанию 3 секунды)
        scroll_distance: Расстояние прокрутки в пикселях (по умолчанию 3000)
        scroll_step: Размер одного шага прокрутки в пикселях (по умолчанию 20)
                    Больше значение = быстрее прокрутка, но менее плавно
                    Меньше значение = медленнее прокрутка, но более плавно
    
    Returns:
        None
    """
    try:
        # Пауза перед началом прокрутки
        time.sleep(0.5)
        
        # Получаем размеры экрана
        screen_width, screen_height = pyautogui.size()
        
        # Вычисляем координаты правой середины экрана
        # Правая треть экрана, по вертикали - середина
        target_x = int(screen_width * 0.25)  # Правая треть
        target_y = int(screen_height * 0.5)    # Середина по вертикали
        
        # Быстро перемещаем курсор в целевую позицию
        pyautogui.moveTo(target_x, target_y, duration=0.1)
        time.sleep(0.1)  # Небольшая пауза после перемещения
        
        # Вычисляем количество шагов прокрутки
        steps = max(1, int(scroll_distance / scroll_step))  # Минимум 1 шаг
        step_duration = duration / steps if steps > 0 else 0
        
        # Прокручиваем вниз
        for i in range(steps):
            pyautogui.scroll(-scroll_step)  # Прокрутка вниз (отрицательное значение)
            if step_duration > 0:
                time.sleep(step_duration)
        
        time.sleep(1.0)  # Пауза после прокрутки для загрузки динамического контента
        
    except Exception as e:
        pass




def extract_reviews_from_json(html: str) -> List[Dict[str, Any]]:
    """Извлекает отзывы из JSON данных в HTML"""
    reviews_data = []
    processed_texts = set()  # Для избежания дубликатов
    
    # Сначала пытаемся найти JSON в script тегах
    script_pattern = r'<script[^>]*type\s*=\s*["\']application/json["\'][^>]*>(.*?)</script>'
    script_matches = re.finditer(script_pattern, html, re.DOTALL | re.IGNORECASE)
    
    for script_match in script_matches:
        script_content = script_match.group(1)
        try:
            # Пытаемся распарсить JSON
            data = json.loads(script_content)
            # Рекурсивно ищем отзывы в JSON структуре
            reviews = _find_reviews_in_json(data)
            for review in reviews:
                text = review.get('text', '')
                if text and text not in processed_texts:
                    processed_texts.add(text)
                    reviews_data.append(review)
        except:
            pass
    
    # Если не нашли в script тегах, ищем JSON объекты напрямую в HTML
    # Ищем все места, где есть "text" и "likes_count" в пределах разумного расстояния
    if not reviews_data:
        # Улучшенный паттерн для текста отзыва - правильно обрабатывает все escape-последовательности
        # Используем более надежный метод: ищем начало строки и извлекаем до закрывающей кавычки с учетом escape
        text_pattern = r'"text"\s*:\s*"'
        
        for text_match in re.finditer(text_pattern, html):
            text_start_pos = text_match.end()  # Позиция после открывающей кавычки
            text_end_pos = text_start_pos
            
            # Вручную парсим строку JSON, учитывая escape-последовательности
            # Ограничиваем поиск до 10000 символов, чтобы не искать слишком долго
            max_search_length = min(text_start_pos + 10000, len(html))
            i = text_start_pos
            while i < max_search_length:
                if html[i] == '\\' and i + 1 < len(html):
                    # Пропускаем escape-символ и следующий символ
                    # Проверяем, что следующий символ валидный для escape-последовательности
                    next_char = html[i + 1]
                    if next_char in ['"', '\\', 'n', 'r', 't', 'u', '/']:
                        i += 2
                        # Для \uXXXX нужно пропустить еще 4 символа
                        if next_char == 'u' and i + 4 < len(html):
                            i += 4
                        continue
                    else:
                        # Невалидная escape-последовательность, пропускаем только \
                        i += 1
                        continue
                elif html[i] == '"':
                    # Нашли потенциальную закрывающую кавычку
                    # Проверяем, что после неё идет валидный JSON символ (запятая, закрывающая скобка, двоеточие для следующего поля)
                    if i + 1 < len(html):
                        next_char = html[i + 1]
                        # Валидные символы после закрывающей кавычки в JSON
                        if next_char in [',', '}', ']', ' ', '\n', '\r', '\t', ':']:
                            text_end_pos = i
                            break
                        # Если следующий символ - это начало нового поля (буква), это тоже валидно
                        elif next_char.isalpha() or next_char == '"':
                            text_end_pos = i
                            break
                    else:
                        # Конец строки - это тоже валидно
                        text_end_pos = i
                        break
                i += 1
            
            if text_end_pos == text_start_pos:
                continue  # Не нашли закрывающую кавычку
            
            # Извлекаем текст с escape-последовательностями
            text_with_escapes = html[text_start_pos:text_end_pos]
            
            # Проверяем, что текст не слишком короткий (возможно, это не полный текст)
            # Но не пропускаем, так как могут быть короткие отзывы
            
            # Декодируем escape-последовательности через json.loads для надежности
            try:
                # Оборачиваем в JSON строку для правильного декодирования
                text = json.loads('"' + text_with_escapes + '"')
            except json.JSONDecodeError:
                # Fallback на ручное декодирование (более полное)
                text = text_with_escapes
                # Обрабатываем все escape-последовательности в правильном порядке
                text = text.replace('\\\\', '\\TEMP_BACKSLASH\\')  # Временная замена для двойных обратных слешей
                text = text.replace('\\"', '"')
                text = text.replace('\\n', '\n')
                text = text.replace('\\r', '\r')
                text = text.replace('\\t', '\t')
                text = text.replace('\\/', '/')
                text = text.replace('\\TEMP_BACKSLASH\\', '\\')  # Возвращаем обратные слеши
            except Exception:
                # Если всё ещё ошибка, используем текст как есть
                text = text_with_escapes
            
            # Пропускаем пустые тексты и дубликаты
            if not text or text in processed_texts:
                continue
            
            text_pos = text_match.start()
            
            # Ищем likes_count и rating в окрестности (в пределах 1500 символов)
            context_start = max(0, text_pos - 500)
            context_end = min(len(html), text_end_pos + 1500)
            context = html[context_start:context_end]
            
            likes_match = re.search(r'"likes_count"\s*:\s*(\d+)', context)
            if not likes_match:
                continue
            
            likes_count = int(likes_match.group(1))
            
            # Ищем rating (количество звёзд) в том же контексте
            rating = None
            rating_match = re.search(r'"rating"\s*:\s*(\d+)', context)
            if rating_match:
                rating = int(rating_match.group(1))
            
            # Ищем дату в разных форматах (расширяем контекст для поиска даты)
            date = ''
            date_context_start = max(0, text_pos - 1000)
            date_context_end = min(len(html), text_end_pos + 2000)
            date_context = html[date_context_start:date_context_end]
            
            # Улучшенный поиск даты с правильной обработкой escape-последовательностей
            date_patterns = [
                r'"date"\s*:\s*"',
                r'"created_at"\s*:\s*"',
                r'"published_at"\s*:\s*"',
            ]
            for date_pattern in date_patterns:
                date_match = re.search(date_pattern, date_context)
                if date_match:
                    date_start = date_match.end()
                    date_end = date_start
                    i = date_start
                    while i < len(date_context):
                        if date_context[i] == '\\' and i + 1 < len(date_context):
                            i += 2
                            continue
                        elif date_context[i] == '"':
                            date_end = i
                            break
                        i += 1
                    if date_end > date_start:
                        date_with_escapes = date_context[date_start:date_end]
                        try:
                            date = json.loads('"' + date_with_escapes + '"')
                        except:
                            date = date_with_escapes.replace('\\"', '"').replace('\\n', '\n').replace('\\r', '\r')
                    break
            
            processed_texts.add(text)
            reviews_data.append({
                'text': text,
                'likes_count': likes_count,
                'date': date,
                'rating': rating
            })
    
    return reviews_data


def _find_reviews_in_json(data: Any, path: str = '') -> List[Dict[str, Any]]:
    """Рекурсивно ищет отзывы в JSON структуре"""
    reviews = []
    
    if isinstance(data, dict):
        # Проверяем, является ли это объектом отзыва
        # Отзыв должен иметь текст и likes_count (media может быть пустым массивом или содержать фотографии)
        if 'text' in data and 'likes_count' in data:
            # Проверяем, что это действительно отзыв (имеет rating или provider или object)
            # Это помогает отличить отзыв от других объектов с text и likes_count
            is_review = (
                'rating' in data or 
                'provider' in data or 
                'object' in data or
                'id' in data  # ID отзыва
            )
            
            if is_review:
                review = {
                    'text': data.get('text', ''),
                    'likes_count': int(data.get('likes_count', 0)),
                    'date': data.get('date', data.get('created_at', data.get('published_at', ''))),
                    'rating': data.get('rating')  # Количество звёзд
                }
                reviews.append(review)
        
        # Рекурсивно ищем в значениях словаря (даже если нашли отзыв, продолжаем поиск)
        for key, value in data.items():
            reviews.extend(_find_reviews_in_json(value, f"{path}.{key}"))
    elif isinstance(data, list):
        # Рекурсивно ищем в элементах списка
        for idx, item in enumerate(data):
            reviews.extend(_find_reviews_in_json(item, f"{path}[{idx}]"))
    
    return reviews


def parse_reviews(driver: webdriver.Chrome, review_url: str, school_id: str) -> list:
    """Парсит отзывы из JSON данных в HTML и даты из DOM"""
    try:
        driver.get(review_url)
    except Exception as e:
        print(f"[error] Не удалось загрузить страницу для школы {school_id}: {e}")
        return []
    
    # Ждём загрузки элементов отзывов (может не быть, если отзывов нет)
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, '_a5f6uz'))
        )
    except TimeoutException:
        # Проверяем, есть ли вообще отзывы на странице
        try:
            # Ищем любые признаки отзывов
            has_reviews = driver.find_elements(By.CLASS_NAME, '_1wlx08h') or \
                         driver.find_elements(By.CLASS_NAME, '_1msln3t') or \
                         driver.find_elements(By.CLASS_NAME, '_a5f6uz')
            if not has_reviews:
                print(f"[info] У школы {school_id} нет отзывов")
                return [{
                    'school_id': school_id,
                    'date': None,
                    'text': None,
                    'likes_count': None
                }]
        except:
            pass
        print(f"[warn] Таймаут ожидания загрузки отзывов для школы {school_id}")
    
    time.sleep(1.0)  # Дополнительная пауза для загрузки данных
    
    # Физическая прокрутка для загрузки всех отзывов через pyautogui
    try:
        scroll_page_with_pyautogui(duration=2.0, scroll_distance=2000, scroll_step=30)
    except Exception as e:
        # Fallback на обычную прокрутку через JavaScript
        try:
            for i in range(5):
                driver.execute_script('window.scrollBy(0, 500);')
                time.sleep(0.3)
        except Exception as e2:
            pass
    
    time.sleep(1.5)  # Дополнительная пауза после прокрутки для загрузки данных
    
    # Получаем HTML контент
    try:
        html_content = driver.page_source
    except Exception as e:
        print(f"[error] Не удалось получить HTML для школы {school_id}: {e}")
        return []
    
    # Сначала пытаемся извлечь отзывы из JSON данных в HTML
    try:
        json_reviews = extract_reviews_from_json(html_content)
        print(f"[debug] Извлечено отзывов из JSON: {len(json_reviews)}")
    except Exception as e:
        print(f"[error] Ошибка при извлечении отзывов из JSON для школы {school_id}: {e}")
        json_reviews = []
    
    # Если нашли отзывы в JSON, используем их, но даты извлекаем из DOM
    if json_reviews:
        try:
            # Извлекаем все тексты отзывов из DOM для сопоставления с датами
            # Сначала ищем все элементы с текстом отзывов
            text_elements_long = driver.find_elements(By.CLASS_NAME, '_1wlx08h')
            text_elements_short = driver.find_elements(By.CLASS_NAME, '_1msln3t')
            dom_texts = []
            
            # Сопоставляем тексты и даты из DOM
            for text_elem in text_elements_long + text_elements_short:
                try:
                    text = text_elem.text.strip()
                    if not text:
                        continue
                    
                    # Ищем дату для этого текста - ищем ближайший элемент _a5f6uz
                    # Сначала ищем в родительских элементах
                    date = ''
                    try:
                        par = text_elem
                        for _ in range(15):  # Увеличиваем глубину поиска
                            try:
                                par = par.find_element(By.XPATH, '..')
                                try:
                                    date_elem = par.find_element(By.CLASS_NAME, '_a5f6uz')
                                    date = date_elem.text.strip()
                                    if date:
                                        break
                                except:
                                    continue
                            except:
                                break
                    except:
                        pass
                    
                    # Если не нашли в родителях, ищем в соседних элементах того же контейнера
                    if not date:
                        try:
                            # Ищем общий родительский контейнер
                            container = text_elem
                            for _ in range(10):
                                try:
                                    container = container.find_element(By.XPATH, '..')
                                    # Ищем все элементы _a5f6uz в этом контейнере
                                    date_elems = container.find_elements(By.CLASS_NAME, '_a5f6uz')
                                    if date_elems:
                                        # Берем первый найденный элемент даты
                                        date = date_elems[0].text.strip()
                                        if date:
                                            break
                                except:
                                    break
                        except:
                            pass
                    
                    if text and text not in [t['text'] for t in dom_texts]:
                        dom_texts.append({'text': text, 'date': date})
                except Exception as e:
                    print(f"[warn] Ошибка при обработке элемента текста: {e}")
                    continue
            
            print(f"[debug] Найдено текстов в DOM: {len(dom_texts)}")
            
            # Сопоставляем JSON отзывы с датами из DOM
            reviews = []
            processed_dom_texts = set()  # Тексты, которые уже обработаны из JSON
            
            for review_data in json_reviews:
                try:
                    text = review_data.get('text', '')
                    date = review_data.get('date', '')
                    
                    # Если дата не найдена в JSON, ищем её в DOM по тексту
                    if not date:
                        # Нормализуем текст для сравнения (убираем лишние пробелы и переносы)
                        def normalize_text(t):
                            return ' '.join(t.split())
                        
                        text_normalized = normalize_text(text)
                        
                        # Ищем точное совпадение текста (нормализованного)
                        for dom_item in dom_texts:
                            dom_text_normalized = normalize_text(dom_item['text'])
                            if dom_text_normalized == text_normalized:
                                date = dom_item['date']
                                processed_dom_texts.add(dom_item['text'])
                                break
                        
                        # Если не нашли точное совпадение, ищем по началу текста
                        if not date:
                            for dom_item in dom_texts:
                                dom_text_normalized = normalize_text(dom_item['text'])
                                # Сравниваем первые 50 символов нормализованного текста
                                text_start = text_normalized[:50] if len(text_normalized) > 50 else text_normalized
                                dom_text_start = dom_text_normalized[:50] if len(dom_text_normalized) > 50 else dom_text_normalized
                                
                                if text_start and dom_text_start and (
                                    text_start == dom_text_start or 
                                    (len(text_start) > 30 and text_start in dom_text_normalized) or 
                                    (len(dom_text_start) > 30 and dom_text_start in text_normalized)
                                ):
                                    date = dom_item['date']
                                    processed_dom_texts.add(dom_item['text'])
                                    break
                        
                        # Если всё ещё не нашли, ищем по любому совпадению начала
                        if not date:
                            for dom_item in dom_texts:
                                dom_text_normalized = normalize_text(dom_item['text'])
                                # Сравниваем первые 30 символов
                                text_start = text_normalized[:30] if len(text_normalized) > 30 else text_normalized
                                dom_text_start = dom_text_normalized[:30] if len(dom_text_normalized) > 30 else dom_text_normalized
                                
                                if text_start and dom_text_start and text_start == dom_text_start:
                                    date = dom_item['date']
                                    processed_dom_texts.add(dom_item['text'])
                                    break
                    
                    # Преобразуем дату в формат YYYY-MM-DD
                    date_formatted = convert_date_to_postgresql_format(date)
                    
                    reviews.append({
                        'school_id': school_id,
                        'date': date_formatted,
                        'text': text,
                        'likes_count': review_data.get('likes_count', 0),
                        'review_star': review_data.get('rating')  # Количество звёзд из JSON
                    })
                except Exception as e:
                    print(f"[warn] Ошибка при обработке отзыва: {e}")
                    continue
            
            # Добавляем отзывы из DOM, которые не были найдены в JSON
            # Это важно, так как некоторые отзывы могут быть только в DOM
            for dom_item in dom_texts:
                dom_text = dom_item['text']
                # Проверяем, не был ли этот текст уже обработан
                if dom_text not in processed_dom_texts:
                    # Нормализуем текст для поиска в JSON
                    def normalize_text(t):
                        return ' '.join(t.split())
                    
                    dom_text_normalized = normalize_text(dom_text)
                    
                    # Проверяем, нет ли этого текста в JSON отзывах (может быть с небольшими отличиями)
                    found_in_json = False
                    for review_data in json_reviews:
                        json_text = review_data.get('text', '')
                        json_text_normalized = normalize_text(json_text)
                        
                        # Сравниваем первые 50 символов
                        dom_start = dom_text_normalized[:50] if len(dom_text_normalized) > 50 else dom_text_normalized
                        json_start = json_text_normalized[:50] if len(json_text_normalized) > 50 else json_text_normalized
                        
                        if dom_start and json_start and (
                            dom_start == json_start or
                            (len(dom_start) > 30 and dom_start in json_text_normalized) or
                            (len(json_start) > 30 and json_start in dom_text_normalized)
                        ):
                            found_in_json = True
                            break
                    
                    # Если не нашли в JSON, добавляем отзыв из DOM
                    if not found_in_json:
                        # Пытаемся извлечь likes_count и rating из HTML для этого отзыва
                        likes_count = 0
                        review_star = None
                        try:
                            text_search = dom_text[:30] if len(dom_text) > 30 else dom_text
                            text_search_escaped = re.escape(text_search)
                            
                            text_positions = []
                            for match_obj in re.finditer(text_search_escaped, html_content):
                                text_positions.append(match_obj.start())
                            
                            for text_pos in text_positions:
                                search_start = max(0, text_pos - 1000)
                                search_end = min(len(html_content), text_pos + 3000)
                                search_context = html_content[search_start:search_end]
                                
                                likes_match = re.search(r'"likes_count"\s*:\s*(\d+)', search_context)
                                if likes_match:
                                    likes_count = int(likes_match.group(1))
                                    
                                    rating_match = re.search(r'"rating"\s*:\s*(\d+)', search_context)
                                    if rating_match:
                                        review_star = int(rating_match.group(1))
                                    break
                        except Exception as e:
                            print(f"[debug] Не удалось извлечь likes_count/rating для DOM отзыва: {e}")
                        
                        # Преобразуем дату в формат YYYY-MM-DD
                        date_formatted = convert_date_to_postgresql_format(dom_item['date'])
                        
                        reviews.append({
                            'school_id': school_id,
                            'date': date_formatted,
                            'text': dom_text,
                            'likes_count': likes_count,
                            'review_star': review_star
                        })
                        print(f"[debug] Добавлен отзыв из DOM, не найденный в JSON: {dom_text[:50]}...")
            
            print(f"[debug] Обработано отзывов из JSON с датами из DOM: {len(reviews)}")
            return reviews
        except Exception as e:
            print(f"[error] Ошибка при извлечении дат из DOM для школы {school_id}: {e}")
            # Возвращаем отзывы без дат, если не удалось извлечь даты
            reviews = []
            for review_data in json_reviews:
                # Преобразуем дату в формат YYYY-MM-DD
                date_str = review_data.get('date', '')
                date_formatted = convert_date_to_postgresql_format(date_str)
                
                reviews.append({
                    'school_id': school_id,
                    'date': date_formatted,
                    'text': review_data.get('text', ''),
                    'likes_count': review_data.get('likes_count', 0),
                    'review_star': review_data.get('rating')  # Количество звёзд из JSON
                })
            return reviews
    
    # Если не нашли в JSON, используем старый метод парсинга DOM
    print("[debug] JSON отзывы не найдены, используем парсинг DOM")
    
    try:
        # Ищем контейнеры отзывов - ищем элементы с классом, который содержит отзывы
        # Пробуем найти все контейнеры отзывов
        review_containers = driver.find_elements(By.CSS_SELECTOR, '[class*="_172gbf8"], [class*="_1k5soqfl"]')
        if not review_containers:
            # Альтернативный способ - ищем по структуре
            try:
                review_containers = driver.find_elements(By.XPATH, "//div[contains(@class, '_') and .//div[contains(@class, '_a5f6uz')]]")
            except:
                review_containers = []
        
        print(f"[debug] Найдено контейнеров отзывов: {len(review_containers)}")
        
        if not review_containers:
            print(f"[info] У школы {school_id} нет отзывов (контейнеры не найдены)")
            return [{
                'school_id': school_id,
                'date': None,
                'text': None,
                'likes_count': None
            }]
        
        reviews = []
        processed_texts = set()  # Для избежания дубликатов
        
        # Для каждого контейнера извлекаем данные отзыва
        for idx, container in enumerate(review_containers):
            try:
                # Ищем текст отзыва
                text_elem = None
                try:
                    text_elem = container.find_element(By.CLASS_NAME, '_1wlx08h')
                except:
                    try:
                        text_elem = container.find_element(By.CLASS_NAME, '_1msln3t')
                    except:
                        pass
                
                if not text_elem:
                    continue
                
                text = text_elem.text.strip()
                if not text or text in processed_texts:
                    continue
                
                processed_texts.add(text)
                
                # Ищем дату
                date = ''
                try:
                    date_elem = container.find_element(By.CLASS_NAME, '_a5f6uz')
                    date = date_elem.text.strip()
                except:
                    pass
                
                # Извлекаем likes_count и rating из JSON в HTML
                likes_count = 0
                review_star = None
                try:
                    # Ищем JSON данные для этого отзыва в HTML
                    # Используем более надежный метод: ищем начало текста в JSON и извлекаем до закрывающей кавычки
                    # Берем первые 30 символов текста для поиска (меньше, чтобы избежать проблем с кавычками и спецсимволами)
                    text_search = text[:30] if len(text) > 30 else text
                    # Экранируем специальные символы для regex
                    text_search_escaped = re.escape(text_search)
                    
                    # Ищем позицию текста (или его начала) в HTML - ищем как в экранированном, так и в неэкранированном виде
                    text_positions = []
                    # Поиск точного совпадения (текст может быть в DOM или в JSON)
                    for match_obj in re.finditer(text_search_escaped, html_content):
                        text_positions.append(match_obj.start())
                    
                    # Для каждой позиции ищем ближайший likes_count и rating в JSON
                    for text_pos in text_positions:
                        # Ищем в окрестности (в пределах 3000 символов)
                        search_start = max(0, text_pos - 1000)
                        search_end = min(len(html_content), text_pos + 3000)
                        search_context = html_content[search_start:search_end]
                        
                        # Ищем "likes_count" в этом контексте
                        likes_match = re.search(r'"likes_count"\s*:\s*(\d+)', search_context)
                        if likes_match:
                            likes_count = int(likes_match.group(1))
                            
                            # Ищем "rating" в том же контексте
                            rating_match = re.search(r'"rating"\s*:\s*(\d+)', search_context)
                            if rating_match:
                                review_star = int(rating_match.group(1))
                            break
                except Exception as e:
                    print(f"[debug] Не удалось извлечь likes_count/rating для отзыва {idx}: {e}")
                
                # Преобразуем дату в формат YYYY-MM-DD
                date_formatted = convert_date_to_postgresql_format(date)
                
                reviews.append({
                    'school_id': school_id,
                    'date': date_formatted,
                    'text': text,
                    'likes_count': likes_count,
                    'review_star': review_star  # Количество звёзд из JSON
                })
                
                print(f"[debug] Обработан отзыв {idx}: текст (длина: {len(text)}), дата: {date}, likes_count: {likes_count}, rating: {review_star}")
                
            except Exception as e:
                print(f"[debug] Ошибка при обработке контейнера {idx}: {e}")
                continue
        
        print(f"[debug] Обработано контейнеров: {len(review_containers)}, найдено уникальных отзывов: {len(reviews)}")
        return reviews
    except Exception as e:
        print(f"[error] Ошибка при парсинге DOM для школы {school_id}: {e}")
        return []


def _load_json_allowing_line_comments(path: str) -> Dict[str, Any]:
    """
    Поддержка // комментариев вне строк JSON.
    Реализовано посимвольным разбором, чтобы не ломать URL вида https://...
    """
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()

    result_chars: List[str] = []
    in_string = False
    escape = False
    i = 0
    length = len(src)
    while i < length:
        ch = src[i]
        if in_string:
            result_chars.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        # вне строки
        if ch == '"':
            in_string = True
            result_chars.append(ch)
            i += 1
            continue

        # однострочный комментарий // ... до конца строки
        if ch == '/' and i + 1 < length and src[i + 1] == '/':
            # пропускаем до конца строки
            while i < length and src[i] not in ['\n', '\r']:
                i += 1
            # перевод строки сохраняем как есть
            continue

        result_chars.append(ch)
        i += 1

    cleaned = ''.join(result_chars)
    return json.loads(cleaned)


def load_input_links(input_file: str) -> List[Dict[str, str]]:
    """Загружает список школ из входного JSON файла"""
    data = _load_json_allowing_line_comments(input_file)
    # Поддерживаем разные форматы входного файла
    if "data" in data:
        return data.get("data", [])
    elif "school_name" in data:
        return data.get("school_name", [])
    else:
        return data if isinstance(data, list) else []


def load_existing_reviews() -> list:
    """Загружает существующие отзывы из файла"""
    if os.path.exists(REVIEWS_OUTPUT_FILE):
        try:
            with open(REVIEWS_OUTPUT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("reviews", [])
        except Exception:
            return []
    return []


def save_reviews_for_school(school_id: str, reviews: list) -> None:
    """Сохраняет отзывы для одной школы, удаляя старые отзывы этой школы и перенумеровывая все отзывы"""
    os.makedirs(REVIEWS_DATA_DIR, exist_ok=True)
    
    # Загружаем существующие отзывы
    existing_reviews = load_existing_reviews()
    
    # Удаляем старые отзывы для этой школы
    existing_reviews = [r for r in existing_reviews if r.get('school_id') != school_id]
    
    # Добавляем новые отзывы
    all_reviews = existing_reviews + reviews
    
    # Перенумеровываем все отзывы сплошной нумерацией и делаем review_id первым полем
    formatted_reviews = []
    for idx, review in enumerate(all_reviews, start=1):
        # Преобразуем дату, если она еще не преобразована
        date_str = review.get('date', '')
        if date_str and not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            date_str = convert_date_to_postgresql_format(date_str)
            review['date'] = date_str
        
        # Создаем новый словарь с review_id первым полем
        formatted_review = {
            'review_id': str(idx),
            'school_id': review.get('school_id', ''),
            'date': review.get('date', ''),
            'text': review.get('text', ''),
            'likes_count': review.get('likes_count', 0),
            'review_star': review.get('review_star')
        }
        formatted_reviews.append(formatted_review)
    
    # Сохраняем все отзывы
    payload = {
        "resource": "2gis",
        "reviews": formatted_reviews,
    }
    with open(REVIEWS_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def save_all_reviews(reviews: list) -> None:
    """Сохраняет все отзывы в один файл (для обратной совместимости)"""
    os.makedirs(REVIEWS_DATA_DIR, exist_ok=True)
    
    # Загружаем существующие отзывы, если файл есть
    existing_reviews = load_existing_reviews()
    
    # Объединяем старые и новые отзывы
    all_reviews = existing_reviews + reviews
    
    # Перенумеровываем все отзывы сплошной нумерацией и делаем review_id первым полем
    formatted_reviews = []
    for idx, review in enumerate(all_reviews, start=1):
        # Преобразуем дату, если она еще не преобразована
        date_str = review.get('date', '')
        if date_str and not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            date_str = convert_date_to_postgresql_format(date_str)
            review['date'] = date_str
        
        # Создаем новый словарь с review_id первым полем
        formatted_review = {
            'review_id': str(idx),
            'school_id': review.get('school_id', ''),
            'date': review.get('date', ''),
            'text': review.get('text', ''),
            'likes_count': review.get('likes_count', 0),
            'review_star': review.get('review_star')
        }
        formatted_reviews.append(formatted_review)
    
    # Сохраняем все отзывы
    payload = {
        "resource": "2gis",
        "reviews": formatted_reviews,
    }
    with open(REVIEWS_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main(input_file: str = None) -> None:
    """
    Основная функция парсинга отзывов
    
    Args:
        input_file: Путь к JSON файлу со списком школ (должен содержать поля '2gis_review_url')
                   Если не указан, ищет файл в текущей директории
    """
    # Ищем входной файл
    if input_file is None:
        # Ищем в разных местах
        possible_paths = [
            os.path.join(REVIEWS_DATA_DIR, "input", "2gis_review_school.json"),
            os.path.join(REVIEWS_DATA_DIR, "input", "2gis_test_review_school.json"),
            os.path.join(REVIEWS_DATA_DIR, "input", "2gis_schools_with_info.json"),
            os.path.join(os.path.dirname(__file__), "2gis_reviews_data", "2gis_schools_with_info.json"),
            os.path.join(os.path.dirname(__file__), "input.json"),
        ]
        input_file = None
        for path in possible_paths:
            if os.path.exists(path):
                input_file = path
                break
        
        if input_file is None:
            print("Ошибка: не найден входной файл со списком школ")
            print("Укажите путь к файлу с полем '2gis_review_url' для каждой школы")
            return
    
    schools_data = load_input_links(input_file)
    if not schools_data:
        print(f"Файл {input_file} пуст или не содержит данных о школах")
        return

    driver = setup_driver()
    all_reviews = []

    try:
        for item in schools_data:
            school_id = item.get("id", "").strip()
            review_url = item.get("2gis_review_url", "").strip()
            
            if not school_id:
                print(f"Пропущена запись без id: {item.get('name', item.get('yandex_name', 'неизвестно'))}")
                continue

            # Парсинг отзывов
            if review_url:
                school_name = item.get("name", item.get("yandex_name", "неизвестно"))
                print(f"Парсинг отзывов для школы {school_id}: {school_name}")
                reviews = parse_reviews(driver, review_url, school_id)
                all_reviews.extend(reviews)
                print(f"  Найдено отзывов: {len(reviews)}")
                
                # Сохраняем отзывы для этой школы сразу после обработки
                save_reviews_for_school(school_id, reviews)
                print(f"  Сохранено отзывов для школы {school_id}")
            else:
                print(f"Пропущена школа {school_id}: нет 2gis_review_url")
            
            time.sleep(0.5)

        print(f"Готово. Всего отзывов обработано: {len(all_reviews)}")

    finally:
        driver.quit()


if __name__ == "__main__":
    import sys
    input_file = sys.argv[1] if len(sys.argv) > 1 else None
    main(input_file)



