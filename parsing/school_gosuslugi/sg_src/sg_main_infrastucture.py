#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсинг страницы «Материально-техническое обеспечение…».

Источник школ:
  sg_data/sg_data_output/sd_test_5_output.json
Поле URL:
  "infrastructure": "https://.../materialno-tehnicheskoe-obespechenie-dostupnaya-sreda/"

Из блока «Условия для занятия физкультурой и спортом» (якорь #usloviya-dlya-zanyatiya-fizkulturoy-i-sportom)
собираются подписи карточек: a.object-item .object-item-text

Результат (полный объект школы + поле infrastucture):
  sg_data/sg_data_output/sd_test_5_output_infrastucture.json
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

SCRIPT_DIR = Path(__file__).resolve().parent
SG_ROOT = SCRIPT_DIR.parent
DATA_DIR = SG_ROOT / "sg_data"

INPUT_JSON = DATA_DIR / "sg_data_output" / "sd_2_stage_gosuslugi_output.json"
OUTPUT_JSON = DATA_DIR / "sg_data_output" / "sd_2_stage_gosuslugi_infrastucture_output.json"
ALL_HTML_DIR = DATA_DIR / "sg_data_output" / "html_infrastucture"


def normalize_text(value: str) -> str:
    return " ".join(value.split())


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
        "(KHTML, like Gecko) Chrome/156.0.8078.76 Safari/537.36"
    )
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(service=Service(), options=opts)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"},
    )
    return driver


def is_missing_link(link: object) -> bool:
    if link is None or not isinstance(link, str):
        return True
    cleaned = link.strip().lower()
    return cleaned == "" or cleaned == "нету в excel"


def safe_filename_part(value: object) -> str:
    text = str(value) if value is not None else "unknown"
    text = re.sub(r"[^0-9A-Za-zА-Яа-я._-]+", "_", text)
    text = text.strip("._")
    return text or "unknown"


def save_html(html: str, school: dict, idx: int, url: str) -> Path:
    ALL_HTML_DIR.mkdir(parents=True, exist_ok=True)
    school_id = safe_filename_part(school.get("id"))
    host = safe_filename_part(urlparse(url).netloc)
    filename = f"{idx:04d}_{school_id}_{host}.html"
    path = ALL_HTML_DIR / filename
    path.write_text(html, encoding="utf-8")
    return path


def parse_infrastucture_list(driver: webdriver.Chrome) -> list[str]:
    """Тексты из карточек a.object-item в секции про физкультуру и спорт."""
    items: list[str] = []
    try:
        anchor = driver.find_element(By.ID, "usloviya-dlya-zanyatiya-fizkulturoy-i-sportom")
        container = anchor.find_element(
            By.XPATH,
            "./ancestor::div[contains(@class, 'tpl-container')][1]",
        )
        for el in container.find_elements(By.CSS_SELECTOR, "a.object-item .object-item-text"):
            text = normalize_text(el.text)
            if text:
                items.append(text)
    except Exception:
        pass
    return list(dict.fromkeys(items))


def write_output(path: Path, data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    input_json = Path(sys.argv[1]) if len(sys.argv) > 1 else INPUT_JSON
    output_json = Path(sys.argv[2]) if len(sys.argv) > 2 else OUTPUT_JSON

    schools = json.loads(input_json.read_text(encoding="utf-8"))
    result_data: list[dict] = []

    driver = build_driver()
    try:
        total = len(schools)
        for idx, school in enumerate(schools, start=1):
            school_copy = dict(school)
            infra_url = school_copy.get("infrastructure")

            if is_missing_link(infra_url):
                result_data.append(school_copy)
                write_output(output_json, result_data)
                print(f"[{idx}/{total}] Пропуск (нет infrastructure): id={school_copy.get('id')}")
                continue

            driver.get(str(infra_url))
            WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(1.5)
            html = driver.page_source

            html_path = save_html(html, school_copy, idx, str(infra_url))
            infr_list = parse_infrastucture_list(driver)
            school_copy["infrastucture"] = infr_list

            result_data.append(school_copy)
            write_output(output_json, result_data)
            print(
                f"[{idx}/{total}] OK: id={school_copy.get('id')} "
                f"infrastucture={infr_list} html={html_path}"
            )
    finally:
        driver.quit()

    print(f"[OK] Результат: {output_json}")


if __name__ == "__main__":
    main()
