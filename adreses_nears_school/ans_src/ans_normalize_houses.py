#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Финальная нормализация номеров домов в ans_stage1_adres_near_school_2.csv.

Не трогает поля, где есть «все дома». Разворачивает диапазоны, «с 1-19а»,
«частный сектор 1-37», чётные/нечётные, чинит дубли улица+дома в одной колонке.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
from typing import List, Optional, Tuple

# Диапазоны шире — не разворачиваем, оставляем как в источнике (11-607, 1-807).
MAX_RANGE_SPAN = 500

# Только точное «все дома» не трогаем; с «частный сектор все дома» — тоже не трогаем
VSE_DOMA_MARKERS = ("все дома",)

SIDE_NOTE_ONLY = re.compile(
    r"^(четн|нечетн)[а-яё\s\-]*сторон[аы]?$",
    re.I,
)


def contains_vse_doma(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in VSE_DOMA_MARKERS)


def should_skip_normalization(houses: str) -> bool:
    if not houses or not houses.strip():
        return True
    if contains_vse_doma(houses):
        return True
    if SIDE_NOTE_ONLY.fullmatch(houses.strip()):
        return True
    return False


def parse_num_suffix(token: str) -> Tuple[int, str]:
    t = token.strip().replace(" ", "")
    m = re.fullmatch(r"(\d+)([а-яa-z]?)", t, re.I)
    if not m:
        raise ValueError(token)
    return int(m.group(1)), m.group(2) or ""


def expand_pure_range(start: int, end: int) -> Optional[List[str]]:
    if start > end or (end - start) > MAX_RANGE_SPAN:
        return None
    return [str(n) for n in range(start, end + 1)]


def expand_range_with_end_suffix(start_s: str, end_s: str) -> Optional[List[str]]:
    """«1-19а» → 1, 2, …, 18, 19а. Слишком широкий диапазон → None (оставить как есть)."""
    start_n, start_suf = parse_num_suffix(start_s)
    end_n, end_suf = parse_num_suffix(end_s)
    if start_suf or not end_suf:
        return expand_pure_range(start_n, end_n)
    if end_n > start_n:
        if (end_n - start_n) > MAX_RANGE_SPAN:
            return None
        out = [str(n) for n in range(start_n, end_n)]
        out.append(f"{end_n}{end_suf}")
        return out
    return [f"{end_n}{end_suf}"]


def expand_parity_range(
    start_s: str, end_s: str, parity: str
) -> List[str]:
    """«16а-74 (четные)» → 16а, 18, 20, …, 74."""
    start_n, start_suf = parse_num_suffix(start_s)
    end_n, end_suf = parse_num_suffix(end_s)
    want_even = "четн" in parity.lower()

    n = start_n
    if want_even and n % 2 == 1:
        n += 1
    if not want_even and n % 2 == 0:
        n += 1

    out: List[str] = []
    while n <= end_n:
        if n == start_n and start_suf:
            out.append(f"{n}{start_suf}")
        elif n == end_n and end_suf and n != start_n:
            out.append(f"{n}{end_suf}")
        else:
            out.append(str(n))
        n += 2
    return out


