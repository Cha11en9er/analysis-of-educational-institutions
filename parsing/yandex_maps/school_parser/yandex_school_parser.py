#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер школ Яндекс.Карт на Selenium.
Получает HTML код страницы с обходом детекта парсеров.
"""

import os
import time
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


def setup_driver(headless: bool = False) -> webdriver.Chrome:
    """
    Настройка Chrome драйвера с обходом детекта парсеров
    
    Args:
        headless: Запускать браузер в фоновом режиме
    
    Returns:
        Настроенный Chrome WebDriver
    """
    chrome_options = Options()
    
    if headless:
        chrome_options.add_argument("--headless")
    
    # Базовые опции для стабильности
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Обход детекта автоматизации
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    # Реалистичный User-Agent
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    
    # Отключение изображений для ускорения (опционально)
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2,
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    # Дополнительные опции для обхода детекта
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    # Скрываем признаки автоматизации через JavaScript
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Переопределяем plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Переопределяем languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ru-RU', 'ru', 'en-US', 'en']
            });
            
            // Переопределяем permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """
    })
    
    return driver


def get_page_html(url: str, wait_timeout: int = 10, scroll: bool = True) -> Optional[str]:
    """
    Получает HTML код страницы Яндекс.Карт
    
    Args:
        url: URL страницы для парсинга
        wait_timeout: Таймаут ожидания загрузки элементов (секунды)
        scroll: Прокручивать страницу для загрузки динамического контента
    
    Returns:
        HTML код страницы или None в случае ошибки
    """
    driver = None
    try:
        driver = setup_driver(headless=False)
        driver.get(url)
        
        # Ждём загрузки основного контента
        try:
            WebDriverWait(driver, wait_timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except TimeoutException:
            print(f"[warn] Таймаут ожидания загрузки страницы: {url}")
        
        time.sleep(2.0)  # Дополнительная пауза для загрузки динамического контента
        
        # Прокрутка для загрузки всех элементов (если нужно)
        if scroll:
            try:
                # Прокручиваем страницу несколько раз
                for i in range(5):
                    driver.execute_script('window.scrollBy(0, 500);')
                    time.sleep(0.5)
                
                # Прокручиваем вверх
                driver.execute_script('window.scrollTo(0, 0);')
                time.sleep(1.0)
            except Exception as e:
                print(f"[warn] Не удалось выполнить прокрутку: {e}")
        
        # Получаем HTML
        html = driver.page_source
        return html
        
    except Exception as e:
        print(f"[error] Ошибка при получении HTML: {e}")
        return None
        
    finally:
        if driver:
            driver.quit()


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
        return True
    except Exception as e:
        print(f"[error] Не удалось сохранить HTML: {e}")
        return False


def main():
    """Пример использования"""
    # URL из комментария в файле
    url = "https://yandex.ru/maps/194/saratov/search/%D1%88%D0%BA%D0%BE%D0%BB%D1%8B%20%D1%81%D0%B0%D1%80%D0%B0%D1%82%D0%BE%D0%B2%D0%B0/?ll=46.153670%2C51.551834&sctx=ZAAAAAgCEAAaKAoSCZ8ENufgD0dAESRh304iwElAEhIJj3IwmwDDzj8RNX9Ma9PYtj8iBgABAgMEBSgKOABAildIAWoCcnWdAc3MzD2gAQCoAQC9ASXHyvrCAYgB7MzUg9ICsq6o6gODoaicBJKag5QE98GH7b0G76SN1OYFvoOGypQFuLKMlwSNp%2B6cBPGLwfC1Ari4pODYAsyd4IoE5re57AOs57zBjwOaiNL9A9uxnMK%2FAoLM7owEq%2Bbt8QO3%2FJ3lA%2BT90oTCBdfnxvAD2sXUwQSe4Ovg3QOD25aIBJ2L8p%2F1A4ICG9GI0LrQvtC70Ysg0YHQsNGA0LDRgtC%2B0LLQsIoCUTE4NDEwNjI0MCQxODQxMDYyMzQkMTg0MTA2MjM4JDM3MzEwNzcyNjk3JDE4NDEwNjI1MiQxODQxMDYyNTQkMTg0MTA2MjUwJDE4NDEwNTkyNJICAzE5NJoCDGRlc2t0b3AtbWFwc6oCGDk4MTQzNjkxNDA5LDIxODE0NjkzNDQ1NdoCKAoSCQflfRzNFUdAEbLOgvj5w0lAEhIJAN1CVyJQ9z8RwND1M6tN4T%2FgAgE%3D&sll=46.153670%2C51.551834&sspn=1.457064%2C0.540483&z=10.4"
    
    print(f"[info] Получение HTML для: {url}")
    html = get_page_html(url, wait_timeout=15, scroll=True)
    
    if html:
        # Сохраняем в файл для анализа
        output_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        output_file = os.path.join(output_dir, "yandex_maps_schools.html")
        save_html_to_file(html, output_file)
        print(f"[info] Размер HTML: {len(html)} символов")
    else:
        print("[error] Не удалось получить HTML")


if __name__ == "__main__":
    main()
