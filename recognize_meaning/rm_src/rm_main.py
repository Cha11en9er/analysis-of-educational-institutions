from dotenv import load_dotenv
from gigachat import GigaChat
import os
import json
import re

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
RM_ROOT = os.path.dirname(CURRENT_DIR)
DATA_DIR = os.path.join(RM_ROOT, 'rm_data')
INPUT_DIR = os.path.join(DATA_DIR, 'rm_input')
OUTPUT_DIR = os.path.join(DATA_DIR, 'rm_output')
INPUT_REVIEW_FILE = os.path.join(INPUT_DIR, 'rm_input_data.json')
OUTPUT_REVIEW_FILE = os.path.join(OUTPUT_DIR, 'rm_output_data.json')

def recognize_review(review_text, auth_key):
    # Формирование подробного prompt'а с примерами структуры вывода
    prompt_template = f"""
    Анализ отзыва об образовательном учреждение:
    ---
    Отзыв: {review_text}

    Задача: Выделите основную мысль отзыва в 5-10 словах и оцените отзыв как положительный или отрицательный. Результат должен быть представлен в следующем формате JSON:
    {{    \\"main_idea\\": \\"\\",    \\"sentiment\\": \\"\\"}}

    Примеры:
    текст отзыва - "Прекрасное место, прекрасные воспитатели, педагоги и не только. Ребенок ходит с удовольствием. Болеем редко))) Сын счастлив."
    Ожидаемый результат - {{\\"main_idea\\": \\"прекрасные педагоги. прекрасное место для детей\\", \\"sentiment\\": \\"положительный\\"}}

    текст отзыва - "У этой школы есть хорошие традиции. В том числе традиционно сильный коллектив учителей, которые сами учились в этой школе."
    Ожидаемый результат - {{\\"main_idea\\": \\"хорошие традиции. сильный коллектив учителей\\", \\"sentiment\\": \\"положительный\\"}}

    текст отзыва - "Сильные преподаватели, хорошая школа, но требует современного ремонта"
    Ожидаемый результат - {{\\"main_idea\\": \\"сильные преподаватели. требуется современный ремонт\\", \\"sentiment\\": \\"положительный\\"}}

    текст отзыва - "самое лучшее что тут можно найти это Владимир Степанович - самый лучший учитель физики и Анна Сергеевна - самая лучшая учительница русского языка и литературы . Еще Елена Викторовна классная . общая оценка заведения - 2 звезды . кроме вышеперечисленных личностей ловить тут конечно нечего ."
    Ожидаемый результат - {{\\"main_idea\\": \\"Владимир Степанович - лучший учитель физики. Анна Сергеевна - лучшая учительница русского языка и литературы. Еще Елена Викторовна классная. в остальном 2 звезды\\", \\"sentiment\\": \\"отрицательный\\"}}

    текст отзыва - "В столовой кормят отвратительно. В раздевалке могут украсть всё что угодно. За этим следит \\"старушка божий одуванчик\\" который лет сто."
    Ожидаемый результат - {{\\"main_idea\\": \\"кормят отвратительно. могут украсть всё что угодно\\", \\"sentiment\\": \\"отрицательный\\"}}

    текст отзыва - "Школа нормальная,но убедительная просьба к адменистрации провести беседу с охраной на тему уважения к родителям учащихся!С нас требуют чтобы мы оплачивали так называемую охрану,от которой пышет хамство,и не умение контролировать свой рот!И мне кажется что ничего страшного не случится если родитель шагнет за порог школы,что бы помочь своему ребенку!"
    Ожидаемый результат - {{\\"main_idea\\": \\"школа нормальная. охрана пышет хамством. нужно провести беседу с охраной\\", \\"sentiment\\": \\"отрицательный\\"}}
    """

    with GigaChat(credentials=auth_key, verify_ssl_certs=False) as giga:
        # Отправляем сформированный запрос и получаем ответ
        response = giga.chat(prompt_template)
        # Извлекаем содержимое первого выбора ответа
        output_json = response.choices[0].message.content.strip('`')
        # Убираем markdown код блоки, если есть
        if output_json.startswith('json'):
            output_json = output_json[4:].strip()
        if output_json.startswith('```'):
            output_json = output_json[3:].strip()
        if output_json.endswith('```'):
            output_json = output_json[:-3].strip()

    return output_json