def normalize_chunk(chunk: str) -> List[str]:
    chunk = chunk.replace('"', "").strip()
    if not chunk:
        return []

    if contains_vse_doma(chunk) or SIDE_NOTE_ONLY.fullmatch(chunk):
        return [chunk]

    # с 1-19а
    m = re.fullmatch(r"с\s+(\d+)\s*-\s*(\d+)([а-яa-z]?)", chunk, re.I)
    if m:
        expanded = expand_range_with_end_suffix(m.group(1), m.group(2) + m.group(3))
        if expanded is not None:
            return expanded

    # частный сектор 1-37
    m = re.search(
        r"частный\s+сектор\s+(\d+)\s*-\s*(\d+)",
        chunk,
        re.I,
    )
    if m:
        start, end = int(m.group(1)), int(m.group(2))
        expanded = expand_pure_range(start, end)
        if expanded is not None:
            return expanded

    # 16а-74 (четные) / 15-85 (нечетные)
    m = re.fullmatch(
        r"(\d+)([а-яa-z]?)\s*-\s*(\d+)([а-яa-z]?)\s*\((четн|нечетн)[а-яё]*\)",
        chunk,
        re.I,
    )
    if m:
        return expand_parity_range(
            m.group(1) + m.group(2),
            m.group(3) + m.group(4),
            m.group(5),
        )

    m = re.fullmatch(
        r"(\d+)\s*-\s*(\d+)\s*\((четн|нечетн)[а-яё]*\)",
        chunk,
        re.I,
    )
    if m:
        return expand_parity_range(m.group(1), m.group(2), m.group(3))

    # 101-147 нечетные
    m = re.fullmatch(
        r"(\d+)\s*-\s*(\d+)\s+(четн|нечетн)[а-яё]*",
        chunk,
        re.I,
    )
    if m:
        return expand_parity_range(m.group(1), m.group(2), m.group(3))

    # 2-32 / 1-19а (простой диапазон)
    compact = re.sub(r"\s+", "", chunk)
    m = re.fullmatch(r"(\d+)([а-яa-z]?)-(\d+)([а-яa-z]?)", compact, re.I)
    if m:
        expanded = expand_range_with_end_suffix(
            m.group(1) + m.group(2),
            m.group(3) + m.group(4),
        )
        if expanded is not None:
            return expanded

    m = re.fullmatch(r"(\d+)-(\d+)", compact)
    if m:
        expanded = expand_pure_range(int(m.group(1)), int(m.group(2)))
        if expanded is not None:
            return expanded

    return [chunk]


def normalize_houses_field(houses: str) -> str:
    houses = houses.replace('"', "").strip()
    if should_skip_normalization(houses):
        return houses

    parts_out: List[str] = []
    for chunk in houses.split(","):
        parts_out.extend(normalize_chunk(chunk))

    # убрать пустые и двойные запятые
    cleaned: List[str] = []
    for p in parts_out:
        p = p.strip()
        if not p or p == ",":
            continue
        cleaned.append(p)
    return ", ".join(cleaned)


def repair_street_houses(street: str, houses: str) -> Tuple[str, str]:
    """Убирает номера домов из колонки «улица», если они продублированы в «дома»."""
    street = street.strip()
    houses = houses.strip().strip('"')

    if not street:
        return street, houses

    # «Вознесенская 16а-74 (четные)» в колонке улицы
    m = re.match(
        r"^([А-Яа-яЁё][А-Яа-яЁё\s\-]+?)\s+(\d+[а-яa-z]?\s*-\s*\d+.*)$",
        street,
        re.I,
    )
    if m:
        name = m.group(1).strip()
        tail = m.group(2).strip()
        if not houses or houses == tail or houses in street:
            return name, tail if not houses or houses == street else houses

    if not houses or not re.search(r"\d", street):
        return street, houses

    # «Пензенская 1А, …» / «Кавказский 1-й тупик 2А, 7, …»
    if "," in street:
        head = street.split(",", 1)[0].strip()
        tokens = head.split()
        if tokens and re.search(r"\d", tokens[-1]):
            name = " ".join(tokens[:-1]).strip()
            if len(name) >= 3:
                return name, houses

    # «Пензенская 1А» без запятой в улице
    tokens = street.split()
    if len(tokens) >= 2 and re.search(r"[\d/]", tokens[-1]):
        name = " ".join(tokens[:-1]).strip()
        if len(name) >= 3:
            return name, houses

    return street, houses


DISTRICT_LINE = re.compile(r"^[А-Яа-яЁё]+(?:ский|ской|ой);")


def split_semicolon_line(line: str, fields: int = 4) -> List[str]:
    """Ровно 4 поля: район;школа;улица;дома (дома могут содержать «;» только при дубле — берём последний сегмент)."""
    parts: List[str] = []
    rest = line
    for _ in range(fields - 1):
        idx = rest.index(";")
        parts.append(rest[:idx])
        rest = rest[idx + 1 :]
    parts.append(rest)
    return parts


