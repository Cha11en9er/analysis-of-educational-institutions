#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для поиска кадастрового номера на сайте кадастр.сайт
Открывает сайт, находит поле ввода и вводит адрес.
Обрабатывает адреса из JSON файла и сохраняет результаты.
"""

import json
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# URL сайта
SITE_URL = "https://кадастр.сайт/"

# Пути к JSON файлам
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FCN_ROOT = os.path.dirname(CURRENT_DIR)
DATA_DIR = os.path.join(FCN_ROOT, "fcn_data")
INPUT_DIR = os.path.join(DATA_DIR, "fcn_input")
OUTPUT_DIR = os.path.join(DATA_DIR, "fcn_output")
JSON_INPUT_FILE = os.path.join(INPUT_DIR, "find_cadastral_number_data.json")
JSON_OUTPUT_FILE = os.path.join(OUTPUT_DIR, "find_cadastral_number_data_output.json")

# Селекторы для поиска input элемента
SELECTORS = [
    (By.NAME, "onestring_251124182124"),
    (By.CLASS_NAME, "input-sugg form-control"),
    (By.ID, "onestring_251124182124"),
]


def setup_driver():
    """Настройка Chrome WebDriver"""
    chrome_options = Options()
    
    # Опции для обхода детекции ботов
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    
    # Отключаем изображения для ускорения
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        print("✅ Chrome WebDriver инициализирован")
        return driver
    except Exception as e:
        print(f"❌ Ошибка инициализации WebDriver: {e}")
        print("Убедитесь, что ChromeDriver установлен и находится в PATH")
        raise


def find_input_element(driver, wait_time=10):
    """
    Находит input элемент по одному из указанных селекторов.
    
    Args:
        driver: WebDriver экземпляр
        wait_time: Время ожидания в секундах
    
    Returns:
        WebElement или None
    """
    wait = WebDriverWait(driver, wait_time)
    
    # Пробуем найти элемент по каждому селектору
    for by, selector in SELECTORS:
        try:
            # Для CLASS_NAME с пробелами нужно использовать CSS селектор
            if by == By.CLASS_NAME and " " in selector:
                # Разделяем классы и используем CSS селектор
                classes = selector.split()
                css_selector = "." + ".".join(classes)
                element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, css_selector)))
                print(f"✅ Найден input элемент по CSS селектору: {css_selector}")
                return element
            else:
                element = wait.until(EC.presence_of_element_located((by, selector)))
                print(f"✅ Найден input элемент по {by}: {selector}")
                return element
        except TimeoutException:
            print(f"⚠️  Элемент не найден по {by}: {selector}")
            continue
        except Exception as e:
            print(f"⚠️  Ошибка при поиске по {by}: {selector} - {e}")
            continue
    
    # Если не нашли по ожиданию, пробуем найти без ожидания
    print("⚠️  Пробую найти элемент без ожидания...")
    for by, selector in SELECTORS:
        try:
            if by == By.CLASS_NAME and " " in selector:
                classes = selector.split()
                css_selector = "." + ".".join(classes)
                element = driver.find_element(By.CSS_SELECTOR, css_selector)
                print(f"✅ Найден input элемент по CSS селектору: {css_selector}")
                return element
            else:
                element = driver.find_element(by, selector)
                print(f"✅ Найден input элемент по {by}: {selector}")
                return element
        except NoSuchElementException:
            continue
        except Exception as e:
            print(f"⚠️  Ошибка при поиске по {by}: {selector} - {e}")
            continue
    
    return None


def load_json_data(file_path):
    """Загружает данные из JSON файла"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Ошибка при загрузке JSON: {e}")
        raise


