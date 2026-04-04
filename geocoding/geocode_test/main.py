import requests
import json
import time
import os

API_KEY = "824221d0-0da3-4a4f-aa36-9a0d89a33524"

addresses_to_geocode = [
    {"street": "Бахметьевская", "numbers": ["33", "35/37", "39", "49"]},
    {"street": "Белоглинская", "numbers": ["33", "35", "37", "39", "47", "49", "51", "53", "57", "59", "34/38"]},
    {"street": "Вольская", "numbers": ["14", "16", "18"]},
    {"street": "Новоузенская", "numbers": ["11/13", "15/33", "10/20", "22а", "24/32", "42", "44", "46/52"]},
    {"street": "Новоузенский проезд 1-ый", "numbers": ["7/33"]},
    {"street": "Рабочая", "numbers": ["55", "63", "65", "67", "69", "71", "73", "79", "81", "85", "40/60", "62/68"]},
    {"street": "Садовая 2-я", "numbers": ["2", "4", "6"]},
    {"street": "Серова А.К.", "numbers": ["1", "6", "8", "10", "33/37"]},
    {"street": "Симбирцева В.Н.", "numbers": ["12", "14", "16/7", "16/6", "16/8", "16/9", "16/10", "16/11", "16/12", "16/13", "16/15", "16/16", "16/17", "18", "19", "23", "23/37", "24/30", "26/30", "27", "29", "31", "32", "36", "40", "40а", "40б", "42", "44", "49", "51", "53", "55", "57", "59", "63"]},
    {"street": "Телевизионный проезд 1-ый", "numbers": ["3"]},
    {"street": "Телевизионный проезд 2-ой", "numbers": ["3а", "4", "6", "8", "12"]},
    {"street": "Телевизионный проезд 3-ий", "numbers": ["9", "11", "13", "15"]},
    {"street": "Ульяновская", "numbers": ["2", "3", "17", "24", "27/35", "28", "32", "37/41", "40", "40а", "42", "50", "60"]},
    {"street": "им. Н.Г. Чернышевского", "numbers": ["90", "92", "92а", "92б", "94", "97", "99", "101", "103", "105"]},
    {"street": "Шелковичная", "numbers": ["8", "10", "12", "12а", "20/28", "23", "29/35", "32", "32/2", "32/3", "34"]},
]

streets_for_polygons = [
    "Шелковичный тупик 1-ый",
    "Шелковичный тупик 2-ой",
    "Шелковичный тупик 3-ий",
    "Шелковичный тупик 4-ый"
]

BASE_URL = "https://geocode-maps.yandex.ru/1.x/"

# 🎯 Координаты центра Саратова
SARATOV_CENTER = "51.53, 46.00"
# 🎯 БОЛЬШОЙ радиус поиска (примерно весь город)
SEARCH_RADIUS = "1.5, 1.5"  # 1.5 градуса в каждую сторону

print(f"🔍 Начинаем геокодирование {len(addresses_to_geocode)} улиц...")
print(f"📍 Город: Саратов (центр: {SARATOV_CENTER})")
print(f"📍 Радиус поиска: {SEARCH_RADIUS}")
print(f"📁 Текущая папка для сохранения: {os.getcwd()}")
print("-" * 60)

def geocode_address(full_address, use_bbox=True):
    if not API_KEY or API_KEY == "ВАШ_ПОЛНЫЙ_API_КЛЮЧ_ЗДЕСЬ":
        print("❌ ОШИБКА: Укажите ваш API-ключ!")
        return None
    
    params = {
        'format': 'json',
        'geocode': full_address,
        'apikey': API_KEY,
        'results': 1,
    }
    
    # 🎯 Добавляем параметры поиска только если нужно
    if use_bbox:
        params['ll'] = SARATOV_CENTER        # центр поиска
        params['spn'] = SEARCH_RADIUS        # область поиска
        # ❌ НЕ добавляем rspn - это ограничивает поиск только областью!
    
    try:
        response = requests.get(BASE_URL, params=params, timeout=10)
        data = response.json()
        
        found = int(data['response']['GeoObjectCollection']['metaDataProperty']['GeocoderResponseMetaData']['found'])
        if found > 0:
            geo_object = data['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']
            pos = geo_object['Point']['pos']
            lon, lat = map(float, pos.split())
            bounded_by = geo_object.get('boundedBy', {}).get('Envelope', {})
            print(f"   ✅ {full_address[:50]:50} → {lat:.6f}, {lon:.6f}")
            return {
                'lat': lat,
                'lon': lon,
                'bounded_by': bounded_by,
                'address': full_address
            }
        else:
            print(f"   ❌ {full_address[:50]:50} → Не найден")
            return None
    except requests.exceptions.Timeout:
        print(f"   ⏱️  {full_address[:50]:50} → Timeout")
        return None
    except Exception as e:
        print(f"   ❌ {full_address[:50]:50} → Ошибка: {str(e)[:30]}")
        return None

# 1️⃣ Геокодируем адреса домов
full_addresses = []
for item in addresses_to_geocode:
    street = item['street']
    for number in item['numbers']:
        # Попробуем несколько вариантов формата адреса
        full_addr = f"Саратов, ул. {street}, д. {number}"
        full_addresses.append(full_addr)

print(f"\n🏠 Геокодируем {len(full_addresses)} адресов...")

results = []
success_count = 0
failed_addresses = []

for i, addr in enumerate(full_addresses, 1):
    geo_data = geocode_address(addr, use_bbox=True)
    if geo_data:
        results.append(geo_data)
        success_count += 1
    else:
        failed_addresses.append(addr)
    
    if i % 10 == 0:
        print(f"   📊 Прогресс: {i}/{len(full_addresses)} (найдено: {success_count})")
    time.sleep(0.15)

# Сохраняем
with open('geocoded_addresses.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\n💾 Сохранено {len(results)}/{len(full_addresses)} адресов в geocoded_addresses.json")

# Сохраняем список не найденных адресов для отладки
if failed_addresses:
    with open('failed_addresses.txt', 'w', encoding='utf-8') as f:
        for addr in failed_addresses:
            f.write(addr + '\n')
    print(f"⚠️  Не найдено {len(failed_addresses)} адресов (см. failed_addresses.txt)")

# 2️⃣ Геокодируем улицы для полигонов
print(f"\n🗺️  Геокодируем {len(streets_for_polygons)} улиц для полигонов...")

polygon_results = []
for street in streets_for_polygons:
    full_addr = f"Саратов, ул. {street}"
    geo_data = geocode_address(full_addr, use_bbox=True)
    if geo_data and geo_data['bounded_by']:
        try:
            lower_corner = list(map(float, geo_data['bounded_by']['lowerCorner'].split()))
            upper_corner = list(map(float, geo_data['bounded_by']['upperCorner'].split()))
            polygon_coords = [
                [lower_corner[0], lower_corner[1]],
                [upper_corner[0], lower_corner[1]],
                [upper_corner[0], upper_corner[1]],
                [lower_corner[0], upper_corner[1]],
                [lower_corner[0], lower_corner[1]]
            ]
            polygon_results.append({
                'street': street,
                'polygon': polygon_coords
            })
            print(f"   ✅ Полигон для {street}")
        except Exception as e:
            print(f"   ⚠️  Не удалось получить границы для {street}")
    time.sleep(0.15)

with open('street_polygons.json', 'w', encoding='utf-8') as f:
    json.dump(polygon_results, f, ensure_ascii=False, indent=2)
print(f"💾 Сохранены полигоны: {len(polygon_results)} улиц в street_polygons.json")

print("\n🎉 Готово! Файлы сохранены в текущей папке.")