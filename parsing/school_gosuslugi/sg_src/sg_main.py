#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсинг карточек школ с сайтов Госуслуг.

Что делает:
1) Берет школы из входного JSON.
2) Для каждой `link_gosuslugi` загружает страницу (Selenium Chrome).
3) Извлекает specialization / EGE / VUZ / Olympiads / Medals / other_results,
   плюс snapshot за целевой год (EGE_2026 и т.п.; null = не обновили).
4) Старые значения не затираются (*_prev / *_history).
5) Инкрементальная запись; мерж в существующий output.
6) Headed-режим, паузы, ретраи, ожидание капчи — чтобы прогон не рвался.

Примеры:
  python sg_main.py --headed --year 2026
  python sg_main.py --headed --skip-done
  python sg_main.py --id 10 --headed
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from selenium import webdriver
from selenium.common.exceptions import (
    InvalidSessionIdException,
    TimeoutException,
    WebDriverException,
)
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

DEFAULT_TARGET_YEAR = 2026
DEFAULT_PAUSE_SEC = 2.5
DEFAULT_PAUSE_JITTER_SEC = 1.5
DEFAULT_RETRIES = 3
DEFAULT_CAPTCHA_WAIT_SEC = 600
DEFAULT_PAGE_LOAD_WAIT_SEC = 2.0
DRIVER_RECYCLE_EVERY = 40

RESULT_KEYS = ("EGE", "VUZ", "Olympiads", "Medals", "other_results")
YEAR_RE = re.compile(r"(20\d{2})")

CAPTCHA_CSS = [
    "iframe[src*='captcha']",
    "iframe[src*='smartcaptcha']",
    ".CheckboxCaptcha",
    "#captcha",
    "[class*='Captcha']",
    "[class*='captcha']",
    "[id*='captcha']",
]

BLOCK_TEXT_MARKERS = (
    "captcha",
    "smartcaptcha",
    "подтвердите, что вы не робот",
    "я не робот",
    "доступ ограничен",
    "too many requests",
    "429",
    "cloudflare",
    "checking your browser",
    "внимание! с вашего ip",
)


def build_driver(*, headed: bool = True) -> webdriver.Chrome:
    opts = Options()
    if not headed:
        opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--start-maximized")
    opts.add_argument("--lang=ru-RU")
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(service=Service(), options=opts)
    driver.set_page_load_timeout(60)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});",
        },
    )
    return driver


def safe_quit(driver: webdriver.Chrome | None) -> None:
    if driver is None:
        return
    try:
        driver.quit()
    except Exception:
        pass


def normalize_text(value: str) -> str:
    return " ".join(value.split())


def is_missing_link(link_gosuslugi: object) -> bool:
    if link_gosuslugi is None:
        return True
    if not isinstance(link_gosuslugi, str):
        return True
    cleaned = link_gosuslugi.strip().lower()
    return cleaned == "" or cleaned == "нету в excel"


def extract_years(text: str) -> list[int]:
    return [int(y) for y in YEAR_RE.findall(text or "")]


def is_for_target_year(text: str, target_year: int) -> bool:
    """
    Карточка относится к целевому году, если:
    - в тексте явно указан target_year, или
    - год в тексте не указан вовсе (типично «олимпиады за 3 года»).
    """
    years = extract_years(text)
    if not years:
        return True
    return target_year in years


def pick_scalar_for_year(value: Any, target_year: int) -> Any:
    if value is None or value == "" or value == []:
        return None
    if isinstance(value, list):
        matched = [item for item in value if is_for_target_year(str(item), target_year)]
        return matched or None
    return value if is_for_target_year(str(value), target_year) else None