def save_json_data(file_path, data):
    """Сохраняет данные в JSON файл"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"✅ Данные сохранены в {file_path}")
    except Exception as e:
        print(f"❌ Ошибка при сохранении JSON: {e}")
        raise


def extract_cadastral_number(driver):
    """
    Извлекает кадастровый номер из таблицы результатов.
    
    Args:
        driver: WebDriver экземпляр
    
    Returns:
        Кадастровый номер (str) или None если не найден
    """
    try:
        # Ждем 5 секунд после перехода на страницу результатов
        print("⏳ Ожидание 5 секунд для загрузки страницы результатов...")
        time.sleep(5)
        
        # Ждем появления таблицы
        print("⏳ Ожидание 3 секунды для загрузки таблицы...")
        time.sleep(3)
        
        # Ищем все строки таблицы
        table_rows = driver.find_elements(By.TAG_NAME, "tr")
        print(f"🔍 Найдено строк таблицы: {len(table_rows)}")
        
        # Если таблица пустая, ждем еще
        if len(table_rows) == 0:
            print("⚠️  Таблица пустая, ожидание еще 3 секунды...")
            time.sleep(3)
            table_rows = driver.find_elements(By.TAG_NAME, "tr")
            print(f"🔍 Найдено строк таблицы после ожидания: {len(table_rows)}")
        
        # Классы для поиска
        target_td_classes = ["p-1", "p-md-2", "d-inline-block", "d-md-table-cell", "text-center", "nowrap"]
        cadastral_td_classes = ["p-1", "p-md-2", "d-block", "d-md-table-cell", "nowrap", "pointer"]
        
        for row in table_rows:
            try:
                # Ищем td с нужным классом и текстом 'здание'
                tds = row.find_elements(By.TAG_NAME, "td")
                
                # Проверяем каждую ячейку в строке
                found_building_cell = False
                for td in tds:
                    td_class = td.get_attribute("class") or ""
                    td_text = td.text.strip().lower()
                    
                    # Проверяем, что все классы присутствуют и текст содержит 'здание'
                    if all(cls in td_class for cls in target_td_classes) and 'здание' in td_text:
                        print("✅ Найдена строка с 'здание'")
                        found_building_cell = True
                        break
                
                # Если нашли ячейку с 'здание', ищем первую ячейку с нужным классом
                if found_building_cell:
                    # Ожидание 3 секунды перед извлечением данных
                    print("⏳ Ожидание 3 секунды перед извлечением кадастрового номера...")
                    time.sleep(3)
                    
                    for cadastral_td in tds:
                        cadastral_td_class_attr = cadastral_td.get_attribute("class") or ""
                        
                        # Проверяем, что все классы присутствуют
                        if all(cls in cadastral_td_class_attr for cls in cadastral_td_classes):
                            cadastral_number = cadastral_td.text.strip()
                            if cadastral_number:
                                print(f"✅ Найден кадастровый номер: {cadastral_number}")
                                return cadastral_number
                    
                    # Если не нашли ячейку с нужным классом, берем первую ячейку строки
                    if tds:
                        cadastral_number = tds[0].text.strip()
                        if cadastral_number:
                            print(f"✅ Найден кадастровый номер (первая ячейка): {cadastral_number}")
                            return cadastral_number
                        
            except Exception as e:
                print(f"⚠️  Ошибка при обработке строки: {e}")
                continue
        
        print("⚠️  Строка с 'здание' не найдена в таблице")
        return None
        
    except Exception as e:
        print(f"❌ Ошибка при извлечении кадастрового номера: {e}")
        import traceback
        traceback.print_exc()
        return None


def search_address(driver, address):
    """
    Выполняет поиск адреса на сайте и извлекает кадастровый номер.
    
    Args:
        driver: WebDriver экземпляр
        address: Адрес для поиска
    
    Returns:
        Кадастровый номер (str) или None если не найден
    """
    try:
        # Проверяем, что driver существует
        if driver is None:
            print("❌ WebDriver не инициализирован")
            return None
        
        # Проверяем, что страница загружена
        try:
            current_url = driver.current_url
            if not current_url or SITE_URL not in current_url:
                print(f"⚠️  Неожиданный URL: {current_url}, возвращаюсь на главную...")
                driver.get(SITE_URL)
                time.sleep(3)
        except Exception as e:
            print(f"⚠️  Ошибка при проверке URL: {e}, пытаюсь перезагрузить страницу...")
            try:
                driver.get(SITE_URL)
                time.sleep(3)
            except Exception as reload_error:
                print(f"❌ Не удалось перезагрузить страницу: {reload_error}")
                return None
        
        # Находим input элемент
        try:
            input_element = find_input_element(driver)
        except Exception as e:
            print(f"❌ Ошибка при поиске input элемента: {e}")
            return None
        
        if input_element is None:
            print("❌ Не удалось найти input элемент (возможно капча или страница не загрузилась)")
            return None
        
        # Очищаем поле и вводим адрес
        try:
            input_element.clear()
            input_element.send_keys(address)
            print(f"✍️  Введен адрес: {address}")
        except Exception as e:
            print(f"❌ Ошибка при вводе адреса: {e}")
            return None
        
        # Ожидание 3 секунды после ввода
        time.sleep(3)
        
        # Ищем первый элемент подсказки
        suggestion_selector = ".suggestions-value.w-icon"
        try:
            wait = WebDriverWait(driver, 5)
            first_suggestion = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, suggestion_selector))
            )
            print("✅ Найден элемент подсказки, нажимаю...")
            try:
                first_suggestion.click()
                print("✅ Клик по элементу подсказки выполнен!")
            except Exception as e:
                print(f"❌ Ошибка при клике по элементу подсказки: {e}")
                return None
            
            # Ожидание 3 секунды после клика по подсказке
            time.sleep(3)
            
            # Нажимаем на кнопку поиска
            button_selector = ".el-button.btnSearch.el-button--danger.el-button--small"
            try:
                search_button = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, button_selector))
                )
                print("✅ Найдена кнопка поиска, нажимаю...")
                try:
                    search_button.click()
                    print("✅ Клик по кнопке поиска выполнен!")
                except Exception as e:
                    print(f"❌ Ошибка при клике по кнопке поиска: {e}")
                    return None
                
                # Ожидание 3 секунды после клика по кнопке поиска
                print("⏳ Ожидание 3 секунды после клика по кнопке поиска...")
                time.sleep(3)
                
                # Извлекаем кадастровый номер из таблицы результатов
                try:
                    cadastral_number = extract_cadastral_number(driver)
                    return cadastral_number
                except Exception as e:
                    print(f"❌ Ошибка при извлечении кадастрового номера: {e}")
                    return None
                
            except TimeoutException:
                # Пробуем найти без ожидания
                try:
                    buttons = driver.find_elements(By.CSS_SELECTOR, button_selector)
                    if buttons:
                        try:
                            buttons[0].click()
                            print("✅ Клик по кнопке поиска выполнен!")
                        except Exception as e:
                            print(f"❌ Ошибка при клике по кнопке поиска: {e}")
                            return None
                        
                        # Ожидание 3 секунды после клика по кнопке поиска
                        print("⏳ Ожидание 3 секунды после клика по кнопке поиска...")
                        time.sleep(3)
                        
                        # Извлекаем кадастровый номер из таблицы результатов
                        try:
                            cadastral_number = extract_cadastral_number(driver)
                            return cadastral_number
                        except Exception as e:
                            print(f"❌ Ошибка при извлечении кадастрового номера: {e}")
                            return None
                    else:
                        print("⚠️  Кнопка поиска не найдена")
                        return None
                except Exception as e:
                    print(f"❌ Ошибка при поиске кнопки: {e}")
                    return None
        except TimeoutException:
            # Элемент подсказки не появился
            print("⚠️  Элемент подсказки не появился (адрес не найден на сайте)")
            return None
        except Exception as e:
            print(f"⚠️  Ошибка при поиске элемента подсказки: {e}")
            return None
            
    except Exception as e:
        print(f"❌ Критическая ошибка при обработке адреса: {e}")
        import traceback
        traceback.print_exc()
        return None


def process_addresses(driver, data, output_file):
    """
    Обрабатывает все адреса из данных.
    
    Args:
        driver: WebDriver экземпляр
        data: Словарь с данными из JSON
        output_file: Путь к выходному JSON файлу для периодического сохранения
    
    Returns:
        Обновленные данные
    """
    total = len(data.get('data', []))
    processed = 0
    skipped = 0
    found = 0
    not_found = 0
    
    print(f"\n📊 Всего адресов для обработки: {total}\n")
    
    for item in data.get('data', []):
        item_id = item.get('id', 'unknown')
        name = item.get('name', 'unknown')
        address = item.get('adres_part2')
        
        print(f"\n{'='*60}")
        print(f"ID: {item_id} | Название: {name}")
        print(f"Адрес: {address}")
        print(f"{'='*60}")
        
        # Пропускаем если адрес null
        if address is None:
            print("⏭️  Адрес null - пропускаю")
            item['cadastral_number'] = None
            skipped += 1
            processed += 1
            # Сохраняем результат сразу
            try:
                save_json_data(output_file, data)
            except Exception as e:
                print(f"⚠️  Ошибка при сохранении: {e}")
            print(f"\n📈 Прогресс: {processed}/{total} | Найдено: {found} | Не найдено: {not_found} | Пропущено: {skipped}")
            continue
        
        # Выполняем поиск с обработкой ошибок
        try:
            cadastral_number = search_address(driver, address)
        except Exception as e:
            print(f"❌ Критическая ошибка при поиске адреса: {e}")
            print("⏭️  Пропускаю этот адрес и продолжаю работу...")
            item['cadastral_number'] = None
            not_found += 1
            processed += 1
            # Сохраняем результат сразу
            try:
                save_json_data(output_file, data)
            except Exception as save_error:
                print(f"⚠️  Ошибка при сохранении: {save_error}")
            print(f"\n📈 Прогресс: {processed}/{total} | Найдено: {found} | Не найдено: {not_found} | Пропущено: {skipped}")
            continue
        
        # Сохраняем результат
        item['cadastral_number'] = cadastral_number
        
        if cadastral_number:
            found += 1
            print(f"✅ Кадастровый номер найден: {cadastral_number}")
        else:
            not_found += 1
            print("❌ Кадастровый номер не найден (cadastral_number = None)")
        
        # Сохраняем результат сразу после обработки каждого адреса
        try:
            save_json_data(output_file, data)
        except Exception as e:
            print(f"⚠️  Ошибка при сохранении: {e}")
        
        # Возвращаемся на главную страницу для следующего поиска
        try:
            print("🔄 Возвращаюсь на главную страницу...")
            driver.get(SITE_URL)
            print("⏳ Ожидание 3 секунды для загрузки главной страницы...")
            time.sleep(3)  # Ждем загрузки страницы
        except Exception as e:
            print(f"⚠️  Ошибка при возврате на главную страницу: {e}")
            print("⚠️  Продолжаю работу, но могут быть проблемы...")
            # Пробуем перезагрузить страницу
            try:
                time.sleep(2)
                driver.refresh()
                time.sleep(3)
            except Exception as refresh_error:
                print(f"❌ Критическая ошибка: не удалось восстановить работу браузера: {refresh_error}")
                print("⚠️  Останавливаю обработку для предотвращения потери данных")
                break
        
        processed += 1
        print(f"\n📈 Прогресс: {processed}/{total} | Найдено: {found} | Не найдено: {not_found} | Пропущено: {skipped}")
        
        # Небольшая пауза между запросами
        time.sleep(1)
    
    print(f"\n\n📊 Итоги:")
    print(f"  Всего обработано: {processed}")
    print(f"  Найдено: {found}")
    print(f"  Не найдено: {not_found}")
    print(f"  Пропущено (null): {skipped}")
    
    return data


def main():
    """Основная функция"""
    driver = None
    try:
        # Загружаем данные из входного JSON
        print(f"📂 Загружаю данные из {JSON_INPUT_FILE}")
        data = load_json_data(JSON_INPUT_FILE)
        
        # Инициализация драйвера
        driver = setup_driver()
        
        # Открываем сайт
        print(f"🌐 Открываю сайт: {SITE_URL}")
        driver.get(SITE_URL)
        
        # Ждем загрузки страницы
        time.sleep(3)
        
        # Обрабатываем все адреса
        updated_data = process_addresses(driver, data, JSON_OUTPUT_FILE)
        
        # Сохраняем результаты в выходной JSON
        print(f"\n💾 Сохраняю результаты в {JSON_OUTPUT_FILE}")
        save_json_data(JSON_OUTPUT_FILE, updated_data)
        
        print("\n✅ Обработка завершена!")
        
    except Exception as e:
        print(f"❌ Произошла ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            print("\n🔒 Закрываю браузер...")
            driver.quit()


if __name__ == "__main__":
    main()
