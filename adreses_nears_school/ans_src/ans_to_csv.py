#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для преобразования обработанного файла адресов школ в CSV формат.

Структура CSV:
1. Район
2. Название школы
3. Название улицы
4. Номера домов
"""

import re
import csv
from pathlib import Path

# Пути к файлам
BASE_DIR = Path(__file__).parent.parent
INPUT_FILE = BASE_DIR / "ans_data" / "ans_stage1_adres_near_school.txt"
OUTPUT_FILE = BASE_DIR / "ans_data" / "ans_stage1_adres_near_school.csv"


def is_school_name(text):
    """
    Проверяет, является ли текст названием школы.
    Названия школ начинаются с: МОУ, МАОУ, ГАОУ, СО, ЧОУ и т.д.
    """
    if not text:
        return False
    text_stripped = text.strip()
    school_patterns = [
        r'^(МОУ|МАОУ|ГАОУ|СО|ЧОУ|МБОУ|ГБОУ|АНОО|МКОУ|ФГОУ|ФГБОУ)\s*[«"]',
    ]
    for pattern in school_patterns:
        if re.match(pattern, text_stripped):
            return True
    return False


def is_house_numbers(text):
    """
    Проверяет, является ли текст номерами домов.
    Номера домов обычно содержат:
    - цифры
    - запятые
    - дефисы (диапазоны)
    - слэши
    - фразу "все дома"
    - слова типа "коттеджная застройка"
    
    НЕ являются номерами домов:
    - слова типа "проезд", "улица", "проспект" и т.д.
    - порядковые числительные типа "2й", "1-й" (начало названия улицы)
    - названия населённых пунктов типа "п. Рейник", "с. Александровка"
    - названия СТ (садовых товариществ) типа "СТ «Рубин-1»"
    - названия посёлков типа "Поселок 2-ая Гуселка"
    - тексты, содержащие ключевые слова улиц (даже если содержат цифры)
    """
    if not text:
        return False
    text_stripped = text.strip().lower()
    
    # Если содержит ключевые слова улиц - это не номера домов
    street_keywords = ['проезд', 'улица', 'проспект', 'тупик', 'взвоз', 'набережная', 'переулок', 'площадь', 'проезды']
    if any(keyword in text_stripped for keyword in street_keywords):
        return False
    
    # Если это типичное слово для названия улицы - это не номера домов
    if text_stripped in street_keywords:
        return False
    
    # Если начинается с порядкового числительного (2й, 1-й, 3-й и т.д.) - это начало названия улицы
    if re.match(r'^\d+[-]?[йй]', text_stripped):
        return False
    
    # Если начинается с обозначения населённого пункта (п., с., д. и т.д.) - это не номера домов
    if re.match(r'^(п\.|с\.|д\.|пос\.|поселок)', text_stripped):
        return False
    
    # Если начинается с "СТ" (садовое товарищество) - это не номера домов
    # Проверяем как "ст " так и "СТ «" (с кавычками)
    if re.match(r'^ст\s+', text_stripped) or re.match(r'^ст\s*[«"]', text, re.IGNORECASE):
        return False
    
    # Если содержит "поселок" или "пос." - это не номера домов
    if 'поселок' in text_stripped or 'пос.' in text_stripped:
        return False
    
    # Если содержит "СТ" (садовое товарищество) с кавычками - это не номера домов
    if re.search(r'ст\s*[«"]', text, re.IGNORECASE):
        return False
    
    # Если содержит "2-ая", "3-я" и т.д. (порядковые числительные в женском роде) - это не номера домов
    if re.search(r'\d+[-]?[ая]я', text_stripped):
        return False
    
    # Если содержит "все дома" или похожие фразы
    if 'все дома' in text_stripped or 'коттеджная' in text_stripped:
        return True
    
    # Если содержит цифры и типичные для номеров домов символы
    if re.search(r'\d', text_stripped):
        # Проверяем наличие типичных паттернов для номеров домов
        # Но исключаем случаи, когда это начало названия улицы
        # (например, "2й Детский" не является номерами домов)
        if re.search(r'(\d+[-\d/]*|\d+[а-я]*|\d+\s*[а-я]+)', text_stripped):
            # Дополнительная проверка: если содержит только одну цифру и слово после неё
            # (типа "2й Детский"), то это не номера домов
            if re.match(r'^\d+[-]?[йй]?\s*[а-я]+', text_stripped):
                return False
            # Если содержит запятую и порядковое числительное (типа "п. Рейник, 1-й") - это не номера домов
            if re.search(r',\s*\d+[-]?[йй]', text_stripped):
                return False
            # Если содержит паттерн "цифра-цифра слово" (типа "1-10 Парусный") - это не номера домов
            # Это название улицы с диапазоном номеров в начале
            if re.search(r'\d+-\d+\s+[а-я]+', text_stripped):
                return False
            # Если содержит паттерн "цифра-цифра слово" в начале (типа "1-9 Ртищевский") - это не номера домов
            if re.match(r'^\d+-\d+\s+[а-я]+', text_stripped):
                return False
            # Если содержит паттерн "цифра-цифра" в начале и после него идёт заглавная буква (типа "1-9 Ртищевский") - это не номера домов
            if re.match(r'^\d+-\d+\s+[А-Я]', text):
                return False
            # Если содержит паттерн номеров домов с буквами и запятыми (типа "1А, 2А, 2Б, 2Б/1")
            # Это явно номера домов
            if re.match(r'^(\d+[а-яА-Я]*(/\d+)?,?\s*)+$', text):
                return True
            # Если содержит только цифры, запятые, дефисы, слэши и пробелы - это номера домов
            # Но не если это диапазон с заглавной буквой после (типа "1-10 Парусный")
            if re.match(r'^[\d\s,\-/]+$', text_stripped):
                return True
            return True
    
    return False


def parse_line(line):
    """
    Разбирает строку на столбцы: Район, Школа, Улица, Дома
    
    Args:
        line: Строка для разбора
        
    Returns:
        tuple: (район, школа, улица, дома) или None если строка невалидна
    """
    if not line or not line.strip():
        return None
    
    # Пропускаем заголовок
    if line.startswith('Район'):
        return None
    
    # Разбиваем по табам
    parts = line.split('\t')
    
    if len(parts) < 2:
        return None
    
    # Первое поле - район
    district = parts[0].strip()
    if not district:
        return None
    
    # Ищем название школы
    school_name = None
    school_end_idx = None
    
    for i in range(1, len(parts)):
        part = parts[i].strip()
        if is_school_name(part):
            # Нашли начало школы
            school_parts = [part]
            # Собираем все части школы (может быть разбито на несколько частей)
            # Школа заканчивается на », но может иметь продолжение типа "района г. Саратова"
            # или адрес школы типа "Державинская, 1"
            for j in range(i + 1, len(parts)):
                next_part = parts[j].strip()
                
                # Если следующая часть является началом новой школы - останавливаемся
                if is_school_name(next_part):
                    break
                
                # Проверяем, является ли это продолжением названия школы
                # Продолжение школы обычно содержит слова типа "района", "г.", "Саратова"
                # или является адресом школы (название улицы + номер дома)
                current_school_text = ' '.join(school_parts)
                
                if '»' in current_school_text:
                    # Школа уже закрыта », следующая часть может быть продолжением только если:
                    # 1. Содержит слова "района", "г.", "Саратова" (продолжение названия школы)
                    # 2. Является адресом школы (название улицы + номер дома, например "Державинская, 1" или "Казанская, 29")
                    #    НО только если после него НЕТ другого поля, которое является названием улицы для закрепления
                    # 3. НЕ начинается с типичных для улиц слов (им., проспект, улица и т.д.)
                    
                    # Проверяем, является ли это адресом школы (паттерн: название улицы, запятая, номер)
                    # Адрес школы: начинается с заглавной буквы, содержит название улицы, запятую и номер в конце
                    # Примеры: "Державинская, 1", "Казанская, 29"
                    # НЕ адрес школы: "с.Александровка, Березовый пер." (нет номера в конце)
                    is_school_address = bool(re.match(r'^[А-Я][А-Яа-я\s]+,?\s*\d+$', next_part))
                    
                    if re.search(r'(района|г\.|Саратова)', next_part):
                        # Это продолжение названия школы
                        school_parts.append(next_part)
                    elif is_school_address:
                        # Это адрес школы (например, "Державинская, 1" или "Казанская, 29")
                        # Адрес школы всегда является частью названия школы
                        school_parts.append(next_part)
                    elif re.match(r'^(им\.|проспект|улица|проезд|тупик|взвоз|набережная|Князевский|Мичурина|Вознесенская|Зарубина)', next_part, re.IGNORECASE):
                        # Это название улицы, останавливаемся
                        break
                    elif is_house_numbers(next_part):
                        # Это номера домов, останавливаемся
                        break
                    else:
                        # Если не соответствует паттерну адреса школы и не является типичными словами,
                        # то это название улицы для закрепления (например, "с.Александровка, Березовый пер.")
                        break
                else:
                    # Школа ещё не закрыта », следующая часть может быть продолжением
                    # только если не начинается с типичных для улиц слов
                    if re.match(r'^(им\.|проспект|улица|проезд|тупик|взвоз|набережная)', next_part, re.IGNORECASE):
                        # Это название улицы
                        break
                    # Проверяем, не является ли это названием улицы
                    # Названия улиц обычно не содержат слова "района", "г.", "Саратова"
                    if not re.search(r'(района|г\.|Саратова)', next_part):
                        # Возможно, это название улицы, но может быть и продолжением школы
                        # Если следующая часть - отдельное поле (не часть многострочного названия),
                        # то скорее всего это улица
                        school_parts.append(next_part)
                    else:
                        # Содержит слова для продолжения школы
                        school_parts.append(next_part)
            
            school_name = ' '.join(school_parts)
            school_end_idx = i + len(school_parts)
            break
    
    if not school_name:
        return None
    
    # Всё что после школы до номеров домов - это название улицы
    street_parts = []
    house_numbers = None
    
    street_keywords = ['проезд', 'улица', 'проспект', 'тупик', 'взвоз', 'набережная', 'переулок', 'площадь', 'проезды']
    
    i = school_end_idx
    while i < len(parts):
        part = parts[i].strip()
        
        if not part:
            i += 1
            continue
        
        # Проверяем, не является ли это началом новой школы (на случай ошибок в данных)
        if is_school_name(part):
            # Это начало новой школы - останавливаемся
            break
        
        # Проверяем, содержит ли часть слова, типичные для названий улиц
        # (проезд, улица, проспект и т.д.) - даже если начинается с цифр
        is_street_name = any(keyword in part.lower() for keyword in street_keywords)
        
        # Если содержит ключевые слова улиц, это точно название улицы
        if is_street_name:
            street_parts.append(part)
            i += 1
            continue
        
        # Проверяем следующее поле, чтобы понять, является ли текущее поле частью названия улицы
        next_part = None
        next_has_street_keyword = False
        if i + 1 < len(parts):
            next_part = parts[i + 1].strip()
            next_has_street_keyword = any(keyword in next_part.lower() for keyword in street_keywords) if next_part else False
        
        # Если следующая часть содержит ключевые слова улиц, то текущая часть - это тоже часть названия улицы
        if next_has_street_keyword:
            street_parts.append(part)
            i += 1
            continue
        
        # Проверяем, является ли это номерами домов
        # Важно: проверяем ДО того, как добавим в название улицы
        # Но также проверяем, не является ли это частью названия улицы
        
        # Специальная проверка: если текущее поле выглядит как часть названия улицы
        # (содержит порядковые числительные, названия населённых пунктов, СТ и т.д.),
        # то это НЕ номера домов, даже если содержит цифры
        is_likely_street_part = False
        
        # Если начинается с обозначения населённого пункта (п., с., д. и т.д.) - это часть улицы
        if re.match(r'^(п\.|с\.|д\.|пос\.|поселок)', part, re.IGNORECASE):
            is_likely_street_part = True
        
        # Если начинается с "СТ" (садовое товарищество) - это часть улицы
        if re.match(r'^СТ\s*[«"]', part, re.IGNORECASE):
            is_likely_street_part = True
        
        # Если содержит "поселок" - это часть улицы
        if 'поселок' in part.lower():
            is_likely_street_part = True
        
        # Если содержит порядковое числительное в начале (1-й, 2й, 1-9 и т.д.) и не является номерами домов
        if re.match(r'^\d+[-]?[йй]?\s+[А-Яа-я]', part):
            is_likely_street_part = True
        
        # Если содержит паттерн "цифра-цифра слово" (типа "1-9 Ртищевский") - это часть улицы
        if re.match(r'^\d+-\d+\s+[А-Яа-я]', part):
            is_likely_street_part = True
        
        # Если это похоже на часть улицы, добавляем в название улицы
        if is_likely_street_part:
            street_parts.append(part)
            i += 1
            continue
        
        # Проверяем, является ли это номерами домов
        if is_house_numbers(part):
            # Нашли номера домов
            house_parts = [part]
            # Собираем все части номеров домов (могут быть разбиты)
            for j in range(i + 1, len(parts)):
                next_part = parts[j].strip()
                if is_house_numbers(next_part) or not next_part:
                    house_parts.append(next_part)
                else:
                    break
            house_numbers = ' '.join(house_parts).strip()
            break
        
        # Если это не номера домов и не начало новой школы, то это часть названия улицы
        # Собираем все части названия улицы до тех пор, пока не встретим номера домов
        street_parts.append(part)
        i += 1
    
    street_name = ' '.join(street_parts).strip() if street_parts else ''
    
    # Если не нашли номера домов, но есть последнее поле - возможно это номера домов
    if not house_numbers and len(parts) > school_end_idx:
        last_part = parts[-1].strip()
        if is_house_numbers(last_part):
            house_numbers = last_part
            # Убираем последнее поле из названия улицы
            if street_parts and street_parts[-1] == last_part:
                street_parts.pop()
                street_name = ' '.join(street_parts).strip()
    
    return (district, school_name, street_name, house_numbers)


def convert_to_csv(input_path, output_path):
    """
    Преобразует файл в CSV формат.
    
    Args:
        input_path: Путь к входному файлу
        output_path: Путь к выходному CSV файлу
    """
    rows = []
    
    with open(input_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.rstrip('\n')
            parsed = parse_line(line)
            if parsed:
                rows.append(parsed)
            elif line_num == 1 and line.startswith('Район'):
                # Добавляем заголовок CSV
                rows.append(('Район', 'Краткое наименование ОУ', 'Название улицы', 'Номера домов'))
    
    # Записываем в CSV
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        for row in rows:
            writer.writerow(row)
    
    print(f"[OK] Обработано строк: {len(rows)}")
    print(f"[OK] CSV файл сохранён в: {output_path}")


def main():
    """Основная функция"""
    print("=" * 60)
    print("Преобразование файла адресов школ в CSV")
    print("=" * 60)
    print(f"Входной файл: {INPUT_FILE}")
    print(f"Выходной файл: {OUTPUT_FILE}")
    print()
    
    if not INPUT_FILE.exists():
        print(f"[ERROR] Файл не найден: {INPUT_FILE}")
        return
    
    convert_to_csv(INPUT_FILE, OUTPUT_FILE)
    print()
    print("=" * 60)
    print("Преобразование завершено")
    print("=" * 60)


if __name__ == "__main__":
    main()

