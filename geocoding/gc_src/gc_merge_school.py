import json
from pathlib import Path
from typing import Any, Dict, List


BASE_DIR = Path(__file__).resolve().parents[1] / "gc_data" / "gc_output"
FILE_2GIS = BASE_DIR / "gc_2gis_output_data.json"
FILE_YM = BASE_DIR / "gc_ym_output_data.json"
FILE_OUT = BASE_DIR / "gc_merge_data.json"


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def build_2gis_index(items: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Индекс по координатам для 2GIS: coordinates -> список объектов.
    Используем список, чтобы можно было корректно обрабатывать случаи с несколькими школами
    на одних координатах (по одной выдаём при совпадении).
    """
    index: Dict[str, List[Dict[str, Any]]] = {}
    for obj in items:
        coords = obj.get("coordinates")
        if not coords:
            continue
        index.setdefault(coords, []).append(obj)
    return index


def pop_match(index: Dict[str, List[Dict[str, Any]]], coords: str) -> Dict[str, Any] | None:
    """
    Берём одну подходящую запись из индекса по координатам и удаляем её из индекса.
    """
    lst = index.get(coords)
    if not lst:
        return None
    obj = lst.pop(0)
    if not lst:
        index.pop(coords, None)
    return obj


def main() -> None:
    ym_data = load_json(FILE_YM)
    gis_data = load_json(FILE_2GIS)

    ym_items: List[Dict[str, Any]] = ym_data.get("data", [])
    gis_items: List[Dict[str, Any]] = gis_data.get("data", [])

    gis_index = build_2gis_index(gis_items)

    merged_items: List[Dict[str, Any]] = []
    running_id = 1

    # 1. Проходим по основному (Яндекс) списку
    for ym_obj in ym_items:
        coords = ym_obj.get("coordinates")
        matched_gis = pop_match(gis_index, coords) if coords else None

        if matched_gis:
            # Случай: есть в основном и в 2GIS — делаем слитую запись
            merged_obj = {
                "id": str(running_id),  # сплошная нумерация только для слитых записей
                "yandex_name": ym_obj.get("name"),
                "2gis_full_name": matched_gis.get("full_name"),
                "2gis_url": matched_gis.get("url"),
                "2gis_review_url": matched_gis.get("feedback_link"),
                "ym_url": ym_obj.get("url"),
                "ym_review_url": ym_obj.get("feedback_link"),
                "ym_adres": ym_obj.get("adres"),
                "cadastral_number": matched_gis.get("cadastral_number"),
                "geocoords": matched_gis.get("coordinates") or ym_obj.get("coordinates"),
            }
            merged_items.append(merged_obj)
            running_id += 1
        else:
            # Случай: есть только в основном — оставляем объект как есть
            merged_items.append(ym_obj)

    # 2. Оставшиеся в индексе 2GIS объекты — есть только в косвенном, добавляем как есть
    for remaining_list in gis_index.values():
        for obj in remaining_list:
            merged_items.append(obj)

    out = {
        "source": "merge_2gis_yandex",
        "topic": ym_data.get("topic") or gis_data.get("topic"),
        "total_elements": len(merged_items),
        "data": merged_items,
    }

    save_json(FILE_OUT, out)
    print(f"Сформирован файл слияния: {FILE_OUT}")
    print(f"Всего записей: {len(merged_items)}")


if __name__ == "__main__":
    main()
