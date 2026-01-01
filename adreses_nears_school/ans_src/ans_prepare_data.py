#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для подготовки данных адресов школ.
Объединяет разбитые на несколько строк записи в одну строку.

Логика работы:
1. Находит строки, начинающиеся с названия района (оканчивается на "ский")
2. Всё что между названиями районов объединяет в одну строку
3. Если между строками разница больше 1 строки, использует пробел как разделитель
"""

import os
import re
from pathlib import Path

# Пути к файлам
BASE_DIR = Path(__file__).parent.parent
INPUT_FILE = BASE_DIR / "ans_data" / "ans_adres_near_school.txt"
OUTPUT_FILE = BASE_DIR / "ans_data" / "ans_stage1_adres_near_school.txt"


def is_district_name(line):
    """
    Проверяет, начинается ли строка с названия района.
    Районы оканчиваются на "ский" (Волжский, Гагаринский, Заводской и т.д.)
    
    Важно: 
    1. Строка должна начинаться с начала (не с дефиса или пробела)
    2. После названия района должна быть табуляция
    3. После табуляции должно идти название школы (МОУ, МАОУ, ГАОУ и т.д.)
    Если после табуляции нет названия школы - это не район, а часть адреса.
    """
    if not line or not line.strip():
        return False
    
    # Если строка начинается с дефиса или пробела - это продолжение, а не новый район
    stripped = line.lstrip()
    if line != stripped or line.startswith('-'):
        return False
    
    # Убираем пробелы в начале для проверки паттерна
    line_clean = line.strip()
    
    # Проверяем, начинается ли строка с названия района
    # Паттерн: слово, оканчивающееся на "ский" или "ской", за которым идёт ТАБУЛЯЦИЯ
    pattern = r'^[А-Яа-я]+(ский|ской)\t'
    if not re.match(pattern, line_clean):
        return False
    
    # Дополнительная проверка: после табуляции должно идти название школы
    # Названия школ начинаются с: МОУ, МАОУ, ГАОУ, СО, ЧОУ и т.д.
    parts = line_clean.split('\t')
    if len(parts) < 2:
        return False
    
    # Вторая часть (после первой табуляции) должна начинаться с названия школы
    second_part = parts[1].strip()
    school_patterns = [
        r'^МОУ\s*[«"]',  # МОУ «...
        r'^МАОУ\s*[«"]',  # МАОУ «...
        r'^ГАОУ\s*',      # ГАОУ ...
        r'^СО\s*[«"]',     # СО «...
        r'^ЧОУ\s*',       # ЧОУ ...
    ]
    
    # Если вторая часть начинается с названия школы - это район
    for pattern in school_patterns:
        if re.match(pattern, second_part):
            return True
    
    # Если не начинается с названия школы - это не район, а часть адреса
    return False


def normalize_tabs(line):
    """
    Исправляет пробелы на табы в нужных местах:
    1. После названия района (оканчивается на "ский" или "ской") должен быть tab
    2. После названия школы (оканчивается на ») должен быть tab
    Важно: таб ставится только после ПЕРВОГО » (которое закрывает название школы),
    а не после всех » в строке.
    
    Args:
        line: Строка для обработки
        
    Returns:
        Исправленная строка
    """
    if not line:
        return line
    
    # 1. Исправляем пробел после названия района на tab
    # Паттерн: название района (оканчивается на "ский" или "ской") + пробел(ы) + следующий текст
    # Но только если после пробела НЕ идёт tab (чтобы не дублировать)
    line = re.sub(r'([А-Яа-я]+(ский|ской))\s+([^\t])', r'\1\t\3', line)
    
    # 2. Исправляем пробел после названия школы (оканчивается на ») на tab
    # Важно: обрабатываем только ПЕРВОЕ вхождение » (которое закрывает название школы)
    if '»' in line:
        # Находим индекс первого »
        first_quote_idx = line.find('»')
        if first_quote_idx != -1:
            # Разделяем строку на части: до первого », первый », и после первого »
            before_first = line[:first_quote_idx]
            first_quote = '»'
            after_first = line[first_quote_idx + 1:]
            
            # Если после первого » идёт пробел(ы) - заменяем первый пробел на tab
            if after_first.startswith(' '):
                # Считаем количество пробелов в начале
                space_count = len(after_first) - len(after_first.lstrip(' '))
                if space_count > 0:
                    # Заменяем первый пробел на tab, остальные пробелы оставляем
                    after_first = '\t' + after_first[space_count:]
            
            # Собираем строку обратно
            line = before_first + first_quote + after_first
    
    return line


def split_multiple_schools(line):
    """
    Разбивает строку на несколько строк, если в поле "название школы" указано несколько школ.
    
    Пример:
    Вход: "Кировский\tМОУ «ООШ № 17»\t(1-9-е классы), МОУ «СОШ № 54» (10-11-е классы)\tОфицерская\tс 7 по 85"
    Выход: [
        "Кировский\tМОУ «ООШ № 17»\t(1-9-е классы)\tОфицерская\tс 7 по 85",
        "Кировский\tМОУ «СОШ № 54» (10-11-е классы)\tОфицерская\tс 7 по 85"
    ]
    
    Args:
        line: Строка для обработки
        
    Returns:
        Список строк (если школ несколько) или список с одной строкой (если школа одна)
    """
    if not line or not line.strip():
        return [line]
    
    # Пропускаем заголовок
    if line.startswith('Район'):
        return [line]
    
    # Разбиваем строку по табам
    parts = line.split('\t')
    
    # Должно быть минимум 2 поля: район и название школы
    if len(parts) < 2:
        return [line]
    
    district = parts[0]  # Район
    
    # Объединяем поля, которые могут содержать название школы
    # После нормализации табов поле школы может быть разбито на несколько частей
    # Например: parts[1] = "МОУ «ООШ № 17»", parts[2] = "(1-9-е классы), МОУ «СОШ № 54»..."
    # Нужно объединить их, если во втором поле содержится новая школа
    
    school_pattern = r'(МОУ|МАОУ|ГАОУ|СО|ЧОУ|МБОУ|ГБОУ|АНОО|МКОУ|ФГОУ|ФГБОУ)\s*[«"]'
    
    # Собираем поле школы из нескольких частей, если нужно
    school_field_parts = []
    rest_fields_start_idx = 1
    
    for i in range(1, len(parts)):
        part = parts[i]
        part_stripped = part.strip()
        
        # Проверяем, начинается ли эта часть с новой школы
        if re.match(school_pattern, part_stripped):
            # Если это первая часть школы - начинаем собирать
            if len(school_field_parts) == 0:
                school_field_parts.append(part)
                rest_fields_start_idx = i + 1
            else:
                # Это начало новой школы - останавливаемся
                break
        else:
            # Проверяем, содержит ли эта часть паттерн школы (может быть где-то в середине)
            if re.search(school_pattern, part_stripped):
                # Содержит школу - это продолжение поля школы
                if len(school_field_parts) > 0:
                    school_field_parts.append(part)
                    rest_fields_start_idx = i + 1
                else:
                    # Если ещё не начали собирать школу, но часть содержит школу
                    # значит это начало поля школы
                    school_field_parts.append(part)
                    rest_fields_start_idx = i + 1
            else:
                # Это продолжение текущей части (классы, запятая и т.д.)
                # Но только если это выглядит как продолжение поля школы
                if len(school_field_parts) > 0:
                    # Проверяем, является ли это продолжением поля школы:
                    # 1. Начинается с "(" для классов
                    # 2. ИЛИ содержит запятую, за которой следует паттерн школы (новая школа)
                    is_continuation = False
                    if part_stripped.startswith('('):
                        is_continuation = True
                    elif ',' in part_stripped:
                        # Проверяем, есть ли после запятой паттерн школы
                        # Это означает, что в этой части есть новая школа
                        if re.search(r',\s*' + school_pattern, part_stripped):
                            is_continuation = True
                    
                    if is_continuation:
                        school_field_parts.append(part)
                        rest_fields_start_idx = i + 1
                    else:
                        # Это уже не часть поля школы, а адрес или дома
                        break
                else:
                    # Если ещё не начали собирать школу, но часть не содержит школу
                    # значит это уже не часть названия школы, а адрес или дома
                    break
    
    # Объединяем части поля школы через пробел (так как между ними был таб, но это продолжение одного поля)
    school_field = ' '.join(school_field_parts) if school_field_parts else parts[1]
    rest_fields = parts[rest_fields_start_idx:] if rest_fields_start_idx < len(parts) else []
    
    # Проверяем, есть ли в поле школы несколько школ
    # Находим все вхождения школ в объединённом поле
    school_matches = list(re.finditer(school_pattern, school_field))
    
    # Если найдено меньше 2 школ - возвращаем исходную строку
    if len(school_matches) < 2:
        return [line]
    
    # Разбиваем поле школы на отдельные школы
    result_lines = []
    
    for i, match in enumerate(school_matches):
        # Начало текущей школы
        start_idx = match.start()
        
        # Конец текущей школы (начало следующей или конец строки)
        if i + 1 < len(school_matches):
            # Есть следующая школа - берём до начала следующей (минус запятая и пробелы)
            end_idx = school_matches[i + 1].start()
            # Убираем запятую и пробелы в конце
            school_text = school_field[start_idx:end_idx].rstrip(', ')
        else:
            # Последняя школа - берём до конца строки
            school_text = school_field[start_idx:].strip()
        
        # Создаём новую строку: район + название школы + остальные поля
        new_line_parts = [district, school_text] + rest_fields
        new_line = '\t'.join(new_line_parts)
        result_lines.append(new_line)
    
    return result_lines


def process_file(input_path, output_path):
    """
    Обрабатывает файл, объединяя разбитые записи.
    
    Args:
        input_path: Путь к входному файлу
        output_path: Путь к выходному файлу
    """
    result_lines = []
    current_record = None
    
    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Пропускаем первую строку (заголовок)
    if lines:
        result_lines.append(lines[0].rstrip('\n'))
    
    # Обрабатываем остальные строки
    for i, line in enumerate(lines[1:], start=1):
        line = line.rstrip('\n')
        
        # Пропускаем пустые строки
        if not line.strip():
            continue
        
        # Если строка начинается с дефиса - это всегда продолжение предыдущей записи
        if line.strip().startswith('-'):
            # Убираем дефис и добавляем к текущей записи
            if current_record is not None:
                continuation = line.strip().lstrip('-').strip()
                current_record = current_record + " " + continuation
            else:
                # Если нет текущей записи, но строка начинается с дефиса - пропускаем дефис
                current_record = line.strip().lstrip('-').strip()
            continue
        
        # Если строка начинается с названия района - это новая запись
        if is_district_name(line):
            # Сохраняем предыдущую запись, если она есть
            if current_record is not None:
                # Нормализуем табы перед сохранением
                current_record = normalize_tabs(current_record)
                result_lines.append(current_record)
            
            # Начинаем новую запись и нормализуем табы
            current_record = normalize_tabs(line)
        else:
            # Это продолжение предыдущей записи
            if current_record is not None:
                # Объединяем через пробел
                current_record = current_record + " " + line.strip()
            else:
                # Если нет текущей записи, но строка не начинается с района
                # (может быть случай, когда файл начинается не с района)
                current_record = normalize_tabs(line)
    
    # Сохраняем последнюю запись
    if current_record is not None:
        # Нормализуем табы перед сохранением
        current_record = normalize_tabs(current_record)
        result_lines.append(current_record)
    
    # Разбиваем строки с несколькими школами и записываем результат в файл
    final_lines = []
    with open(output_path, 'w', encoding='utf-8') as f:
        for line in result_lines:
            # Дополнительная нормализация табов для всех строк (на случай заголовка)
            if line and not line.startswith('Район'):  # Не трогаем заголовок
                line = normalize_tabs(line)
            
            # Разбиваем строку, если в ней несколько школ
            split_lines = split_multiple_schools(line)
            final_lines.extend(split_lines)
            
            # Записываем все строки (может быть несколько, если было разбиение)
            for split_line in split_lines:
                f.write(split_line + '\n')
    
    print(f"[OK] Обработано строк: {len(lines)}")
    print(f"[OK] Получено записей после объединения: {len(result_lines) - 1}")  # -1 потому что первая строка - заголовок
    print(f"[OK] Получено записей после разбиения школ: {len(final_lines) - 1}")  # -1 потому что первая строка - заголовок
    print(f"[OK] Результат сохранён в: {output_path}")


def main():
    """Основная функция"""
    print("=" * 60)
    print("Обработка файла адресов школ")
    print("=" * 60)
    print(f"Входной файл: {INPUT_FILE}")
    print(f"Выходной файл: {OUTPUT_FILE}")
    print()
    
    if not INPUT_FILE.exists():
        print(f"[ERROR] Файл не найден: {INPUT_FILE}")
        return
    
    process_file(INPUT_FILE, OUTPUT_FILE)
    print()
    print("=" * 60)
    print("Обработка завершена")
    print("=" * 60)


if __name__ == "__main__":
    main()

