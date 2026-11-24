#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Разбор показателей ЕГЭ с официальных страниц школ на Госуслугах.

Строка показателя имеет вид: "<число(ы)> - <описание>".
Примеры из выгрузки sg_main:
  "69 - Средний балл на ЕГЭ в 2026 году"
      -> общий средний балл 69 за 2026 год;
  "56,4 - Общий средний балл ЕГЭ 2026 года"
      -> общий средний балл 56.4 за 2026 год;
  "86 - Средний балл на ЕГЭ по химии в 2026 году"
      -> балл по предмету (химия 86), общего балла школа не публикует;
  "85 - Средний балл ЕГЭ информатика - 2025/2026"
      -> балл по предмету (информатика 85);
  "75/77,86 - Средний балл на ЕГЭ в 2026 году по русскому языку/по профильной математике"
      -> два предмета: русский язык 75, профильная математика 77.86;
  "82/75,15 - Средний балл на ЕГЭ в 2022 году по русскому языку/общий"
      -> русский язык 82 и общий балл 75.15;
  "91 - Самые высокие баллы: Русский язык-91"
      -> максимумы, а не средние: в рейтинг не идут.

Модуль общий для prepare_final_data.py (рейтинг) и apply_fresh_results.py (подготовка
выгрузки), чтобы правила не расходились.
"""
from __future__ import annotations

import re
from typing import Any

# Признаки максимумов: это не средний балл
NOT_AVERAGE_MARKERS = (
    "высший балл",
    "высокие баллы",
    "стобалльн",
    "максимальн",
    "наивысш",
    "лучший результат",
)

AVERAGE_MARKERS = ("средний балл", "средний результат")

# Предметы и шаблоны их упоминания. Порядок важен: длинные варианты идут раньше.
SUBJECT_PATTERNS: tuple[tuple[str, str], ...] = (
    ("Профильная математика", r"профильн\w*\s+математ\w*"),
    ("Математика", r"математ\w*"),
    ("Русский язык", r"русск\w*(?:\s+язык)?|родной\s+язык"),
    ("Английский язык", r"английск\w*"),
    ("Немецкий язык", r"немецк\w*"),
    ("Французский язык", r"французск\w*"),
    ("Испанский язык", r"испанск\w*"),
    ("Иностранный язык", r"иностранн\w*\s+язык"),
    ("Информатика", r"информатик\w*"),
    ("Физика", r"физик\w*"),
    ("Химия", r"хими\w*"),
    ("Биология", r"биолог\w*"),
    ("История", r"истори\w*"),
    ("Обществознание", r"обществознан\w*"),
    ("География", r"географ\w*"),
    ("Литература", r"литератур\w*"),
    ("ОБЗР", r"\bобзр\b"),
    ("ОБР", r"\bобр\b"),
    ("ОБЖ", r"\bобж\b"),
    ("Физическая культура", r"физкультур\w*|физическ\w*\s+культур\w*"),
    ("Технология", r"технологи\w*"),
    ("Астрономия", r"астрономи\w*"),
    ("Экономика", r"экономик\w*"),
    ("Право", r"\bправо\b"),
    ("Логика", r"логик\w*"),
    ("Психология", r"психологи\w*"),
)

# «Общий балл» — особый «предмет»: это средний балл школы по всем предметам
OVERALL_PATTERN = r"общ\w*(?:\s+средн\w*)?(?:\s+балл\w*)?"

_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")


def _to_float(text: str) -> float | None:
    try:
        return round(float(text.replace(",", ".")), 2)
    except ValueError:
        return None


def _split_values(head: str) -> list[float] | None:
    """Числа из начала строки. None, если там проценты или мусор."""
    parts = [p.strip() for p in head.split("/")]
    values: list[float] = []
    for part in parts:
        if not part:
            return None
        if "%" in part:
            return None  # процент от максимума: это не балл ЕГЭ
        nums = _NUM_RE.findall(part)
        if len(nums) != 1:
            return None
        val = _to_float(nums[0])
        if val is None:
            return None
        values.append(val)
    return values or None


def _find_subjects(desc: str) -> list[tuple[int, str]]:
    """Предметы в описании в порядке появления: [(позиция, название)]."""
    found: list[tuple[int, int, str]] = []
    for name, pattern in SUBJECT_PATTERNS:
        for m in re.finditer(pattern, desc, flags=re.IGNORECASE):
            found.append((m.start(), m.end(), name))
    found.sort(key=lambda t: (t[0], -(t[1] - t[0])))
    result: list[tuple[int, str]] = []
    used_until = -1
    for start, end, name in found:
        if start < used_until:
            continue  # уже попали внутрь более длинного совпадения
        result.append((start, name))
        used_until = end
    # «общий» считаем последним по позиции, но он может стоять в конце списка
    for m in re.finditer(OVERALL_PATTERN, desc, flags=re.IGNORECASE):
        if m.start() < used_until:
            continue
        result.append((m.start(), "Общий балл"))
        used_until = m.end()
    result.sort(key=lambda t: t[0])
    return result


def _years(text: str) -> int | None:
    years = [int(y) for y in re.findall(r"(20\d{2})", text)]
    return max(years) if years else None


def parse_ege_line(line: str) -> dict[str, Any]:
    """Разбор одной строки показателя.

    -> {"kind": "overall"|"subject"|"skip", "score": float|None,
        "year": int|None, "subject": str|None}
    """
    text = str(line or "").strip()
    out = {"kind": "skip", "score": None, "year": None, "subject": None}
    if not text:
        return out
    low = text.lower()
    if any(marker in low for marker in NOT_AVERAGE_MARKERS):
        return out
    if not any(marker in low for marker in AVERAGE_MARKERS):
        return out

    head, _, desc = text.partition(" - ")
    if not desc:
        head, _, desc = text.partition("-")
    values = _split_values(head)
    if not values:
        return out
    year = _years(desc)
    subjects = _find_subjects(desc)

    if not subjects:
        # Средний балл без указания предмета: считаем его общим.
        # Год обязателен: «Средний балл на ЕГЭ за 3 года» к конкретному году не привязан.
        if len(values) == 1 and year is not None:
            out.update(kind="overall", score=values[0], year=year)
        return out

    if len(values) != len(subjects):
        # значения и предметы не соотносятся однозначно: не угадываем
        return out

    for value, (_pos, name) in zip(values, subjects):
        if name == "Общий балл":
            if year is not None:
                out.update(kind="overall", score=value, year=year)
            return out

    _pos, name = subjects[0]
    out.update(kind="subject", score=values[0], year=year, subject=name)
    out["all_subjects"] = [
        {"subject": n, "score": v} for v, (_p, n) in zip(values, subjects)
    ]
    return out


def parse_ege_lines(lines: list[str] | None, require_ege: bool = True) -> dict[str, Any]:
    """Разбор всех строк показателей ЕГЭ школы.

    require_ege=False — не отбрасывать строки без слова «ЕГЭ» (например, ячейки
    ручного Excel-файла, где в тексте может не быть слова «ЕГЭ»).

    -> {"overall": {"score": float, "year": int} | None,
        "subjects": [{"subject": str, "score": float, "year": int}],
        "has_data": bool, "has_max": bool, "raw_lines": [str]}
    """
    overall = None
    subjects: dict[str, dict[str, Any]] = {}
    has_data = False
    has_max = False
    raw_lines: list[str] = []

    for line in lines or []:
        text = str(line or "").strip()
        if not text or (require_ege and "егэ" not in text.lower()):
            continue
        raw_lines.append(text)
        low = text.lower()
        if any(marker in low for marker in NOT_AVERAGE_MARKERS):
            has_max = True
        parsed = parse_ege_line(text)
        if parsed["kind"] == "skip":
            continue
        has_data = True
        if parsed["kind"] == "overall":
            if overall is None or (parsed["year"] or 0) >= (overall["year"] or 0):
                overall = {"score": parsed["score"], "year": parsed["year"]}
            continue
        name = parsed.get("subject")
        if not name:
            continue
        for item in parsed.get("all_subjects") or [{"subject": name, "score": parsed["score"]}]:
            subject_name = item["subject"]
            subject_score = item["score"]
            if subject_name == "Общий балл":
                continue
            year = parsed["year"]
            prev = subjects.get(subject_name)
            if prev is None or (year or 0) >= (prev.get("year") or 0):
                subjects[subject_name] = {"subject": subject_name, "score": subject_score, "year": year}

    return {
        "overall": overall,
        "subjects": sorted(subjects.values(), key=lambda s: s["subject"]),
        "has_data": has_data,
        "has_max": has_max,
        "raw_lines": raw_lines,
    }


def ege_lines_from_school(school: dict[str, Any]) -> list[str]:
    """Строки показателей ЕГЭ из записи выгрузки sg_main."""
    lines = school.get("EGE_LINES")
    if isinstance(lines, list) and lines:
        return [str(x) for x in lines]
    raw = school.get("results_kpi_raw")
    if isinstance(raw, list) and raw:
        picked = [str(x) for x in raw if "егэ" in str(x).lower()]
        if picked:
            return picked
    single = school.get("EGE") or school.get("EGE_2026")
    return [str(single)] if single else []
