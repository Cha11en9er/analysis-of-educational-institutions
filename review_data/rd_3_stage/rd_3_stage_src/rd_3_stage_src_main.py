import json
import os
import re

# Укажите пути до папок с файлами
REVIEWS_FOLDER = 'C:/repos/analysis-of-educational-institutions/review_data/rd_2_stage/rd_separately'  
ANALYZE_FOLDER = 'C:/repos/analysis-of-educational-institutions/review_data/rd_2_stage_analys/rd_separately_analyzed' 

def read_json_objects(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        if content.startswith('[') and content.endswith(']'):
            return json.loads(content)

        # Для объектов без массива — парсим через regex
        objects = []
        depth = 0
        start = -1
        for i, char in enumerate(content):
            if char == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0 and start != -1:
                    obj_str = content[start:i+1].strip()
                    if obj_str:
                        try:
                            obj = json.loads(obj_str)
                            objects.append(obj)
                        except json.JSONDecodeError:
                            print(f"⚠️  Пропущен некорректный объект в {filepath} около позиции {start}-{i}")
        return objects
    except Exception as e:
        print(f"❌ Ошибка при чтении {filepath}: {e}")
        return []

def merge_by_review_id(reviews, analysis):
    analysis_map = {}
    for item in analysis:
        rid = item.get("review_id")
        if rid is not None:
            analysis_map[str(rid)] = {
                "topics": item.get("topics", {}),
                "overall": item.get("overall")
            }

    merged = []
    for rev in reviews:
        rid = str(rev.get("review_id"))
        merged_item = rev.copy()
        if rid in analysis_map:
            ana = analysis_map[rid]
            merged_item["topics"] = ana["topics"]
            merged_item["overall"] = ana["overall"]
        merged.append(merged_item)
    return merged

def find_files_in_folder(folder, pattern):
    """Ищет файлы по шаблону внутри указанной папки"""
    files_found = {}
    regex = re.compile(pattern)
    for filename in os.listdir(folder):
        match = regex.match(filename)
        if match:
            files_found[int(match.group(1))] = filename
    return files_found

def main():
    # Паттерны для поиска файлов
    review_pattern = r'school_reviews_separately_(\d+)\.json'
    analyz_pattern = r'school_reviews_separately_(\d+)_analyz\.json'

    # Находим файлы в папках
    review_files = find_files_in_folder(REVIEWS_FOLDER, review_pattern)
    analyz_files = find_files_in_folder(ANALYZE_FOLDER, analyz_pattern)

    # Находим номера N, у которых есть оба файла
    common_n = sorted(set(review_files.keys()) & set(analyz_files.keys()))

    if not common_n:
        print("❌ Не найдено подходящих пар файлов с анализом.")
        return

    print(f"🔍 Найдено пар файлов с анализом для {len(common_n)} N: {common_n}")

    for n in common_n:
        reviews_path = os.path.join(REVIEWS_FOLDER, review_files[n])
        analyz_path = os.path.join(ANALYZE_FOLDER, analyz_files[n])
        output_path = f"C:/repos/analysis-of-educational-institutions/review_data/rd_3_stage/rd_3_stage_data/school_review_separately_{n}_final.json"

        print(f"✅ Обрабатываем N={n}: {reviews_path} + {analyz_path}")

        reviews = read_json_objects(reviews_path)
        analysis = read_json_objects(analyz_path)

        merged = merge_by_review_id(reviews, analysis)

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(merged, f, ensure_ascii=False, indent=2)
            print(f"✅ Сохранено: {output_path} ({len(merged)} отзывов)")
        except Exception as e:
            print(f"❌ Ошибка записи {output_path}: {e}")

if __name__ == "__main__":
    main()