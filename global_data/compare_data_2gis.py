import json
from typing import Dict, Tuple, Any

BASE_PATH = "C:/repos/analysis-of-educational-institutions/global_data/2gis_data"
FILE_MAIN = f"{BASE_PATH}/2gis_all_school_with_info.json"
FILE_CAD = f"{BASE_PATH}/2gis_all_school_with_info_cadastral.json"


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def main() -> None:
    # Загружаем данные
    all_school = load_json(FILE_MAIN)
    all_school_cadastral = load_json(FILE_CAD)

    schools = all_school.get("data", [])
    schools_cad = all_school_cadastral.get("data", [])

    # Индекс по (id, name) -> кадастровый номер
    cad_index: Dict[Tuple[str, str], Any] = {}
    for s in schools_cad:
        cad_num = s.get("cadastral_number")
        if not cad_num:
            continue
        key = (str(s.get("id")), str(s.get("name")))
        cad_index[key] = cad_num

    updated = 0
    not_found = []

    # Проходим по основному списку школ и добавляем cadastral_number
    for school in schools:
        key = (str(school.get("id")), str(school.get("name")))
        cad_num = cad_index.get(key)
        if cad_num:
            if school.get("cadastral_number") != cad_num:
                school["cadastral_number"] = cad_num
                updated += 1
        else:
            not_found.append(key)

    # Сохраняем обновлённый основной файл
    all_school["data"] = schools
    save_json(FILE_MAIN, all_school)

    print(f"Обновлено школ с кадастровыми номерами: {updated}")
    # Если нужно посмотреть, какие не нашли — раскомментировать:
    # for _id, name in not_found:
    #     print("Не найдено в кадастровом файле:", _id, name)


if __name__ == "__main__":
    main()