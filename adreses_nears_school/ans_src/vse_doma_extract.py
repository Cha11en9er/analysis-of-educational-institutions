#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер номеров домов с https://saratov.ginfo.ru/ulicy/

Логика: каталог всех улиц → a.ulica_link по ключевому слову → страница улицы → dom_link.

Запуск из корня (Chrome всегда видимый):
    .\\venv\\Scripts\\python.exe .\\adreses_nears_school\\ans_src\\vse_doma_extract.py --update-csv
    .\\venv\\Scripts\\python.exe .\\adreses_nears_school\\ans_src\\vse_doma_extract.py "Волжский;...;все дома"
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple
from urllib.parse import urljoin

from playwright.sync_api import Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

ULICY_URL = "https://saratov.ginfo.ru/ulicy/"
LAST_STREET_HREF = "/ulicy/ulica_53-y_strelkovoy_divizii/"
DEFAULT_TIMEOUT_MS = 40_000
DEFAULT_SLOW_MO_MS = 800
DEFAULT_STEP_DELAY_SEC = 1.0
DEFAULT_DOM_DUMP_DIR = "adreses_nears_school/ans_data/dom_dumps"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

TEST_LINE = "Волжский;МОУ «Гимназия № 7»;1-й проезд Муленкова;все дома"

CHROME_ARGS = (
    "--start-maximized",
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--no-first-run",
    "--no-default-browser-check",
)

STREET_TYPES = (
    "проезд", "проезды", "проездов",
    "переулок", "переулки", "переулков",
    "улица", "улицы",
    "проспект", "тупик", "тупики", "тупиков",
    "шоссе", "бульвар", "аллея", "набережная", "площадь",
)
PASSAGE_MARKERS = ("проезд", "проезды", "пр-д", "переулок", "переулки", "пер.")
DEAD_END_MARKERS = ("тупик", "тупики", "туп.")
SIZE_PREFIXES = ("большая", "малая", "верхняя", "нижняя", "новая", "старая", "узкая", "широкая")


@dataclass
class UlicaLink:
    href: str
    label: str
    url: str


def log_step(msg: str, *, verbose: bool = True) -> None:
    if verbose:
        print(f"  → {msg}", flush=True)


def parse_csv_line(line: str) -> dict[str, str]:
    parts = [p.strip() for p in line.strip().split(";")]
    if len(parts) < 4:
        raise ValueError(f"Ожидается минимум 4 поля через «;», получено: {line!r}")
    return {"district": parts[0], "school": parts[1], "street": parts[2], "houses": parts[3]}


def extract_ordinal(street: str) -> Optional[str]:
    m = re.match(r"^\s*(\d+)\s*-\s*й\b", street, re.I)
    return m.group(1) if m else None


def want_link_kind(street: str) -> str:
    """Ожидаемый тип на сайте: street | passage | dead_end | lane."""
    low = street.lower()
    if any(m in low for m in DEAD_END_MARKERS):
        return "dead_end"
    if any(m in low for m in ("переулок", "переулки", "пер.")):
        return "lane"
    if any(m in low for m in PASSAGE_MARKERS):
        return "passage"
    return "street"


def link_kind_from_label(label: str) -> str:
    low = label.lower().strip()
    if low.startswith("пр-д") or low.startswith("пр-д ") or "проезд" in low:
        return "passage"
    if low.startswith("туп.") or low.startswith("туп. ") or "тупик" in low:
        return "dead_end"
    if low.startswith("пер.") or "переул" in low:
        return "lane"
    if low.startswith("ул.") or low.startswith("ул. ") or "улица" in low:
        return "street"
    return "other"


def is_passage_address(street: str) -> bool:
    return want_link_kind(street) == "passage"


def normalize_text(text: str) -> str:
    t = text.lower().replace("ё", "е")
    t = re.sub(r"[^\w\s.-]", " ", t, flags=re.UNICODE)
    return " ".join(t.split())


def _normalize_base_name(rest: str) -> str:
    base = rest
    for w in STREET_TYPES:
        base = re.sub(rf"\b{re.escape(w)}\b", " ", base, flags=re.I)
    base = re.sub(r"\s+", " ", base).strip(" .,")
    base = re.sub(r"(ов)ые$", r"\1ый", base, flags=re.I)
    base = re.sub(r"ные$", "ный", base, flags=re.I)
    return base.strip()


def _kind_word(kind: str) -> str:
    return {"passage": "проезд", "dead_end": "тупик", "lane": "переулок", "street": "улица"}.get(
        kind, "улица"
    )