def build_year_snapshot(parsed: dict[str, Any], target_year: int) -> dict[str, Any]:
    return {
        f"EGE_{target_year}": pick_scalar_for_year(parsed.get("EGE"), target_year),
        f"VUZ_{target_year}": pick_scalar_for_year(parsed.get("VUZ"), target_year),
        f"Olympiads_{target_year}": pick_scalar_for_year(parsed.get("Olympiads"), target_year),
        f"Medals_{target_year}": pick_scalar_for_year(parsed.get("Medals"), target_year),
        f"other_results_{target_year}": pick_scalar_for_year(
            parsed.get("other_results"), target_year
        ),
        "results_target_year": target_year,
    }


def empty_year_snapshot(target_year: int) -> dict[str, Any]:
    return {
        f"EGE_{target_year}": None,
        f"VUZ_{target_year}": None,
        f"Olympiads_{target_year}": None,
        f"Medals_{target_year}": None,
        f"other_results_{target_year}": None,
        "results_target_year": target_year,
    }


def page_has_captcha_or_block(driver: webdriver.Chrome) -> bool:
    try:
        for css in CAPTCHA_CSS:
            for el in driver.find_elements(By.CSS_SELECTOR, css):
                try:
                    if el.is_displayed():
                        return True
                except Exception:
                    return True
    except Exception:
        pass

    try:
        title = (driver.title or "").lower()
        body_snip = ""
        try:
            body_snip = (driver.find_element(By.TAG_NAME, "body").text or "")[:2500].lower()
        except Exception:
            body_snip = (driver.page_source or "")[:4000].lower()
        blob = f"{title}\n{body_snip}"
        return any(marker in blob for marker in BLOCK_TEXT_MARKERS)
    except Exception:
        return False


def wait_out_captcha(
    driver: webdriver.Chrome,
    *,
    timeout_sec: float,
    headed: bool,
) -> None:
    if not page_has_captcha_or_block(driver):
        return

    print(
        f"[CAPTCHA] Обнаружена капча/блок. "
        f"{'Решите в окне Chrome — жду до ' + str(int(timeout_sec)) + 'с.' if headed else 'Headless: жду исчезновения.'}",
        flush=True,
    )
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        time.sleep(5)
        if not page_has_captcha_or_block(driver):
            print("[CAPTCHA] Снято, продолжаю.", flush=True)
            time.sleep(1.0)
            return
        left = int(deadline - time.time())
        if left % 30 < 5:
            print(f"[CAPTCHA] Ещё жду... осталось ~{left}с", flush=True)

    raise TimeoutError(f"Капча/блок не сняты за {int(timeout_sec)}с")


def pause_between(pause_sec: float, jitter_sec: float) -> None:
    delay = max(0.0, pause_sec + random.uniform(0, jitter_sec))
    if delay > 0:
        time.sleep(delay)


def extract_fields_from_dom(driver: webdriver.Chrome, url: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}

    specialization: list[str] = []
    try:
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
                if "профильные направления" in low or "о профильной подготовке" in low:
                    continue
                specialization.append(text)
    except Exception:
        specialization = []

    if specialization:
        parsed["specialization"] = list(dict.fromkeys(specialization))

    olympiads: list[str] = []
    medals: list[str] = []
    other_results: list[str] = []
    all_kpi_raw: list[str] = []
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

            number = normalize_text(
                number_nodes[0].get_attribute("textContent") or number_nodes[0].text or ""
            )
            desc = normalize_text(
                desc_nodes[0].get_attribute("textContent") or desc_nodes[0].text or ""
            )
            if not number or not desc:
                continue

            line = f"{number} - {desc}"
            if line in all_kpi_raw:
                continue
            all_kpi_raw.append(line)
            low_desc = desc.lower()

            if "вуз" in low_desc:
                parsed["VUZ"] = line
            elif "егэ" in low_desc:
                parsed["EGE"] = line
            elif "олимпиад" in low_desc:
                olympiads.append(line)
            elif "медал" in low_desc:
                medals.append(line)
            else:
                other_results.append(line)
    except Exception:
        pass

    parsed["Olympiads"] = olympiads
    parsed["Medals"] = medals
    parsed["other_results"] = other_results
    parsed["results_kpi_raw"] = all_kpi_raw

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

    return parsed


