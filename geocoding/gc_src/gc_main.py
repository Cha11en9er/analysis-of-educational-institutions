import requests
import json
import os
from pathlib import Path

from dotenv import load_dotenv

GC_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = GC_ROOT.parent

for env_path in (REPO_ROOT / ".env", GC_ROOT / ".env"):
    if env_path.is_file():
        load_dotenv(env_path)

SARATOV_CENTER = "51.53, 46.00"
SEARCH_RADIUS = "1.5, 1.5"
BASE_URL = "https://geocode-maps.yandex.ru/1.x/"
REGION = "Саратовская область"
CITY = "Саратов"


def with_saratov_context(address: str) -> str:
    low = address.lower()
    if "саратов" in low:
        return address
    return f"{REGION}, г. {CITY}, {address}"

DATA_DIR = GC_ROOT / "gc_data"
INPUT_DATA_FILE = DATA_DIR / "gc_input" / "gc_2gis_input_data.json"
OUTPUT_DATA_FILE = DATA_DIR / "gc_output" / "gc_2gis_output_data.json"

# Загружаем список объектов из JSON-файла
with open(INPUT_DATA_FILE, 'r', encoding='utf-8') as file:
    data = json.load(file)

# Извлекаем массив школ из ключа 'data'
schools = data.get('data', [])

# Ваш ключ API от Яндекс.Карт
API_KEY = os.getenv("YANDEX_API_KEY")

def geocode_address(address):
    """
    Геокодирование адреса через Яндекс.Геокодер.
    Возвращает широту и долготу или None, если объект не найден.
    """
    if not API_KEY:
        raise RuntimeError("YANDEX_API_KEY не найден в .env (корень репозитория или geocoding/)")

    params = {
        "apikey": API_KEY,
        "format": "json",
        "geocode": with_saratov_context(address),
        "results": 1,
        "ll": SARATOV_CENTER,
        "spn": SEARCH_RADIUS,
    }

    response = requests.get(BASE_URL, params=params, timeout=15)
    response.raise_for_status()
    payload = response.json()

    collection = payload["response"]["GeoObjectCollection"]
    found = int(collection["metaDataProperty"]["GeocoderResponseMetaData"]["found"])
    if found < 1 or not collection["featureMember"]:
        return None

    geo_object = collection["featureMember"][0]["GeoObject"]
    lon_str, lat_str = geo_object["Point"]["pos"].split()
    return {"latitude": float(lat_str), "longitude": float(lon_str)}

# Обрабатываем каждую школу и добавляем координаты
for school in schools:
    print(f"Геокодируем школу {school['name']}")
    result = geocode_address(school['adres'])
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