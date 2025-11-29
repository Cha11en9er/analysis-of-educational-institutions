#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер дополнительных данных о школах с Яндекс.Карт (ym).

Назначение:
- взять список школ из `ym_data/ym_find_all_info/input/ym_schools_test.json`
- для каждой школы открыть страницу `url` в браузере (Selenium)
- извлечь из DOM адрес школы и количество отзывов
- записать найденные данные в `ym_data/ym_find_all_info/output/ym_full_schools_data.json`
"""

import json
import os
import re
import time
from typing import List, Dict, Any

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.common import exceptions as selenium_exceptions
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("[ERROR] Selenium не установлен. Установите: pip install selenium")

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    print("[WARN] beautifulsoup4 не установлен. Установите: pip install beautifulsoup4")


# Пути относительно текущего файла
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))  # .../school_parser/ym_find_all_info
YM_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))  # .../yandex_maps
DATA_DIR = os.path.join(YM_ROOT, "ym_data", "ym_find_all_info")
INPUT_FILE = os.path.join(DATA_DIR, "input", "ym_schools_test.json")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")
FULL_OUTPUT_FILE = os.path.join(OUTPUT_DIR, "ym_full_schools_data.json")


def setup_driver() -> webdriver.Chrome:
    """
    Простая настройка Chrome WebDriver для загрузки страниц школ.
    Берём похожую конфигурацию, как в `ym_review_dev.py`, но без лишних опций.
    """
    if not SELENIUM_AVAILABLE:
        raise ImportError("Selenium не установлен. Установите: pip install selenium")

    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Картинки можно не отключать, т.к. нам важен DOM, но для скорости можно:
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2,
    }
    chrome_options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=chrome_options)
    # Скрываем флаг webdriver
    try:
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    except Exception:
        pass

    return driver


def load_schools_from_json(path: str) -> List[Dict[str, Any]]:
    """Читает список школ из JSON файла `ym_schools_test.json`."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] Файл не найден: {path}")
        return []
    except json.JSONDecodeError as e:
        print(f"[ERROR] Ошибка парсинга JSON ({path}): {e}")
        return []

    schools = data.get("data", [])
    if not isinstance(schools, list):
        print(f"[ERROR] Неверный формат JSON: поле 'data' должно быть списком")
        return []

    print(f"[INFO] Загружено школ из JSON: {len(schools)}")
    return schools


def extract_school_info_from_html(html: str) -> Dict[str, Any]:
    """
    Извлекает из HTML адрес школы и количество отзывов.

    Адрес:
        <a class="orgpage-header-view__address"> ... <span>АДРЕС</span>

    Количество отзывов:
        <div class="tabs-select-view__title _name_reviews" aria-label="Отзывы, 35">...</div>
    
    Если данные не найдены, возвращает дефолтные значения:
    - adres: 'адрес не найден'
    - reviews_count: 'отзывов нету'
    """
    adres = ""
    reviews_count = None

    if not BS4_AVAILABLE:
        return {"adres": "адрес не найден", "reviews_count": "отзывов нету"}

    soup = BeautifulSoup(html, "html.parser")

    # Адрес школы
    try:
        addr_a = soup.find("a", class_="orgpage-header-view__address")
        if addr_a:
            # Берём текст, как он отображается пользователю
            adres = addr_a.get_text(" ", strip=True)
    except Exception as e:
        print(f"[WARN] Не удалось извлечь адрес: {e}")

    # Количество отзывов
    try:
        reviews_div = soup.find("div", class_="tabs-select-view__title _name_reviews")
        if not reviews_div:
            # На всякий случай ищем по частичному совпадению класса
            for div in soup.find_all("div"):
                classes = div.get("class") or []
                if any("_name_reviews" in c for c in classes):
                    reviews_div = div
                    break

        if reviews_div:
            aria_label = reviews_div.get("aria-label") or ""
            text = reviews_div.get_text(" ", strip=True) or ""
            # Пытаемся вытащить число из aria-label, иначе из текста
            m = re.search(r"(\d+)", aria_label) or re.search(r"(\d+)", text)
            if m:
                reviews_count = int(m.group(1))
    except Exception as e:
        print(f"[WARN] Не удалось извлечь количество отзывов: {e}")

    # Устанавливаем дефолтные значения, если данные не найдены
    if not adres:
        adres = "адрес не найден"
    
    if reviews_count is None or reviews_count == 0:
        reviews_count = "отзывов нету"

    return {
        "adres": adres,
        "reviews_count": reviews_count,
    }


