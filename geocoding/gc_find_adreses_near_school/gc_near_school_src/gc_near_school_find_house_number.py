import os
import requests
from dotenv import load_dotenv


load_dotenv()

API_KEY = os.getenv("YANDEX_API_KEY")
BASE_URL = "https://geocode-maps.yandex.ru/1.x/"


def extract_house_number_from_address(address: str) -> str | None:
    """
    Из полной текстовой строки адреса вытаскивает номер дома.
    Пример входа: 'Россия, Саратовская область, Саратов, Заводской район, улица Проточная, 15Б'
    """
    # Разбиваем адрес по запятым и идём с конца, т.к. номер дома обычно последняя или предпоследняя часть
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if not parts:
        return None

    # Ключевые слова, по которым понятно, что это часть названия улицы, а не номер дома
    street_keywords = [
        "улица",
        "ул",
        "проспект",
        "пр-т",
        "проезд",
        "пер",
        "переулок",
        "шоссе",
        "тракт",
        "площадь",
        "пл",
        "бульвар",
        "бул",
        "набережная",
        "наб",
    ]

    # Берём последние 3 фрагмента и ищем там номер
    tail_parts = list(reversed(parts[-3:]))

    for part in tail_parts:
        lower = part.lower()
        if any(kw in lower for kw in street_keywords):
            # Скорее всего это продолжение названия улицы, пропускаем
            continue

        token = part.replace(" ", "")
        # Если в кусочке есть хотя бы одну цифру – считаем, что это номер дома
        has_digit = any(ch.isdigit() for ch in token)
        if has_digit:
            return part

    return None


def get_houses_for_street(street: str, district: str | None = None, city: str = "Саратов", max_results: int = 200) -> list[str]:
    """
    Возвращает список номеров домов для указанной улицы.
    Если указан район, он добавляется в запрос, что повышает точность.
    """
    if not API_KEY:
        raise RuntimeError("YANDEX_API_KEY не найден в окружении (.env)")

    if district:
        query = f"{city}, {district} район, {street}"
    else:
        query = f"{street}, {city}"

    params = {
        "apikey": API_KEY,
        "geocode": query,
        "format": "json",
        "results": max_results,
    }

    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()
    data = response.json()

    members = data.get("response", {}).get("GeoObjectCollection", {}).get("featureMember", [])
    houses: set[str] = set()

    for item in members:
        meta = (
            item
            .get("GeoObject", {})
            .get("metaDataProperty", {})
            .get("GeocoderMetaData", {})
        )
        text = meta.get("text")
        if not text:
            continue

        house = extract_house_number_from_address(text)
        if house:
            houses.add(house)

    return sorted(houses)


def get_points_for_street(street: str, district: str | None = None, city: str = "Саратов", max_results: int = 200) -> list[dict]:
    """
    Возвращает список объектов с полным адресом и координатами для указанной улицы.
    Это более "сырой" вариант, где можно взять либо номера домов из текста, либо просто координаты.
    Формат элемента списка:
    {
        "address": "<полный адрес из GeocoderMetaData.text>",
        "latitude": <float>,
        "longitude": <float>,
    }
    """
    if not API_KEY:
        raise RuntimeError("YANDEX_API_KEY не найден в окружении (.env)")

    def _request(query: str) -> list[dict]:
        params = {
            "apikey": API_KEY,
            "geocode": query,
            "format": "json",
            "results": max_results,
        }
        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("response", {}).get("GeoObjectCollection", {}).get("featureMember", [])

    # 1) Пробуем с районом
    members: list[dict] = []
    if district:
        query = f"{city}, {district} район, {street}"
        members = _request(query)

    # 2) Если ничего не нашли или район не задан — пробуем без района
    if not members:
        query = f"{street}, {city}"
        members = _request(query)

    points: list[dict] = []
    for item in members:
        geo = item.get("GeoObject", {})
        pos = geo.get("Point", {}).get("pos")
        if not pos:
            continue
        try:
            lon_str, lat_str = pos.split()
            latitude = float(lat_str)
            longitude = float(lon_str)
        except Exception:
            continue

        meta = (
            geo
            .get("metaDataProperty", {})
            .get("GeocoderMetaData", {})
        )
        text = meta.get("text", "")

        points.append(
            {
                "address": text,
                "latitude": latitude,
                "longitude": longitude,
            }
        )

    return points


def main():
    """
    Отладочный запуск для одной строки из ans_stage1_adres_near_school.csv:
    Кировский;МАОУ «Гимназия №31»;Выселочная;все дома

    Задача: получить полный список найденных адресов и их координаты
    по улице Выселочная в Кировском районе г. Саратова.
    """
    district = "Кировский"
    street = "Выселочная"

    print(f"Район: {district}")
    print(f"Улица: {street}")
    print("\n==============================")

    try:
        points = get_points_for_street(street=street, district=district)
    except Exception as e:
        print(f"Ошибка при запросе к геокодеру: {e}")
        return

    if not points:
        print("Не найдено ни одного объекта (ни домов, ни координат).")
        return

    print(f"Найдено объектов: {len(points)}")
    print("Список адресов и координат:")
    for i, p in enumerate(points, start=1):
        print(f"{i}. {p['address']} -> ({p['latitude']}, {p['longitude']})")


if __name__ == "__main__":
    main()