def parse_row_line(line: str) -> Tuple[str, str, str, str]:
    parts = split_semicolon_line(line.strip(), 4)
    district, school, street = (
        parts[0].strip(),
        parts[1].strip(),
        parts[2].strip(),
    )
    houses = parts[3].strip().replace('"', "")
    # «…Пензенская 1А,…;1А, 3/1,…» — дубль: берём последний сегмент
    if ";" in houses:
        segments = [s.strip() for s in houses.split(";") if s.strip()]
        if (
            len(segments) >= 2
            and re.search(r"[\d/]", segments[-1])
            and re.search(r"[\d/]", segments[0])
            and street not in segments[-1]
        ):
            # Южная: «частный сектор 1-37…; 36, 36а…» — объединяем
            if any("частный" in s.lower() or re.search(r"\d+\s*-\s*\d+", s) for s in segments[:-1]):
                houses = ", ".join(segments)
            else:
                houses = segments[-1]
        else:
            houses = ", ".join(segments)
    street, houses = repair_street_houses(street, houses)
    return district, school, street, houses


def format_row_line(district: str, school: str, street: str, houses: str) -> str:
    return f"{district};{school};{street};{houses}"


def read_csv_rows(path: str) -> Tuple[str, List[str]]:
    """Читает CSV построчно (без «ломающих» кавычек в csv.reader)."""
    with open(path, encoding="utf-8") as f:
        lines = [ln.rstrip("\n\r") for ln in f.readlines()]
    if not lines:
        return "", []
    header = lines[0].strip()
    merged: List[str] = []
    buf: Optional[str] = None
    for line in lines[1:]:
        if not line.strip():
            continue
        if DISTRICT_LINE.match(line):
            if buf:
                merged.append(buf)
            buf = line
        elif buf:
            buf += line
        else:
            merged.append(line)
    if buf:
        merged.append(buf)
    return header, merged


def write_csv_rows(path: str, header: str, data_lines: List[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(header + "\n")
        f.write("\n".join(data_lines))
        if data_lines:
            f.write("\n")


def normalize_csv_file(
    csv_path: str,
    *,
    backup: bool = True,
    verbose: bool = True,
) -> dict[str, int]:
    if not os.path.isabs(csv_path):
        csv_path = os.path.join(os.getcwd(), csv_path)

    header, data_lines = read_csv_rows(csv_path)
    stats = {"rows": len(data_lines), "changed": 0, "skipped_vse": 0, "street_fixed": 0}

    new_lines: List[str] = []
    for line in data_lines:
        try:
            district, school, street, houses = parse_row_line(line)
        except ValueError:
            new_lines.append(line)
            continue

        orig_street, orig_houses = street, houses
        if contains_vse_doma(houses):
            stats["skipped_vse"] += 1
            new_lines.append(format_row_line(district, school, street, houses))
            continue

        new_houses = normalize_houses_field(houses)
        if street != orig_street:
            stats["street_fixed"] += 1

        out_line = format_row_line(district, school, street, new_houses)
        if new_houses != orig_houses or street != orig_street or out_line != line:
            stats["changed"] += 1
            if verbose and (new_houses != orig_houses or street != orig_street):
                print(f"  {street}", flush=True)
                if street != orig_street:
                    print(f"    улица: {orig_street!r} → {street!r}", flush=True)
                if new_houses != orig_houses:
                    preview = new_houses[:80] + ("…" if len(new_houses) > 80 else "")
                    print(f"    дома: {preview}", flush=True)

        new_lines.append(out_line)

    if backup:
        shutil.copy2(csv_path, csv_path + ".bak_normalize")
    write_csv_rows(csv_path, header, new_lines)

    if verbose:
        print(
            f"\nГотово: изменено {stats['changed']} строк, "
            f"пропущено с «все дома» — {stats['skipped_vse']}, "
            f"исправлено улиц — {stats['street_fixed']}",
            flush=True,
        )
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Нормализация номеров домов в CSV")
    ap.add_argument(
        "--csv",
        default="adreses_nears_school/ans_data/ans_stage1_adres_near_school_2.csv",
    )
    ap.add_argument("--no-backup", action="store_true")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args()
    normalize_csv_file(args.csv, backup=not args.no_backup, verbose=not args.quiet)


if __name__ == "__main__":
    main()
