import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SOURCE_FILE = BASE_DIR.parent / "2gis" / "2gis_data" / "tgis_output" / "2gis_all_school_with_info.json"
CADASTRAL_FILE = BASE_DIR.parent / "find_cadastral_number" / "fcn_data" / "fcn_output" / "find_cadastral_number_data_output.json"
TARGET_FILE = BASE_DIR / "vam_data" / "vam_data_input" / "vam_2gis_input_data.json"


def read_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_cadastral_map():
    if not CADASTRAL_FILE.exists():
        return {}

    cad_data = read_json(CADASTRAL_FILE)
    cad_list = cad_data.get("data", cad_data)

    return {
        item.get("id"): item.get("cadastral_number")
        for item in cad_list
        if isinstance(item, dict)
    }


def prepare_record(school: dict, cadastral_map: dict):
    adres = school.get("adres_part2") or school.get("adres") or school.get("adres_part1")

    return {
        "id": school.get("id"),
        "name": school.get("name"),
        "url": school.get("url"),
        "feedback_link": school.get("feedback_link"),
        "full_name": school.get("full_name"),
        "adres": adres,
        "cadastral_number": cadastral_map.get(school.get("id")),
    }


def main():
    if not SOURCE_FILE.exists():
        raise FileNotFoundError(f"Не найден файл с данными 2ГИС: {SOURCE_FILE}")

    source_data = read_json(SOURCE_FILE)
    schools = source_data.get("data", source_data)

    cadastral_map = build_cadastral_map()

    prepared = [prepare_record(school, cadastral_map) for school in schools if isinstance(school, dict)]

    output = {
        "source": "2GIS",
        "topic": "Школы Саратова",
        "total_elements": len(prepared),
        "data": prepared,
    }

    TARGET_FILE.parent.mkdir(parents=True, exist_ok=True)
    with TARGET_FILE.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=4)

    print(f"✅ Подготовлено записей: {len(prepared)}")
    print(f"📄 Результат сохранён в: {TARGET_FILE}")


if __name__ == "__main__":
    main()