def load_existing_output() -> Dict[str, Any]:
    """
    Читает текущий файл `ym_full_schools_data.json`, если он существует.
    Возвращает структуру с полями source, topic, data.
    """
    if not os.path.exists(FULL_OUTPUT_FILE):
        return {
            "source": "yandex_maps",
            "topic": "",
            "data": [],
        }

    try:
        with open(FULL_OUTPUT_FILE, "r", encoding="utf-8") as f:
            content = json.load(f)
        content.setdefault("source", "yandex_maps")
        content.setdefault("topic", "")
        content.setdefault("data", [])
        return content
    except Exception as e:
        print(f"[WARN] Не удалось прочитать существующий выходной файл: {e}")
        return {
            "source": "yandex_maps",
            "topic": "",
            "data": [],
        }


def is_school_fully_parsed(school: Dict[str, Any]) -> bool:
    """
    Проверяет, есть ли у школы полная информация (адрес и количество отзывов).
    
    Школа считается полностью распарсенной, если:
    - есть поле 'adres' и оно не пустое и не равно 'адрес не найден'
    - есть поле 'reviews_count' и оно не равно 'отзывов нету'
    """
    adres = school.get("adres", "")
    reviews_count = school.get("reviews_count", "")
    
    # Проверяем адрес
    has_adres = adres and adres != "" and adres != "адрес не найден"
    
    # Проверяем количество отзывов (должно быть числом, не строкой 'отзывов нету')
    has_reviews_count = reviews_count != "" and reviews_count != "отзывов нету" and reviews_count is not None
    
    return has_adres and has_reviews_count


