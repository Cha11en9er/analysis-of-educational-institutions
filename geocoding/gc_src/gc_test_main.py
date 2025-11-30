import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
RM_ROOT = os.path.dirname(CURRENT_DIR)
DATA_DIR = os.path.join(RM_ROOT, 'gc_data')
INPUT_DIR = os.path.join(DATA_DIR, 'gc_input')
OUTPUT_DIR = os.path.join(DATA_DIR, 'gc_output')
INPUT_DATA_FILE = os.path.join(INPUT_DIR, 'gc_test_input_data.json')
OUTPUT_DATA_FILE = os.path.join(OUTPUT_DIR, 'gc_test_output_data.json')

# Загружаем список объектов из JSON-файла
with open(INPUT_DATA_FILE, 'r', encoding='utf-8') as file:
    data = json.load(file)

# Извлекаем массив школ из ключа 'data'
schools = data.get('data', [])

# Ваш ключ API от Яндекс.Карт
API_KEY = os.getenv("YANDEX_API_KEY")

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
    print(f"Геокодируем школу {school['name']}")
    result = geocode_address(school['adres_part2'])
    if result is not None:
        # Добавляем поле coordinates в формате (широта, долгота)
        school['coordinates'] = f"({result['latitude']}, {result['longitude']})"
        print(f"Координаты: {school['coordinates']}")
    else:
        # Если геокодирование не удалось, добавляем None
        school['coordinates'] = None
        print("Ошибка геокодирования.")

# Сохраняем результат в output JSON файл с сохранением исходной структуры
output_data = {
    'source': data.get('source'),
    'topic': data.get('topic'),
    'total_elements': data.get('total_elements'),
    'data': schools
}

with open(OUTPUT_DATA_FILE, 'w', encoding='utf-8') as file:
    json.dump(output_data, file, ensure_ascii=False, indent=4)

print(f"\n[OK] Результаты сохранены в файл: {OUTPUT_DATA_FILE}")