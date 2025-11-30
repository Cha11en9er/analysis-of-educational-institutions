import folium

# Данные из вашего объекта
school = {
    "id": "1",
    "name": "Средняя школа №83",
    "url": "https://2gis.ru/saratov/firm/70000001037362342",
    "feedback_link": "https://2gis.ru/saratov/firm/70000001037362342/tab/reviews",
    "full_name": "МОУ Средняя общеобразовательная школа №83",
    "adres_part1": "Целинстрой м-н, Заводской район, Саратов, 410039",
    "adres_part2": "Саратов, Крымская улица, 2",
    "adres": "Целинстрой м-н, Заводской район, Саратов, 410039. Саратов, Крымская улица, 2",
    "cadastral_number": "64:48:020331:1356",
    "coordinates": (51.489902, 45.928749),
    "rating": 4.5  # допустим есть рейтинг
}

# Создаем карту, центрируем на координатах школы
map_school = folium.Map(location=school["coordinates"], zoom_start=15)

# Формируем текст всплывающей подсказки (HTML)
popup_html = f"""
<b>{school['name']}</b><br>
Адрес: {school['adres']}<br>
Рейтинг: {school.get("rating", "нет данных")}<br>
<a href="{school['url']}" target="_blank">Страница школы</a><br>
<a href="{school['feedback_link']}" target="_blank">Отзывы</a>
"""

# Добавляем маркер с информацией
folium.Marker(
    location=school["coordinates"],
    popup=folium.Popup(popup_html, max_width=300),
    tooltip=school["name"]  # текст при наведении
).add_to(map_school)

# Сохраняем карту в HTML файл
map_school.save("school_map.html")
print("Карта сохранена в файл school_map.html")