def parse_ai_response(ai_output: str) -> dict:
    """Парсит JSON ответ от AI и извлекает main_idea и sentiment"""
    try:
        # Пытаемся распарсить JSON
        result = json.loads(ai_output)
        return {
            'main_idea': result.get('main_idea', ''),
            'sentiment': result.get('sentiment', '')
        }
    except json.JSONDecodeError as e:
        print(f"[WARN] Ошибка парсинга JSON ответа: {e}")
        print(f"[DEBUG] Ответ AI: {ai_output}")
        # Пытаемся извлечь данные вручную через regex
        main_idea_match = re.search(r'"main_idea"\s*:\s*"([^"]*)"', ai_output)
        sentiment_match = re.search(r'"sentiment"\s*:\s*"([^"]*)"', ai_output)
        return {
            'main_idea': main_idea_match.group(1) if main_idea_match else '',
            'sentiment': sentiment_match.group(1) if sentiment_match else ''
        }


def highlight_review(input_file_path, output_file_path, auth_key):
    """Обрабатывает отзывы и сохраняет результаты в выходной файл"""
    # Читаем входной файл
    with open(input_file_path, "r", encoding='utf-8') as f:
        input_data = json.load(f)
    
    # Сохраняем метаданные из входного файла
    output_data = {
        'resource': input_data.get('resource', ''),
        'parse_date': input_data.get('parse_date', ''),
        'reviews': []
    }
    
    # Обрабатываем каждый отзыв
    reviews = input_data.get('reviews', [])
    total_reviews = len(reviews)
    
    print(f"[INFO] Найдено отзывов для обработки: {total_reviews}")
    
    for idx, review_info in enumerate(reviews, 1):
        review_text = review_info.get('text', '')
        
        if not review_text:
            print(f"[WARN] Отзыв {idx}/{total_reviews}: пропущен (нет текста)")
            # Добавляем отзыв без анализа
            output_review = review_info.copy()
            output_review['main_idea'] = ''
            output_review['sentiment'] = ''
            output_data['reviews'].append(output_review)
            continue
        
        print(f"[INFO] Обработка отзыва {idx}/{total_reviews} (school_id: {review_info.get('school_id', 'unknown')})")
        
        try:
            # Получаем анализ от AI
            ai_response = recognize_review(review_text, auth_key)
            # Парсим ответ
            analysis = parse_ai_response(ai_response)
            
            # Создаём выходной отзыв с добавленными полями
            output_review = review_info.copy()
            output_review['main_idea'] = analysis['main_idea']
            output_review['sentiment'] = analysis['sentiment']
            
            output_data['reviews'].append(output_review)
            
            print(f"[OK] Отзыв {idx}/{total_reviews} обработан: sentiment={analysis['sentiment']}")
            
        except Exception as e:
            print(f"[ERROR] Ошибка при обработке отзыва {idx}/{total_reviews}: {e}")
            # Добавляем отзыв без анализа в случае ошибки
            output_review = review_info.copy()
            output_review['main_idea'] = ''
            output_review['sentiment'] = ''
            output_data['reviews'].append(output_review)
    
    # Сохраняем результат в выходной файл
    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
    with open(output_file_path, "w", encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
    
    print(f"[OK] Результаты сохранены в: {output_file_path}")
    print(f"[OK] Всего обработано отзывов: {len(output_data['reviews'])}")


# Загрузка переменных окружения из .env файла
load_dotenv()

# Получение ключа аутентификации из переменных среды
auth_key = os.getenv("AUTH_KEY")

if __name__ == "__main__":
    highlight_review(INPUT_REVIEW_FILE, OUTPUT_REVIEW_FILE, auth_key)