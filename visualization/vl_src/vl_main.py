import folium
import json
import os
import re

# Пути к файлам
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
VL_ROOT = os.path.dirname(CURRENT_DIR)
DATA_DIR = os.path.join(VL_ROOT, 'vl_data')
INPUT_DIR = os.path.join(DATA_DIR, 'vl_input')
INPUT_FILE = os.path.join(INPUT_DIR, 'vl_test_input_data.json')
OUTPUT_FILE = os.path.join(CURRENT_DIR, 'school_map.html')

def parse_geocoords(geocoords_str):
    """Парсит строку geocoords в формате '(lat, lon)' в кортеж (lat, lon)"""
    if not geocoords_str:
        return None
    # Удаляем скобки и пробелы, разделяем по запятой
    coords_str = geocoords_str.strip('()').replace(' ', '')
    try:
        lat, lon = map(float, coords_str.split(','))
        return (lat, lon)
    except (ValueError, AttributeError):
        return None

def get_school_name(school_data):
    """Получает название школы: приоритет yandex_name, затем 2gis_name, затем 2gis_full_name"""
    return (school_data.get('yandex_name') or 
            school_data.get('2gis_name') or 
            school_data.get('2gis_full_name') or 
            'Неизвестная школа')

def create_school_map(input_file_path, output_file_path):
    """Создает карту со всеми школами из JSON файла"""
    # Загружаем данные из JSON
    with open(input_file_path, "r", encoding='utf-8') as f:
        data = json.load(f)
    
    schools = data.get('data', [])
    
    if not schools:
        print("[WARN] Нет данных для отображения")
        return
    
    # Фильтруем школы с валидными координатами
    valid_schools = []
    for school in schools:
        geocoords_str = school.get('geocoords')
        if geocoords_str:
            coords = parse_geocoords(geocoords_str)
            if coords:
                valid_schools.append((school, coords))
    
    if not valid_schools:
        print("[WARN] Нет школ с валидными координатами")
        return
    
    print(f"[INFO] Найдено школ с координатами: {len(valid_schools)}")
    
    # Вычисляем центр карты (среднее значение всех координат)
    avg_lat = sum(coords[0] for _, coords in valid_schools) / len(valid_schools)
    avg_lon = sum(coords[1] for _, coords in valid_schools) / len(valid_schools)
    
    # Создаем карту, центрируем на средних координатах
    map_schools = folium.Map(location=(avg_lat, avg_lon), zoom_start=12)
    
    # Добавляем маркеры для каждой школы
    for school_data, coords in valid_schools:
        name = get_school_name(school_data)
        
        # Формируем текст всплывающей подсказки (HTML)
        popup_html = f"<b>{name}</b><br>"
        
        # Добавляем id, если есть
        school_id = school_data.get('id')
        if school_id:
            popup_html += f"ID: {school_id}<br>"
        
        # Добавляем адрес, если есть
        adres = school_data.get('adres') or school_data.get('ym_adres') or ''
        if adres:
            popup_html += f"Адрес: {adres}<br>"
        
        # Добавляем рейтинги, если есть
        ratings = []
        if school_data.get('ym_rating'):
            ratings.append(f"Яндекс: {school_data['ym_rating']}")
        if school_data.get('2gis_rating'):
            ratings.append(f"2GIS: {school_data['2gis_rating']}")
        if ratings:
            popup_html += f"Рейтинг: {', '.join(ratings)}<br>"
        
        # Добавляем ссылки
        if school_data.get('ym_url'):
            popup_html += f'<a href="{school_data["ym_url"]}" target="_blank">Яндекс Карты</a><br>'
        if school_data.get('2gis_url'):
            popup_html += f'<a href="{school_data["2gis_url"]}" target="_blank">2GIS</a><br>'
        
        # Добавляем маркер с информацией
        folium.Marker(
            location=coords,
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=name  # текст при наведении
        ).add_to(map_schools)
    
    # Сохраняем карту в HTML файл
    map_schools.save(output_file_path)
    print(f"[OK] Карта сохранена в файл {output_file_path}")
    print(f"[OK] Всего отображено школ: {len(valid_schools)}")

if __name__ == "__main__":
    create_school_map(INPUT_FILE, OUTPUT_FILE)