def parse_school_page(
    driver: webdriver.Chrome,
    url: str,
    *,
    target_year: int = DEFAULT_TARGET_YEAR,
    page_load_wait_sec: float = DEFAULT_PAGE_LOAD_WAIT_SEC,
    captcha_wait_sec: float = DEFAULT_CAPTCHA_WAIT_SEC,
    headed: bool = True,
) -> tuple[dict, str]:
    driver.get(url)
    WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(page_load_wait_sec)

    wait_out_captcha(driver, timeout_sec=captcha_wait_sec, headed=headed)

    # после капчи страница могла обновиться
    time.sleep(0.8)
    html = driver.page_source
    parsed = extract_fields_from_dom(driver, url)
    parsed.update(build_year_snapshot(parsed, target_year))
    return parsed, html


def parse_school_page_with_retries(
    driver: webdriver.Chrome,
    url: str,
    *,
    target_year: int,
    retries: int,
    page_load_wait_sec: float,
    captcha_wait_sec: float,
    headed: bool,
) -> tuple[dict, str, webdriver.Chrome]:
    """Возвращает (parsed, html, driver). Driver может быть пересоздан при падении сессии."""
    last_error: Exception | None = None
    current = driver

    for attempt in range(1, retries + 1):
        try:
            parsed, html = parse_school_page(
                current,
                url,
                target_year=target_year,
                page_load_wait_sec=page_load_wait_sec,
                captcha_wait_sec=captcha_wait_sec,
                headed=headed,
            )
            return parsed, html, current
        except (InvalidSessionIdException, WebDriverException) as exc:
            last_error = exc
            print(
                f"[RETRY] Сессия браузера сломалась (попытка {attempt}/{retries}): {exc}",
                flush=True,
            )
            safe_quit(current)
            time.sleep(min(5 * attempt, 20))
            current = build_driver(headed=headed)
        except TimeoutError as exc:
            last_error = exc
            print(f"[RETRY] Таймаут/капча (попытка {attempt}/{retries}): {exc}", flush=True)
            time.sleep(min(8 * attempt, 40))
            try:
                current.refresh()
            except Exception:
                safe_quit(current)
                current = build_driver(headed=headed)
        except Exception as exc:
            last_error = exc
            print(
                f"[RETRY] Ошибка парсинга (попытка {attempt}/{retries}): {exc}",
                flush=True,
            )
            time.sleep(min(5 * attempt, 25))

    assert last_error is not None
    raise last_error


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


