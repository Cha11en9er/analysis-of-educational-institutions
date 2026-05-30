#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсинг карточек школ с сайтов Госуслуг.

Что делает:
1) Берет школы из входного JSON.
2) Для каждой `link_gosuslugi` загружает страницу (Selenium, headless Chrome).
3) Извлекает:
   - specialization (профильные направления),
   - результаты (Olympiads / EGE / VUZ),
   - infrastructure (ссылка "Вся инфраструктура", если есть).
4) После каждой школы сразу перезаписывает выходной JSON (инкрементальная запись).

Требуется: Chrome/Chromium и selenium (драйвер Selenium 4.6+ обычно подтягивает сам).
"""

from __future__ import annotations

import sys
import time
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

SCRIPT_DIR = Path(__file__).resolve().parent
SG_ROOT = SCRIPT_DIR.parent
DATA_DIR = SG_ROOT / "sg_data"
INPUT_JSON = DATA_DIR / "sg_data_input" / "sd_2_stage_gosuslugi.json"
OUTPUT_JSON = DATA_DIR / "sg_data_output" / "sd_2_stage_gosuslugi_output.json"
ALL_HTML_DIR = DATA_DIR / "sg_data_output" / "html_pages"


def build_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--lang=ru-RU")
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(service=Service(), options=opts)

    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});",
        },
    )
    return driver


def normalize_text(value: str) -> str:
    return " ".join(value.split())


def is_missing_link(link_gosuslugi: object) -> bool:
    if link_gosuslugi is None:
        return True
    if not isinstance(link_gosuslugi, str):
        return True
    cleaned = link_gosuslugi.strip().lower()
    return cleaned == "" or cleaned == "нету в excel"


def parse_school_page(driver: webdriver.Chrome, url: str) -> tuple[dict, str]:
    driver.get(url)
    WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(1.5)

    html = driver.page_source

    parsed: dict = {}

    # 1) specialization
    specialization = []
    try:
        # Встречаются как минимум два шаблона:
        # 1) ul.gw-complex-nav__3rd-level a.gw-complex-nav__link
        # 2) меню с a[href*='/profilnye-napravleniya/'] и span.menu-item-text
        selectors = [
            "ul.gw-complex-nav__3rd-level a.gw-complex-nav__link",
            "a[href*='/profilnye-napravleniya/'] span.menu-item-text",
            "a[href*='/profilnye-napravleniya/']",
        ]
        for selector in selectors:
            for link_el in driver.find_elements(By.CSS_SELECTOR, selector):
                text = normalize_text(link_el.text)
                if not text:
                    continue
                low = text.lower()
                # Не записываем служебные пункты меню
                if "профильные направления" in low or "о профильной подготовке" in low:
                    continue
                specialization.append(text)
    except Exception:
        specialization = []

    if specialization:
        # сохраняем порядок и убираем дубли
        parsed["specialization"] = list(dict.fromkeys(specialization))

    # 2) KPI блоки «Результаты школы»
    # У части школ карточки — <div class="object-item">, у других — <a class="object-item">.
    # Скопируем только внутри блока с якорем #rezultaty-shkoly, иначе «ВУЗ» цепляется с другого места страницы.
    olympiads = []
    try:
        metric_root = driver
        try:
            anchor = driver.find_element(By.ID, "rezultaty-shkoly")
            metric_root = anchor.find_element(
                By.XPATH,
                "./ancestor::div[contains(@class, 'tpl-block-273')][1]",
            )
        except Exception:
            pass

        metric_items = metric_root.find_elements(
            By.CSS_SELECTOR,
            "a.object-item, div.object-item",
        )
        for item in metric_items:
            number_nodes = item.find_elements(By.CSS_SELECTOR, ".tpl-text-header6")
            desc_nodes = item.find_elements(By.CSS_SELECTOR, ".tpl-text-default-paragraph")
            if not number_nodes or not desc_nodes:
                continue

            number = normalize_text(number_nodes[0].text)
            desc = normalize_text(desc_nodes[0].text)
            if not number or not desc:
                continue

            line = f"{number} - {desc}"
            low_desc = desc.lower()

            if "вуз" in low_desc:
                parsed["VUZ"] = line
            elif "егэ" in low_desc:
                parsed["EGE"] = line
            elif "олимпиад" in low_desc:
                olympiads.append(line)
    except Exception:
        pass

    if olympiads:
        parsed["Olympiads"] = olympiads

    # 3) infrastructure
    try:
        infrastructure_nodes = driver.find_elements(
            By.XPATH,
            "//a[contains(normalize-space(.), 'Вся инфраструктура')]",
        )
        if infrastructure_nodes:
            href = infrastructure_nodes[0].get_attribute("href") or ""
            if href.strip():
                base = f"{urlparse(url).scheme}://{urlparse(url).netloc}/"
                parsed["infrastructure"] = urljoin(base, href)
    except Exception:
        pass

    return parsed, html


def write_output(path: Path, data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_filename_part(value: object) -> str:
    text = str(value) if value is not None else "unknown"
    text = re.sub(r"[^0-9A-Za-zА-Яа-я._-]+", "_", text)
    text = text.strip("._")
    return text or "unknown"


def write_school_html(html: str, school: dict, idx: int, source_url: str) -> Path:
    ALL_HTML_DIR.mkdir(parents=True, exist_ok=True)
    school_id = safe_filename_part(school.get("id"))
    host = safe_filename_part(urlparse(source_url).netloc)
    filename = f"{idx:04d}_{school_id}_{host}.html"
    output_path = ALL_HTML_DIR / filename
    output_path.write_text(html, encoding="utf-8")
    return output_path


def main() -> None:
    input_json = Path(sys.argv[1]) if len(sys.argv) > 1 else INPUT_JSON
    output_json = Path(sys.argv[2]) if len(sys.argv) > 2 else OUTPUT_JSON

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    input_data = json.loads(input_json.read_text(encoding="utf-8"))
    result_data: list[dict] = []

    driver = build_driver()
    try:
        for idx, school in enumerate(input_data, start=1):
            school_copy = dict(school)
            link_gosuslugi = school_copy.get("link_gosuslugi")

            if is_missing_link(link_gosuslugi):
                result_data.append(school_copy)
                write_output(output_json, result_data)
                print(f"[{idx}/{len(input_data)}] Пропуск (нет ссылки): id={school_copy.get('id')}")
                continue

            parsed_fields, html = parse_school_page(driver, str(link_gosuslugi))
            school_copy.update(parsed_fields)
            result_data.append(school_copy)

            per_school_html = write_school_html(html, school_copy, idx, str(link_gosuslugi))

            # инкрементальная запись после каждой школы
            write_output(output_json, result_data)
            print(
                f"[{idx}/{len(input_data)}] OK: id={school_copy.get('id')} "
                f"url={link_gosuslugi} html={per_school_html}"
            )
    finally:
        driver.quit()

    print(f"[OK] Результат сохранён: {output_json}")


if __name__ == "__main__":
    main()
