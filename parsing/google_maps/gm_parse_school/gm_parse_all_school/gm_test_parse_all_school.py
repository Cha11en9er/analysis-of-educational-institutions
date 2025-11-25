#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Простой тестовый скрипт для проверки открытия Google Maps.
Минимальные настройки Selenium без обхода детекта.
Пользователь сам прокручивает страницу, парсер только сохраняет HTML.
"""

import os
import sys
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Попытка импортировать keyboard для перехвата клавиш
try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False
    print("[warn] Библиотека 'keyboard' не установлена. Используется альтернативный метод.")


def wait_for_key_press(key: str = 'p', message: str = None) -> None:
    """
    Ожидает нажатия указанной клавиши перед продолжением выполнения.
    
    Args:
        key: Клавиша для ожидания (по умолчанию 'p')
        message: Сообщение для вывода (опционально)
    """
    if message:
        print(f"\n{message}")
    else:
        print(f"\n[info] Ожидание нажатия клавиши '{key.upper()}'...")
    
    if KEYBOARD_AVAILABLE:
        # Используем библиотеку keyboard для перехвата клавиш
        print(f"[info] Нажмите '{key.upper()}' в любом месте...")
        keyboard.wait(key)
        print(f"[info] Клавиша '{key.upper()}' нажата, продолжаем...")
    else:
        # Альтернативный метод через input (работает только в консоли)
        if sys.platform == 'win32':
            try:
                import msvcrt
                print(f"[info] Нажмите '{key.upper()}' в консоли...")
                while True:
                    if msvcrt.kbhit():
                        char = msvcrt.getch().decode('utf-8').lower()
                        if char == key.lower():
                            print(f"[info] Клавиша '{key.upper()}' нажата, продолжаем...")
                            break
            except Exception:
                # Если msvcrt не работает, используем input
                input(f"[info] Нажмите Enter для продолжения (альтернативный метод)...")
        else:
            # Для Linux/Mac используем input
            input(f"[info] Нажмите Enter для продолжения (альтернативный метод)...")


def save_html_to_file(html: str, filepath: str) -> bool:
    """
    Сохраняет HTML в файл
    
    Args:
        html: HTML код для сохранения
        filepath: Путь к файлу для сохранения
    
    Returns:
        True если успешно, False в случае ошибки
    """
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[info] HTML сохранён: {filepath}")
        print(f"[info] Размер HTML: {len(html)} символов")
        return True
    except Exception as e:
        print(f"[error] Не удалось сохранить HTML: {e}")
        return False




def main():
    """Простое открытие Google Maps с минимальными настройками"""
    # URL из оригинального файла
    url = "https://www.google.com/maps/search/%D1%88%D0%BA%D0%BE%D0%BB%D1%8B+%D1%81%D0%B0%D1%80%D0%B0%D1%82%D0%BE%D0%B2%D0%B0/@51.5642244,45.8778875,12z?entry=ttu&g_ep=EgoyMDI1MTExNy4wIKXMDSoASAFQAw%3D%3D"
    
    # Минимальные настройки Chrome
    chrome_options = Options()
    
    # Только базовые опции для стабильности
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Без обхода детекта - пусть сайт видит обычный браузер
    # Не добавляем --disable-blink-features=AutomationControlled
    # Не добавляем excludeSwitches
    # Не добавляем маскировку через JavaScript
    
    print("[info] Инициализация Chrome WebDriver с минимальными настройками...")
    driver = None
    
    try:
        # Создаём драйвер
        driver = webdriver.Chrome(options=chrome_options)
        
        print(f"[info] Открытие страницы: {url}")
        driver.get(url)
        
        print("[info] Страница открыта. Ожидание загрузки...")
        time.sleep(3.0)  # Пауза для загрузки страницы
        
        # Шаг 2: Ждём нажатия 'P' для начала ручной прокрутки
        wait_for_key_press('p', 
            "[info] ========================================\n"
            "[info] Страница загружена.\n"
            "[info] Пройдите капчу, если требуется.\n"
            "[info] После прохождения капчи нажмите 'P' для начала ручной прокрутки.\n"
            "[info] ========================================")
        
        # Шаг 3: Пользователь сам прокручивает страницу
        print("[info] Прокрутите страницу вниз вручную для загрузки всех данных.")
        print("[info] Когда закончите прокрутку, нажмите 'P' для сохранения HTML.")
        
        # Шаг 4: Ждём нажатия 'P' после завершения прокрутки
        wait_for_key_press('p',
            "[info] ========================================\n"
            "[info] Нажмите 'P' когда закончите прокрутку.\n"
            "[info] HTML будет сохранён.\n"
            "[info] ========================================")
        
        # Шаг 5: Сохраняем HTML DOM страницы
        print("[info] Получение HTML DOM страницы...")
        html = driver.page_source
        
        # Определяем путь к файлу для сохранения
        script_dir = os.path.dirname(os.path.abspath(__file__))
        gm_data_dir = os.path.join(script_dir, "..", "..", "gm_data")
        gm_data_dir = os.path.abspath(os.path.normpath(gm_data_dir))
        
        # Путь для HTML
        html_dir = os.path.join(gm_data_dir, "gm_debug_html")
        html_file = os.path.join(html_dir, "gm_debug_html.html")
        
        print(f"[info] Сохранение HTML в: {html_file}")
        save_html_to_file(html, html_file)
        
        print("[info] HTML сохранён. Нажмите 'P' для закрытия браузера.")
        wait_for_key_press('p')
        
        print("[info] Закрытие браузера...")
        
    except Exception as e:
        print(f"[error] Ошибка: {e}")
        
    finally:
        if driver:
            driver.quit()
            print("[info] Браузер закрыт")


if __name__ == "__main__":
    main()

# test link - https://www.google.com/maps/place/%D0%9C%D0%9E%D0%A3+%22%D0%A1%D1%80%D0%B5%D0%B4%D0%BD%D1%8F%D1%8F+%D0%BE%D0%B1%D1%89%D0%B5%D0%BE%D0%B1%D1%80%D0%B0%D0%B7%D0%BE%D0%B2%D0%B0%D1%82%D0%B5%D0%BB%D1%8C%D0%BD%D0%B0%D1%8F+%D1%88%D0%BA%D0%BE%D0%BB%D0%B0+%E2%84%96+21+%D0%B8%D0%BC.+%D0%9F.%D0%90.+%D0%A1%D1%82%D0%BE%D0%BB%D1%8B%D0%BF%D0%B8%D0%BD%D0%B0%22/data=!4m7!3m6!1s0x4114c7cebe0d1817:0xbd841d8bae19c3ce!8m2!3d51.5415964!4d46.0235912!16s%2Fg%2F1hc45lj30!19sChIJFxgNvs7HFEERzsMZrosdhL0?authuser=0&amp;hl=ru&amp;rclk=1