def load_existing_output(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _is_empty_result(value: Any) -> bool:
    return value is None or value == "" or value == []


def archive_previous_values(existing: dict[str, Any], new_fields: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(new_fields)
    for key in RESULT_KEYS:
        if key not in new_fields:
            continue
        old = existing.get(key)
        new = new_fields[key]
        if _is_empty_result(old):
            continue
        if old == new:
            if existing.get(f"{key}_prev") is not None:
                enriched[f"{key}_prev"] = existing[f"{key}_prev"]
            if existing.get(f"{key}_history"):
                enriched[f"{key}_history"] = existing[f"{key}_history"]
            continue

        history = list(existing.get(f"{key}_history") or [])
        prev = existing.get(f"{key}_prev")
        if prev is not None and prev != old and prev not in history:
            history.append(prev)
        if old not in history:
            history.append(old)

        enriched[f"{key}_prev"] = old
        enriched[f"{key}_history"] = history

    return enriched


def apply_parsed_fields(school: dict[str, Any], parsed_fields: dict[str, Any]) -> dict[str, Any]:
    updated = dict(school)
    archived = archive_previous_values(school, parsed_fields)
    updated.update(archived)
    updated["results_parsed_at"] = datetime.now(timezone.utc).isoformat()
    updated.pop("parse_error", None)
    return updated


def already_done(school: dict[str, Any], target_year: int) -> bool:
    if school.get("parse_error"):
        return False
    if school.get("results_target_year") != target_year:
        return False
    if not school.get("results_parsed_at"):
        return False
    # снимок за год уже записан (даже если все null — это тоже результат)
    return f"EGE_{target_year}" in school


def filter_schools(
    schools: list[dict],
    *,
    ids: set[int] | None,
    limit: int,
) -> list[dict]:
    selected = schools
    if ids:
        selected = [s for s in selected if s.get("id") in ids]
    if limit and limit > 0:
        selected = selected[:limit]
    return selected


def upsert_school(result_data: list[dict], school: dict) -> list[dict]:
    school_id = school.get("id")
    for idx, existing in enumerate(result_data):
        if existing.get("id") == school_id:
            result_data[idx] = school
            return result_data
    result_data.append(school)
    return result_data


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Парсинг карточек школ с Госуслуг")
    parser.add_argument("input_json", nargs="?", default=str(INPUT_JSON))
    parser.add_argument("output_json", nargs="?", default=str(OUTPUT_JSON))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--id", type=int, action="append", dest="ids")
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--year", type=int, default=DEFAULT_TARGET_YEAR)
    parser.add_argument(
        "--headed",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Окно Chrome (по умолчанию включено; --no-headed = headless)",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=DEFAULT_PAUSE_SEC,
        help=f"Базовая пауза между школами, сек (default {DEFAULT_PAUSE_SEC})",
    )
    parser.add_argument(
        "--pause-jitter",
        type=float,
        default=DEFAULT_PAUSE_JITTER_SEC,
        help=f"Случайная добавка к паузе, сек (default {DEFAULT_PAUSE_JITTER_SEC})",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=f"Ретраи на школу (default {DEFAULT_RETRIES})",
    )
    parser.add_argument(
        "--captcha-wait",
        type=float,
        default=DEFAULT_CAPTCHA_WAIT_SEC,
        help=f"Сколько ждать ручного решения капчи, сек (default {DEFAULT_CAPTCHA_WAIT_SEC})",
    )
    parser.add_argument(
        "--page-wait",
        type=float,
        default=DEFAULT_PAGE_LOAD_WAIT_SEC,
        help=f"Пауза после загрузки страницы, сек (default {DEFAULT_PAGE_LOAD_WAIT_SEC})",
    )
    parser.add_argument(
        "--skip-done",
        action="store_true",
        help="Пропускать школы, уже успешно снятые за --year",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    input_json = Path(args.input_json)
    output_json = Path(args.output_json)
    ids = set(args.ids) if args.ids else None
    target_year = args.year
    headed = bool(args.headed)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    input_data = json.loads(input_json.read_text(encoding="utf-8"))
    if not isinstance(input_data, list):
        raise SystemExit("Ожидается JSON-массив школ во входном файле")

    existing = [] if args.fresh else load_existing_output(output_json)
    existing_by_id = {s.get("id"): s for s in existing if isinstance(s, dict)}
    result_data: list[dict] = [] if args.fresh else list(existing)

    to_process = filter_schools(input_data, ids=ids, limit=args.limit)
    if not to_process:
        raise SystemExit("Нет школ для обработки (проверьте --id / --limit)")

    print(
        f"[INFO] К обработке: {len(to_process)} школ "
        f"(ids={sorted(ids) if ids else 'все'}, limit={args.limit or 'нет'}, "
        f"year={target_year}, headed={headed}, pause={args.pause}+jitter{args.pause_jitter}, "
        f"retries={args.retries}, skip_done={args.skip_done})",
        flush=True,
    )

    driver = build_driver(headed=headed)
    parsed_ok = 0
    skipped = 0
    failed = 0
    processed_since_recycle = 0

    try:
        for idx, school in enumerate(to_process, start=1):
            school_id = school.get("id")
            base = dict(existing_by_id.get(school_id, school))
            base.update(school)

            if args.skip_done and already_done(base, target_year):
                skipped += 1
                print(
                    f"[{idx}/{len(to_process)}] SKIP done: id={school_id}",
                    flush=True,
                )
                continue

            link_gosuslugi = base.get("link_gosuslugi")
            if is_missing_link(link_gosuslugi):
                no_link = dict(base)
                no_link.update(empty_year_snapshot(target_year))
                no_link["results_parsed_at"] = datetime.now(timezone.utc).isoformat()
                no_link.pop("parse_error", None)
                result_data = upsert_school(result_data, no_link)
                existing_by_id[school_id] = no_link
                write_output(output_json, result_data)
                skipped += 1
                print(
                    f"[{idx}/{len(to_process)}] Пропуск (нет ссылки): id={school_id} "
                    f"- {target_year}=null",
                    flush=True,
                )
                continue

            try:
                parsed_fields, html, driver = parse_school_page_with_retries(
                    driver,
                    str(link_gosuslugi),
                    target_year=target_year,
                    retries=max(1, args.retries),
                    page_load_wait_sec=args.page_wait,
                    captcha_wait_sec=args.captcha_wait,
                    headed=headed,
                )
                school_copy = apply_parsed_fields(base, parsed_fields)
                result_data = upsert_school(result_data, school_copy)
                existing_by_id[school_id] = school_copy
                per_school_html = write_school_html(
                    html, school_copy, idx, str(link_gosuslugi)
                )
                write_output(output_json, result_data)
                parsed_ok += 1
                processed_since_recycle += 1

                print(
                    f"[{idx}/{len(to_process)}] OK: id={school_id} url={link_gosuslugi} "
                    f"html={per_school_html}",
                    flush=True,
                )
                print(
                    f"    EGE={school_copy.get('EGE')!r} "
                    f"-> EGE_{target_year}={school_copy.get(f'EGE_{target_year}')!r} "
                    f"(prev={school_copy.get('EGE_prev')!r})",
                    flush=True,
                )
                print(
                    f"    VUZ={school_copy.get('VUZ')!r} "
                    f"-> VUZ_{target_year}={school_copy.get(f'VUZ_{target_year}')!r}",
                    flush=True,
                )
                print(
                    f"    Olympiads_{target_year}="
                    f"{school_copy.get(f'Olympiads_{target_year}')!r}",
                    flush=True,
                )
                print(
                    f"    Medals_{target_year}={school_copy.get(f'Medals_{target_year}')!r}",
                    flush=True,
                )
            except Exception as exc:
                failed += 1
                err_text = f"{type(exc).__name__}: {exc}"
                print(
                    f"[{idx}/{len(to_process)}] FAIL id={school_id}: {err_text}",
                    flush=True,
                )
                traceback.print_exc()
                failed_school = dict(base)
                failed_school.update(empty_year_snapshot(target_year))
                failed_school["parse_error"] = err_text
                failed_school["results_parsed_at"] = datetime.now(timezone.utc).isoformat()
                result_data = upsert_school(result_data, failed_school)
                existing_by_id[school_id] = failed_school
                write_output(output_json, result_data)

                # сессия могла умереть — пересоздаём браузер и продолжаем
                try:
                    _ = driver.title
                except Exception:
                    safe_quit(driver)
                    driver = build_driver(headed=headed)
                    processed_since_recycle = 0

            if processed_since_recycle >= DRIVER_RECYCLE_EVERY:
                print("[INFO] Пересоздаю Chrome (профилактика).", flush=True)
                safe_quit(driver)
                driver = build_driver(headed=headed)
                processed_since_recycle = 0

            pause_between(args.pause, args.pause_jitter)
    finally:
        safe_quit(driver)

    print(
        f"[OK] Готово: ok={parsed_ok}, skip={skipped}, fail={failed}, "
        f"файл={output_json}, школ в файле={len(result_data)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
