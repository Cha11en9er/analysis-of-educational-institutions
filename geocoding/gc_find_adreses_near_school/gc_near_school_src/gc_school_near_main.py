import requests
import json
import os
import re
from dotenv import load_dotenv

load_dotenv()

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
RM_ROOT = os.path.dirname(CURRENT_DIR)
DATA_DIR = os.path.join(RM_ROOT, 'gc_data')
INPUT_DIR = os.path.join(DATA_DIR, 'gc_input')
OUTPUT_DIR = os.path.join(DATA_DIR, 'gc_output')
INPUT_DATA_FILE = os.path.join(INPUT_DIR, 'gc_school_near_input_data.json')
OUTPUT_DATA_FILE = os.path.join(OUTPUT_DIR, 'gc_school_near_output_data.json')

# Загружаем список объектов из JSON-файла
with open(INPUT_DATA_FILE, 'r', encoding='utf-8') as file:
    schools = json.load(file)

# Ваш ключ API от Яндекс.Карт
API_KEY = os.getenv("YANDEX_API_KEY")

def clean_school_name(name):
    """
    Очищает название школы от лишних фраз:
    - Убирает "(5-11-е классы)"
    - Убирает "(5-11-е классы) (по согласованию)"
    """
    # Убираем "(5-11-е классы) (по согласованию)"
    name = re.sub(r'\s*\(5-11-е классы\)\s*\(по согласованию\)', '', name)
    # Убираем "(5-11-е классы)"
    name = re.sub(r'\s*\(5-11-е классы\)', '', name)
    # Убираем лишние пробелы
    name = name.strip()
    return name

def geocode_address(address):
    """
    Функция для геокодирования адреса с использованием Яндекс.Карт.
    Возвращает координаты в формате широта/долгота.
    """
    base_url = f'https://geocode-maps.yandex.ru/1.x/'
    params = {
        'apikey': API_KEY,
        'format': 'json',
        'geocode': address
    }
    
    response = requests.get(base_url, params=params)
    data = response.json()
    
    if not data['response']['GeoObjectCollection']['featureMember']:
        return None
        
    geo_object = data['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']
    coordinates = geo_object['Point']['pos'].split()  # долгота, широта
    latitude, longitude = float(coordinates[1]), float(coordinates[0])
    return {'latitude': latitude, 'longitude': longitude}

# Обрабатываем каждую школу и добавляем координаты
for school in schools:
    # Очищаем название школы
    cleaned_name = clean_school_name(school['school_near_name'])
    district = school['district_near_name']
    
    # Формируем адрес для геокодирования: город Саратов, 'название района' район, 'название школы'
    address = f"город Саратов, {district} район, {cleaned_name}"
    
    print(f"Геокодируем школу: {cleaned_name} ({district})")
    print(f"Адрес для геокодирования: {address}")
    
    result = geocode_address(address)
    if result is not None:
        # Добавляем поле coordinates в формате (широта, долгота)
        school['coordinates'] = f"({result['latitude']}, {result['longitude']})"
        print(f"Координаты: {school['coordinates']}")
    else:
        # Если геокодирование не удалось, добавляем None
        school['coordinates'] = None
        print("Ошибка геокодирования.")
    print()

# Сохраняем результат в output JSON файл
with open(OUTPUT_DATA_FILE, 'w', encoding='utf-8') as file:
    json.dump(schools, file, ensure_ascii=False, indent=2)

print(f"\n[OK] Результаты сохранены в файл: {OUTPUT_DATA_FILE}")
print(f"Всего обработано школ: {len(schools)}")