def expand_street_variants(street: str) -> List[str]:
    """
    Одна строка CSV → одна или несколько улиц для поиска на сайте.

    «1,2,3-й Совхозные проезды» → три варианта с разными номерами.
    «1-8 Рубиновые проезды» → восемь вариантов.
    """
    s = street.strip()

    m = re.match(r"^([\d]+(?:\s*,\s*[\d]+)+)\s*-?\s*й\s+(.+)$", s, re.I)
    if m:
        ordinals = re.findall(r"\d+", m.group(1))
        base = _normalize_base_name(m.group(2))
        kind = want_link_kind(m.group(2))
        kw = _kind_word(kind)
        return [f"{o}-й {base} {kw}".strip() for o in ordinals]

    m = re.match(r"^(\d+)\s*-\s*(\d+)\s+(.+)$", s, re.I)
    if m:
        start, end = int(m.group(1)), int(m.group(2))
        base = _normalize_base_name(m.group(3))
        kind = want_link_kind(m.group(3))
        kw = _kind_word(kind)
        return [f"{o}-й {base} {kw}".strip() for o in range(start, end + 1)]

    return [s]


def extract_match_words(street: str) -> List[str]:
    """Слова, которые должны встретиться в label/href (не полное имя CSV)."""
    s = street.strip()
    s = re.sub(r"^\d+\s*-\s*й\s+", "", s, flags=re.I)
    s = re.sub(r"^им\.?\s*", "", s, flags=re.I)
    s = re.sub(r"\bимени\b", " ", s, flags=re.I)
    for p in SIZE_PREFIXES:
        s = re.sub(rf"^{re.escape(p)}\s+", "", s, flags=re.I)
    for w in STREET_TYPES:
        s = re.sub(rf"\b{re.escape(w)}\b", " ", s, flags=re.I)
    s = re.sub(r"\b[А-ЯA-Z]\.\s*[А-ЯA-Z]\.?\b", " ", s)
    s = re.sub(r"\b[А-ЯA-Z]\.\s*[А-ЯA-Z]\.\s*[А-ЯA-Z]\.?\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" .,")
    words = [w for w in s.split() if len(w) >= 3]
    return words or [street.strip()]


def extract_search_token(street: str) -> str:
    """
    Часть имени для поиска (не полный текст CSV).

    «Защитников Отечества» → «Отечества» (все match_words проверяются отдельно)
    «Большая Долинная» → «Долинная»
    «Сетевой проезд» → «Сетевой»
    """
    words = extract_match_words(street)
    return words[-1]


def link_kind_score(label: str, street: str) -> int:
    want = want_link_kind(street)
    got = link_kind_from_label(label)
    if want == got:
        return 25
    if want == "street" and got == "other":
        return 5
    if want == "passage" and got == "street":
        return 0
    if want == "street" and got == "passage":
        return 0
    return 8 if got == "other" else 0


def link_ordinal_match(link: UlicaLink, ordinal: Optional[str]) -> bool:
    if not ordinal:
        return True
    low = normalize_text(f"{link.label} {link.href}").replace(" ", "")
    patterns = (
        f"{ordinal}-й",
        f"{ordinal}й",
        f"{ordinal}-y",
        f"_{ordinal}_",
        f"-{ordinal}-",
        f"{ordinal}-y_",
    )
    return any(p in low for p in patterns)


def score_ulica_link(link: UlicaLink, street: str) -> int:
    blob = normalize_text(f"{link.label} {link.href}")
    match_words = extract_match_words(street)
    if not all(normalize_text(w) in blob for w in match_words):
        return 0

    score = 50
    score += link_kind_score(link.label, street)
    if link_ordinal_match(link, extract_ordinal(street)):
        score += 30
    elif extract_ordinal(street):
        score -= 40
    return score


def apply_stealth(page: Page, context: BrowserContext) -> None:
    Stealth().apply_stealth_sync(page)
    context.on("page", lambda p: Stealth().apply_stealth_sync(p))


def wait_if_captcha(page: Page) -> None:
    loc = page.locator('iframe[src*="captcha"], iframe[src*="smartcaptcha"], .CheckboxCaptcha')
    try:
        if loc.count() and loc.first.is_visible(timeout=500):
            print("\n>>> КАПЧА — решите в Chrome, Enter…", flush=True)
            input()
    except PlaywrightTimeoutError:
        pass


def resolve_dump_dir(dump_dir: str) -> str:
    path = dump_dir if os.path.isabs(dump_dir) else os.path.join(os.getcwd(), dump_dir)
    os.makedirs(path, exist_ok=True)
    return path


def dump_page_dom(page: Page, filename: str, *, dump_dir: str, verbose: bool) -> str:
    """Сохраняет полный HTML страницы после загрузки."""
    out_dir = resolve_dump_dir(dump_dir)
    path = os.path.join(out_dir, filename)
    html = page.content()
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    if verbose:
        print(f"  → DOM сохранён: {path} ({len(html):,} символов)", flush=True)
    return path


def slug_for_dump(name: str) -> str:
    s = normalize_text(name).replace(" ", "_")
    s = re.sub(r"[^\w.-]", "", s, flags=re.UNICODE)
    return s[:80] or "page"


def create_browser(pw, *, slow_mo_ms: int) -> Tuple[Browser, BrowserContext, Page]:
    Stealth().hook_playwright_context(pw)
    browser = pw.chromium.launch(
        headless=False,
        channel="chrome",
        slow_mo=slow_mo_ms,
        ignore_default_args=["--enable-automation", "--no-sandbox"],
        args=list(CHROME_ARGS),
    )
    context = browser.new_context(
        locale="ru-RU",
        timezone_id="Europe/Saratov",
        viewport={"width": 1920, "height": 1080},
        user_agent=USER_AGENT,
    )
    page = context.new_page()
    apply_stealth(page, context)
    return browser, context, page


def scroll_until_catalog_loaded(page: Page, *, timeout_ms: int, verbose: bool) -> None:
    """Догружает список улиц: конец — появление последней улицы в каталоге."""
    log_step(f"Прокрутка каталога до {LAST_STREET_HREF}", verbose=verbose)
    page.wait_for_selector("a.ulica_link", state="attached", timeout=timeout_ms)
    deadline = time.time() + timeout_ms / 1000
    last_count = 0
    stall_rounds = 0

    while time.time() < deadline:
        if page.locator(f'a.ulica_link[href="{LAST_STREET_HREF}"]').count() > 0:
            log_step("Каталог полностью загружен", verbose=verbose)
            return

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(0.35)

        count = page.locator("a.ulica_link").count()
        if count == last_count:
            stall_rounds += 1
            if stall_rounds >= 8:
                break
        else:
            stall_rounds = 0
            last_count = count

    if page.locator(f'a.ulica_link[href="{LAST_STREET_HREF}"]').count() == 0:
        raise PlaywrightTimeoutError(
            f"Каталог не догрузился: нет ссылки {LAST_STREET_HREF}"
        )


def cache_all_ulica_links(page: Page) -> List[UlicaLink]:
    links: List[UlicaLink] = []
    all_links = page.locator("a.ulica_link")
    for i in range(all_links.count()):
        el = all_links.nth(i)
        href = el.get_attribute("href")
        if not href:
            continue
        label = el.inner_text().strip()
        links.append(UlicaLink(href=href, label=label, url=urljoin(ULICY_URL, href)))
    return links


def _collect_ulica_candidates_from_cache(
    catalog: List[UlicaLink], street: str
) -> List[Tuple[int, int, UlicaLink]]:
    candidates: List[Tuple[int, int, UlicaLink]] = []
    for i, link in enumerate(catalog):
        sc = score_ulica_link(link, street)
        if sc > 0:
            candidates.append((sc, i, link))
    return candidates


def _collect_ulica_candidates(page: Page, street: str) -> List[Tuple[int, int, UlicaLink]]:
    catalog = cache_all_ulica_links(page)
    return _collect_ulica_candidates_from_cache(catalog, street)


def _pick_best_candidate(candidates: List[Tuple[int, int, UlicaLink]], street: str) -> UlicaLink:
    if not candidates:
        token = extract_search_token(street)
        words = ", ".join(extract_match_words(street))
        raise PlaywrightTimeoutError(
            f"На /ulicy/ нет совпадений для «{street}» (ищем: {words}, якорь: {token})"
        )

    best = max(c[0] for c in candidates)
    top = [c for c in candidates if c[0] >= best - 5]
    want = want_link_kind(street)

    kind_filtered = [c for c in top if link_kind_from_label(c[2].label) == want]
    if kind_filtered:
        top = kind_filtered
    elif want == "passage":
        passage_only = [
            c for c in top if link_kind_from_label(c[2].label) == "passage"
        ]
        if passage_only:
            top = passage_only

    ordinal = extract_ordinal(street)
    if ordinal:
        ord_matches = [c for c in top if link_ordinal_match(c[2], ordinal)]
        if not ord_matches:
            raise PlaywrightTimeoutError(
                f"Для «{street}» нет проезда/улицы с номером {ordinal}-й в каталоге"
            )
        top = ord_matches

    top.sort(key=lambda x: x[1])
    return top[0][2]


def resolve_ulica_link(page: Page, street: str, catalog: Optional[List[UlicaLink]] = None) -> UlicaLink:
    """На уже загруженном /ulicy/ выбирает первую подходящую a.ulica_link."""
    if catalog is None:
        candidates = _collect_ulica_candidates(page, street)
    else:
        candidates = _collect_ulica_candidates_from_cache(catalog, street)
    return _pick_best_candidate(candidates, street)


def resolve_ulica_links_for_csv_row(
    page: Page, csv_street: str, catalog: Optional[List[UlicaLink]] = None
) -> List[Tuple[str, UlicaLink]]:
    """Все варианты для строки CSV (например 3 проезда из «1,2,3-й …»)."""
    variants = expand_street_variants(csv_street)
    out: List[Tuple[str, UlicaLink]] = []
    for variant in variants:
        link = resolve_ulica_link(page, variant, catalog=catalog)
        out.append((variant, link))
    return out


def pick_and_click_ulica_link(
    page: Page,
    street: str,
    *,
    timeout_ms: int,
    verbose: bool,
    pause: float,
) -> str:
    """На /ulicy/ ищет token, подсвечивает, кликает первую подходящую a.ulica_link."""
    token = extract_search_token(street)
    words = ", ".join(extract_match_words(street))
    log_step(f"Поиск: слова [{words}], якорь «{token}» (CSV: «{street}»)", verbose=verbose)

    chosen = resolve_ulica_link(page, street)
    log_step(f"Выбрано: «{chosen.label}» → {chosen.url}", verbose=verbose)

    target = page.locator(f'a.ulica_link[href="{chosen.href}"]').first
    target.scroll_into_view_if_needed()
    if pause:
        time.sleep(pause)

    target.evaluate(
        "el => { el.style.outline = '3px solid #e00'; el.style.backgroundColor = '#ffeb3b'; }"
    )
    if pause:
        time.sleep(pause)

    log_step("Кликаю ссылку…", verbose=verbose)
    target.click()
    page.wait_for_load_state("domcontentloaded")
    if pause:
        time.sleep(pause)

    return chosen.label


def collect_house_numbers(page: Page, *, timeout_ms: int, verbose: bool, pause: float) -> List[str]:
    log_step("Собираю номера домов…", verbose=verbose)
    page.bring_to_front()
    page.wait_for_selector(".more_hide a.dom_link", state="attached", timeout=timeout_ms)
    if pause:
        time.sleep(pause)

    numbers: List[str] = []
    for el in page.locator(".more_hide a.dom_link").all():
        t = el.inner_text().strip()
        if t:
            numbers.append(t)
    return numbers


def fetch_house_numbers(
    page: Page,
    street: str,
    *,
    timeout_ms: int,
    step_delay_sec: float,
    verbose: bool,
    dump_dir: str,
    dump_dom: bool,
) -> List[str]:
    wait_if_captcha(page)
    log_step(f"Открываю каталог {ULICY_URL}", verbose=verbose)
    page.goto(ULICY_URL, wait_until="domcontentloaded")
    page.bring_to_front()
    if step_delay_sec:
        time.sleep(step_delay_sec)

    scroll_until_catalog_loaded(page, timeout_ms=timeout_ms, verbose=verbose)
    if step_delay_sec:
        time.sleep(step_delay_sec)

    if dump_dom:
        dump_page_dom(page, "ulicy_catalog_loaded.html", dump_dir=dump_dir, verbose=verbose)

    pick_and_click_ulica_link(
        page, street, timeout_ms=timeout_ms, verbose=verbose, pause=step_delay_sec
    )
    if dump_dom:
        dump_page_dom(
            page,
            f"ulica_{slug_for_dump(street)}.html",
            dump_dir=dump_dir,
            verbose=verbose,
        )
    nums = collect_house_numbers(page, timeout_ms=timeout_ms, verbose=verbose, pause=step_delay_sec)
    log_step(f"Номеров: {len(nums)}", verbose=verbose)
    return nums


def fetch_house_numbers_from_line(
    line: str,
    *,
    slow_mo_ms: int = DEFAULT_SLOW_MO_MS,
    step_delay_sec: float = DEFAULT_STEP_DELAY_SEC,
    wait_enter: bool = True,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    verbose: bool = True,
    dump_dir: str = DEFAULT_DOM_DUMP_DIR,
    dump_dom: bool = True,
) -> List[str]:
    parsed = parse_csv_line(line)

    with sync_playwright() as pw:
        print("\n" + "=" * 55, flush=True)
        print("  ОТКРЫВАЮ GOOGLE CHROME (всегда видимый режим)", flush=True)
        print("=" * 55 + "\n", flush=True)

        browser, context, page = create_browser(pw, slow_mo_ms=slow_mo_ms)
        page.set_default_timeout(timeout_ms)
        try:
            numbers = fetch_house_numbers(
                page,
                parsed["street"],
                timeout_ms=timeout_ms,
                step_delay_sec=step_delay_sec,
                verbose=verbose,
                dump_dir=dump_dir,
                dump_dom=dump_dom,
            )
            print(
                f"\nНомера ({len(numbers)}): {', '.join(numbers) or '(пусто)'}",
                flush=True,
            )
            print("Строка:", expand_line(line, numbers), flush=True)
            if wait_enter:
                print("\n>>> Enter — закрыть Chrome", flush=True)
                try:
                    input()
                except EOFError:
                    pass
            return numbers
        finally:
            context.close()
            browser.close()


def expand_line(line: str, numbers: List[str]) -> str:
    p = parse_csv_line(line)
    return format_csv_row(p["district"], p["school"], p["street"], ", ".join(numbers))


def format_csv_row(district: str, school: str, street: str, houses: str) -> str:
    return f"{district};{school};{street};{houses}"


def is_vse_doma(houses: str) -> bool:
    return houses.strip().lower() == "все дома"


MAX_HOUSE_RANGE_SPAN = 500


def expand_house_ranges(houses: str) -> str:
    """
    Простые диапазоны «2-32» → «2, 3, …, 32» для геокодера.
    Сложные записи (слэши, дроби) не трогаем.
    """
    if is_vse_doma(houses):
        return houses

    parts_out: List[str] = []
    for chunk in houses.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        compact = re.sub(r"\s+", "", chunk)
        m = re.fullmatch(r"(\d+)-(\d+)", compact)
        if m:
            start, end = int(m.group(1)), int(m.group(2))
            if start <= end and (end - start) <= MAX_HOUSE_RANGE_SPAN:
                parts_out.extend(str(n) for n in range(start, end + 1))
                continue
        parts_out.append(chunk)
    return ", ".join(parts_out)


def fetch_houses_at_url(
    page: Page,
    url: str,
    *,
    timeout_ms: int,
    pause: float = 0,
) -> List[str]:
    page.goto(url, wait_until="domcontentloaded")
    if pause:
        time.sleep(pause)
    return collect_house_numbers(page, timeout_ms=timeout_ms, verbose=False, pause=0)


def scrape_vse_doma_entries(
    page: Page,
    csv_street: str,
    catalog: List[UlicaLink],
    *,
    timeout_ms: int,
    pause: float,
    verbose: bool,
) -> List[Tuple[str, str]]:
    """Успешные варианты: (название улицы для CSV, номера через запятую)."""
    entries: List[Tuple[str, str]] = []
    variants = expand_street_variants(csv_street)

    for variant in variants:
        try:
            link = resolve_ulica_link(page, variant, catalog=catalog)
            nums = fetch_houses_at_url(page, link.url, timeout_ms=timeout_ms, pause=pause)
            if not nums:
                if verbose:
                    print(f"    ! {variant}: домов нет на странице", flush=True)
                continue
            entries.append((variant, ", ".join(nums)))
            if verbose:
                print(f"    ✓ {variant}: {len(nums)} домов → {', '.join(nums)}", flush=True)
        except PlaywrightTimeoutError as e:
            if verbose:
                print(f"    ! {variant}: {e}", flush=True)
    return entries


def read_csv_data(path: str) -> Tuple[str, List[str]]:
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    if not lines:
        return "", []
    return lines[0].rstrip("\n"), [ln.rstrip("\n") for ln in lines[1:] if ln.strip() or ln == "\n"]


def build_updated_rows(
    data_rows: List[str],
    scrape_updates: dict[int, List[Tuple[str, str]]],
) -> List[str]:
    out: List[str] = []
    for i, row in enumerate(data_rows):
        if not row.strip():
            continue
        p = parse_csv_line(row)
        if is_vse_doma(p["houses"]):
            if i in scrape_updates and scrape_updates[i]:
                for street, houses in scrape_updates[i]:
                    out.append(format_csv_row(p["district"], p["school"], street, houses))
            else:
                out.append(row)
        else:
            new_houses = expand_house_ranges(p["houses"])
            out.append(format_csv_row(p["district"], p["school"], p["street"], new_houses))
    return out


def update_csv_from_ginfo(
    csv_path: str,
    *,
    limit_vse_doma: Optional[int] = None,
    slow_mo_ms: int = 0,
    step_delay_sec: float = 0.25,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    verbose: bool = True,
    wait_enter: bool = False,
    backup: bool = True,
) -> dict[str, int]:
    if not os.path.isabs(csv_path):
        csv_path = os.path.join(os.getcwd(), csv_path)

    header, data_rows = read_csv_data(csv_path)
    vse_indices = [
        i for i, row in enumerate(data_rows) if is_vse_doma(parse_csv_line(row)["houses"])
    ]
    if limit_vse_doma is not None:
        vse_indices = vse_indices[:limit_vse_doma]

    stats = {"vse_doma_total": len(vse_indices), "updated": 0, "expanded_ranges": 0, "unchanged_vse": 0}
    scrape_updates: dict[int, List[Tuple[str, str]]] = {}

    for row in data_rows:
        p = parse_csv_line(row)
        if not is_vse_doma(p["houses"]) and expand_house_ranges(p["houses"]) != p["houses"]:
            stats["expanded_ranges"] += 1

    if verbose:
        print(f"CSV: {csv_path}", flush=True)
        print(f"Строк «все дома» к обходу: {len(vse_indices)}", flush=True)
        print(f"Строк с разворотом диапазонов: {stats['expanded_ranges']}", flush=True)

    if vse_indices:
        with sync_playwright() as pw:
            if verbose:
                print("\n" + "=" * 55, flush=True)
                print("  Chrome — загрузка номеров домов с ginfo.ru", flush=True)
                print("=" * 55 + "\n", flush=True)

            browser, context, page = create_browser(pw, slow_mo_ms=slow_mo_ms)
            page.set_default_timeout(timeout_ms)
            try:
                wait_if_captcha(page)
                page.goto(ULICY_URL, wait_until="domcontentloaded")
                scroll_until_catalog_loaded(page, timeout_ms=timeout_ms, verbose=verbose)
                catalog = cache_all_ulica_links(page)
                log_step(f"Каталог: {len(catalog)} улиц", verbose=verbose)

                for n, idx in enumerate(vse_indices, start=1):
                    p = parse_csv_line(data_rows[idx])
                    if verbose:
                        print(f"\n[{n}/{len(vse_indices)}] {p['street']}", flush=True)
                    entries = scrape_vse_doma_entries(
                        page,
                        p["street"],
                        catalog,
                        timeout_ms=timeout_ms,
                        pause=step_delay_sec,
                        verbose=verbose,
                    )
                    if entries:
                        scrape_updates[idx] = entries
                        stats["updated"] += 1
                    else:
                        stats["unchanged_vse"] += 1

                if wait_enter:
                    print("\n>>> Enter — закрыть Chrome", flush=True)
                    try:
                        input()
                    except EOFError:
                        pass
            finally:
                context.close()
                browser.close()

    new_rows = build_updated_rows(data_rows, scrape_updates)
    if backup:
        backup_path = csv_path + ".bak"
        with open(csv_path, encoding="utf-8") as src, open(backup_path, "w", encoding="utf-8") as dst:
            dst.write(src.read())
        if verbose:
            print(f"\nРезервная копия: {backup_path}", flush=True)

    with open(csv_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(header + "\n")
        f.write("\n".join(new_rows))
        if new_rows:
            f.write("\n")

    if verbose:
        print(
            f"\nГотово: обновлено «все дома» — {stats['updated']}, "
            f"без изменений — {stats['unchanged_vse']}, "
            f"развёрнуто диапазонов — {stats['expanded_ranges']}",
            flush=True,
        )
    return stats


def load_vse_doma_lines(csv_path: str, limit: int) -> List[str]:
    lines: List[str] = []
    with open(csv_path, encoding="utf-8") as f:
        next(f, None)  # header
        for raw in f:
            row = raw.strip()
            if not row:
                continue
            parts = row.split(";")
            if len(parts) >= 4 and parts[3].strip().lower() == "все дома":
                lines.append(row)
                if len(lines) >= limit:
                    break
    return lines


def dump_batch_vse_doma(
    csv_path: str,
    limit: int,
    *,
    slow_mo_ms: int = DEFAULT_SLOW_MO_MS,
    step_delay_sec: float = DEFAULT_STEP_DELAY_SEC,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    verbose: bool = True,
    dump_dir: str = DEFAULT_DOM_DUMP_DIR,
    wait_enter: bool = True,
) -> None:
    """Первые N строк «все дома»: каталог + DOM каждой найденной улицы/проезда."""
    rows = load_vse_doma_lines(csv_path, limit)
    summary_lines: List[str] = []

    with sync_playwright() as pw:
        print("\n" + "=" * 55, flush=True)
        print("  ОТКРЫВАЮ GOOGLE CHROME — пакетная выгрузка DOM", flush=True)
        print("=" * 55 + "\n", flush=True)

        browser, context, page = create_browser(pw, slow_mo_ms=slow_mo_ms)
        page.set_default_timeout(timeout_ms)
        try:
            wait_if_captcha(page)
            page.goto(ULICY_URL, wait_until="domcontentloaded")
            if step_delay_sec:
                time.sleep(step_delay_sec)
            scroll_until_catalog_loaded(page, timeout_ms=timeout_ms, verbose=verbose)
            dump_page_dom(page, "ulicy_catalog_loaded.html", dump_dir=dump_dir, verbose=verbose)
            catalog = cache_all_ulica_links(page)
            log_step(f"В каталоге ссылок: {len(catalog)}", verbose=verbose)

            for row_idx, row in enumerate(rows, start=1):
                p = parse_csv_line(row)
                csv_street = p["street"]
                variants = expand_street_variants(csv_street)
                if verbose:
                    print(f"\n[{row_idx}/{len(rows)}] CSV: {csv_street}", flush=True)
                    if len(variants) > 1:
                        print(f"  Варианты поиска: {variants}", flush=True)

                matches: List[Tuple[str, UlicaLink]] = []
                for variant in variants:
                    try:
                        link = resolve_ulica_link(page, variant, catalog=catalog)
                        matches.append((variant, link))
                    except PlaywrightTimeoutError as e:
                        summary_lines.append(f"{row_idx}. ОШИБКА {variant}: {e}")
                        if verbose:
                            print(f"  ! {variant}: {e}", flush=True)

                for v_idx, (variant, link) in enumerate(matches, start=1):
                    href_slug = link.href.strip("/").replace("/ulicy/", "").replace("/", "_")
                    fname = f"{row_idx:02d}_{v_idx:02d}_{href_slug}.html"
                    if verbose:
                        print(f"  {variant}\n    → {link.url}\n    ({link.label})", flush=True)
                    page.goto(link.url, wait_until="domcontentloaded")
                    if step_delay_sec:
                        time.sleep(step_delay_sec)
                    dump_page_dom(page, fname, dump_dir=dump_dir, verbose=verbose)
                    summary_lines.append(
                        f"{row_idx}.{v_idx} {csv_street} | вариант: {variant} | {link.url} | {link.label}"
                    )

            summary_path = os.path.join(resolve_dump_dir(dump_dir), "batch_summary.txt")
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write("\n".join(summary_lines))
            if verbose:
                print(f"\nСводка: {summary_path}", flush=True)

            if wait_enter:
                print("\n>>> Enter — закрыть Chrome", flush=True)
                try:
                    input()
                except EOFError:
                    pass
        finally:
            context.close()
            browser.close()


def resolve_street_urls(
    streets: List[str],
    *,
    slow_mo_ms: int = DEFAULT_SLOW_MO_MS,
    step_delay_sec: float = DEFAULT_STEP_DELAY_SEC,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    verbose: bool = True,
    dump_dir: str = DEFAULT_DOM_DUMP_DIR,
    dump_dom: bool = True,
    wait_enter: bool = True,
) -> List[Tuple[str, UlicaLink]]:
    results: List[Tuple[str, UlicaLink]] = []
    with sync_playwright() as pw:
        print("\n" + "=" * 55, flush=True)
        print("  ОТКРЫВАЮ GOOGLE CHROME (всегда видимый режим)", flush=True)
        print("=" * 55 + "\n", flush=True)

        browser, context, page = create_browser(pw, slow_mo_ms=slow_mo_ms)
        page.set_default_timeout(timeout_ms)
        try:
            wait_if_captcha(page)
            page.goto(ULICY_URL, wait_until="domcontentloaded")
            if step_delay_sec:
                time.sleep(step_delay_sec)
            scroll_until_catalog_loaded(page, timeout_ms=timeout_ms, verbose=verbose)
            catalog: Optional[List[UlicaLink]] = None
            if dump_dom:
                dump_page_dom(page, "ulicy_catalog_loaded.html", dump_dir=dump_dir, verbose=verbose)
            catalog = cache_all_ulica_links(page)
            for street in streets:
                p = parse_csv_line(street) if ";" in street else {"street": street}
                name = p["street"]
                for variant, link in resolve_ulica_links_for_csv_row(page, name, catalog=catalog):
                    results.append((variant, link))
                    if verbose:
                        print(f"CSV: {name}\n  вариант: {variant}\n  → {link.url}\n  ({link.label})\n")
            if wait_enter:
                print("\n>>> Enter — закрыть Chrome", flush=True)
                try:
                    input()
                except EOFError:
                    pass
        finally:
            context.close()
            browser.close()
    return results


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser(description="Номера домов с ginfo.ru/ulicy/")
    ap.add_argument("line", nargs="?", default=TEST_LINE)
    ap.add_argument(
        "--csv",
        default="adreses_nears_school/ans_data/ans_stage1_adres_near_school_2.csv",
        help="CSV с адресами (для --links-only)",
    )
    ap.add_argument(
        "--update-csv",
        action="store_true",
        help="Заполнить «все дома» с ginfo.ru и развернуть диапазоны в CSV",
    )
    ap.add_argument(
        "--limit-vse-doma",
        type=int,
        default=None,
        help="Обработать только первые N строк «все дома» (остальной CSV всё равно с диапазонами)",
    )
    ap.add_argument("--no-backup", action="store_true", help="Не создавать .bak перед записью")
    ap.add_argument("--links-only", action="store_true", help="Только ссылки на улицы, без домов")
    ap.add_argument(
        "--dump-batch",
        action="store_true",
        help="DOM каталога + DOM страниц для первых N строк «все дома»",
    )
    ap.add_argument("--limit", type=int, default=10, help="Сколько первых «все дома» из CSV")
    ap.add_argument("--slow-mo", type=int, default=DEFAULT_SLOW_MO_MS)
    ap.add_argument("--step-delay", type=float, default=DEFAULT_STEP_DELAY_SEC)
    ap.add_argument("--dump-dir", default=DEFAULT_DOM_DUMP_DIR, help="Папка для HTML-дампов")
    ap.add_argument("--no-dump-dom", action="store_true", help="Не сохранять DOM на диск")
    ap.add_argument("--no-wait-enter", action="store_true")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_MS // 1000)
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args()

    if args.update_csv:
        csv_path = args.csv
        if not os.path.isabs(csv_path):
            csv_path = os.path.join(os.getcwd(), csv_path)
        try:
            update_csv_from_ginfo(
                csv_path,
                limit_vse_doma=args.limit_vse_doma,
                slow_mo_ms=args.slow_mo,
                step_delay_sec=args.step_delay,
                timeout_ms=args.timeout * 1000,
                verbose=not args.quiet,
                wait_enter=not args.no_wait_enter,
                backup=not args.no_backup,
            )
        except PlaywrightTimeoutError as e:
            print(f"\nОшибка: {e}")
            raise SystemExit(1) from e
        return

    if args.dump_batch:
        csv_path = args.csv
        if not os.path.isabs(csv_path):
            csv_path = os.path.join(os.getcwd(), csv_path)
        print(f"Пакетная выгрузка DOM: первые {args.limit} «все дома» → {args.dump_dir}\n")
        try:
            dump_batch_vse_doma(
                csv_path,
                args.limit,
                slow_mo_ms=args.slow_mo,
                step_delay_sec=args.step_delay,
                timeout_ms=args.timeout * 1000,
                verbose=not args.quiet,
                dump_dir=args.dump_dir,
                wait_enter=not args.no_wait_enter,
            )
        except PlaywrightTimeoutError as e:
            print(f"\nОшибка: {e}")
            raise SystemExit(1) from e
        return

    if args.links_only:
        csv_path = args.csv
        if not os.path.isabs(csv_path):
            csv_path = os.path.join(os.getcwd(), csv_path)
        rows = load_vse_doma_lines(csv_path, args.limit)
        print(f"Первые {len(rows)} улиц с «все дома» из {args.csv}\n")
        try:
            resolve_street_urls(
                rows,
                slow_mo_ms=args.slow_mo,
                step_delay_sec=args.step_delay,
                timeout_ms=args.timeout * 1000,
                verbose=not args.quiet,
                dump_dir=args.dump_dir,
                dump_dom=not args.no_dump_dom,
                wait_enter=not args.no_wait_enter,
            )
        except PlaywrightTimeoutError as e:
            print(f"\nОшибка: {e}")
            raise SystemExit(1) from e
        return

    p = parse_csv_line(args.line)
    token = extract_search_token(p["street"])
    print(f"Улица CSV: {p['street']}")
    print(f"Поиск на /ulicy/: «{token}»")
    if not args.no_dump_dom:
        print(f"DOM после загрузки: {args.dump_dir}\n")

    try:
        fetch_house_numbers_from_line(
            args.line,
            slow_mo_ms=args.slow_mo,
            step_delay_sec=args.step_delay,
            wait_enter=not args.no_wait_enter,
            timeout_ms=args.timeout * 1000,
            verbose=not args.quiet,
            dump_dir=args.dump_dir,
            dump_dom=not args.no_dump_dom,
        )
    except PlaywrightTimeoutError as e:
        print(f"\nОшибка: {e}")
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
