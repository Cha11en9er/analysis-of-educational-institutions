PROMPT_BIG_PATH = 'prompt_big.txt'
PROMPT_SMALL_PATH = 'prompt_small.txt'

# Читаем большой промпт в UTF-8 (иначе Windows по умолчанию берёт cp1251 и падает на некоторых символах)
with open(PROMPT_BIG_PATH, 'r', encoding='utf-8') as file:
    prompt = file.read()

# Делаем одну строку: убираем переводы строк и лишние пробелы по краям
single_line_prompt = ' '.join(prompt.split())

# Записываем результат в файл с маленьким промптом (также в UTF-8)
with open(PROMPT_SMALL_PATH, 'w', encoding='utf-8') as out:
    out.write(single_line_prompt + '\n')

print('Однострочный промпт записан в', PROMPT_SMALL_PATH)