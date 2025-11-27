import json
import os
from pathlib import Path

def process_raw_data():
    """Обрабатывает все файлы из raw_data и создает итоговый файл"""
    
    # Пути к файлам и папкам
    raw_data_dir = Path(__file__).parent / "raw_data"
    output_file = Path(__file__).parent / "2gis_all_school.json"
    
    # Список для хранения всех школ
    all_schools = []
    
    # Получаем все JSON файлы из папки raw_data и сортируем их
    json_files = sorted(raw_data_dir.glob("page_*.json"))
    
    # Проходим по каждому файлу
    for json_file in json_files:
        print(f"Обработка файла: {json_file.name}")
        
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Извлекаем массив data из файла
        if 'data' in data and isinstance(data['data'], list):
            for school in data['data']:
                # Проверяем наличие необходимых полей
                if 'name' in school and 'url' in school:
                    # Обрезаем URL до первого знака ?
                    url = school['url']
                    if '?' in url:
                        url = url.split('?')[0]
                    
                    # Создаем feedback_link
                    feedback_link = url + "/tab/reviews"
                    
                    # Добавляем школу в список (id будет добавлен позже)
                    all_schools.append({
                        'name': school['name'],
                        'url': url,
                        'feedback_link': feedback_link
                    })
    
    # Добавляем id к каждому элементу, начиная с 1, и переупорядочиваем поля
    for idx, school in enumerate(all_schools, start=1):
        # Переупорядочиваем поля: id первым, затем name, url, feedback_link
        school_data = {
            'id': str(idx),
            'name': school['name'],
            'url': school['url'],
            'feedback_link': school['feedback_link']
        }
        all_schools[idx - 1] = school_data
    
    # Создаем итоговую структуру
    result = {
        "source": "2GIS",
        "topic": "Школы Саратова",
        "total_elements": len(all_schools),
        "data": all_schools
    }
    
    # Сохраняем результат в файл
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
    
    print(f"\nОбработка завершена!")
    print(f"Всего обработано школ: {len(all_schools)}")
    print(f"Результат сохранен в: {output_file}")

if __name__ == "__main__":
    process_raw_data()