def fetch_school_pages() -> None:
    """
    Основная логика:
    - читает школы из `ym_schools_test.json`
    - последовательно открывает `url` каждой школы в Selenium
    - извлекает необходимые данные из DOM и пополняет `ym_full_schools_data.json`
    """
    schools = load_schools_from_json(INPUT_FILE)
    if not schools:
        print("[ERROR] Список школ пуст — нечего парсить")
        return

    # Для теста можно оставить только первую школу (как вы просили),
    # но логика уже поддерживает список — просто раскомментируйте по желанию.
    # schools = schools[:1]

    print(f"[INFO] Будет обработано школ: {len(schools)}")

    existing_output = load_existing_output()
    enriched_schools: List[Dict[str, Any]] = existing_output["data"][:]
    existing_ids = {str(item.get("id")): item for item in enriched_schools}

    driver = None
    try:
        driver = setup_driver()

        for idx, school in enumerate(schools, start=1):
            url = school.get("url")
            school_id = str(school.get("id", "unknown"))
            name = school.get("name", "")

            if not url:
                print(f"[WARN] Пропускаю школу id={school_id}: нет поля 'url'")
                continue

            # Проверяем, есть ли уже полная информация о школе
            if school_id in existing_ids:
                existing_school = existing_ids[school_id]
                if is_school_fully_parsed(existing_school):
                    print(f"[SKIP] Школа id={school_id} уже имеет полную информацию в выходном файле — пропускаю.")
                    continue
                else:
                    print(f"[INFO] Школа id={school_id} есть в файле, но информация неполная — парсим заново.")

            print(f"\n[INFO] ({idx}/{len(schools)}) Открываю школу id={school_id}, name='{name}'")
            print(f"[INFO] URL: {url}")

            try:
                driver.get(url)
            except selenium_exceptions.WebDriverException as e:
                print(f"[ERROR] Ошибка загрузки страницы для школы id={school_id}: {e}")
                continue

            # Ждём 3 секунды для загрузки страницы
            print("[INFO] Ожидание загрузки страницы (3 секунды)...")
            time.sleep(3)

            # Здесь можно добавить скролл, если нужно подгрузить динамический контент
            # Пока просто берём текущий DOM
            try:
                html = driver.page_source
            except selenium_exceptions.WebDriverException as e:
                print(f"[ERROR] Не удалось получить page_source для школы id={school_id}: {e}")
                continue

            # Извлекаем из DOM адрес и количество отзывов
            info = extract_school_info_from_html(html)
            adres = info.get("adres", "")
            reviews_count = info.get("reviews_count", 0)

            print(f"[INFO] Извлечён адрес: '{adres}'")
            print(f"[INFO] Извлечено количество отзывов: {reviews_count}")

            # Проверяем, не находится ли школа в Энгельсе
            if adres and "энгельс" in adres.lower():
                print(f"[SKIP] Школа id={school_id} находится в Энгельсе — пропускаю.")
                continue

            # Формируем обогащённую запись о школе
            enriched_school = dict(school)
            enriched_school["adres"] = adres
            enriched_school["reviews_count"] = reviews_count
            enriched_schools.append(enriched_school)
            existing_ids[school_id] = enriched_school

    finally:
        if driver is not None:
            driver.quit()
            print("[INFO] WebDriver закрыт")

    # После обхода всех школ записываем итоговый JSON в ym_full_schools_data.json
    # Берём мета-информацию (source, topic) из входного файла, если она там есть
    source = "yandex_maps"
    topic = ""
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            input_data = json.load(f)
            source = input_data.get("source", source)
            topic = input_data.get("topic", topic)
    except Exception as e:
        print(f"[WARN] Не удалось прочитать метаданные из входного файла: {e}")

    # Если исходный файл уже содержал topic/source, не перезаписываем пустыми значениями
    final_source = source or existing_output.get("source", "yandex_maps")
    final_topic = topic or existing_output.get("topic", "")

    # Фильтруем школы из Энгельса из уже существующих данных
    filtered_schools = []
    engels_removed = 0
    for school in enriched_schools:
        adres = school.get("adres", "")
        if adres and "энгельс" in adres.lower():
            engels_removed += 1
            school_id = school.get("id", "unknown")
            print(f"[FILTER] Удаляю школу id={school_id} из результата (Энгельс): '{adres}'")
        else:
            filtered_schools.append(school)

    if engels_removed > 0:
        print(f"[INFO] Удалено школ из Энгельса: {engels_removed}")

    full_output = {
        "source": final_source,
        "topic": final_topic,
        "data": filtered_schools,
    }

    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(FULL_OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(full_output, f, ensure_ascii=False, indent=4)
        print(f"[OK] Обогащённые данные сохранены в: {FULL_OUTPUT_FILE}")
        print(f"[OK] Всего школ в выходном файле: {len(filtered_schools)}")
    except Exception as e:
        print(f"[ERROR] Не удалось сохранить файл {FULL_OUTPUT_FILE}: {e}")


def main():
    """
    Точка входа:
    - создаёт/обновляет HTML-файлы в `output`
    - записывает все найденные данные в `ym_full_schools_data.json`
    """
    print("[INFO] Старт парсера дополнительных данных школ (ym_find_all_info)")
    print(f"[INFO] Входной JSON: {INPUT_FILE}")
    print(f"[INFO] Папка для HTML: {OUTPUT_DIR}")
    fetch_school_pages()
    print("[INFO] Работа парсера завершена")


if __name__ == "__main__":
    main()


