"""
Скрипт для очистки кеша модели transformers.
Используйте этот скрипт, если модель загружается слишком быстро 
или использует старую версию (tiny вместо base).
"""

import os
import shutil
from pathlib import Path

def clear_transformers_cache():
    """Очищает кеш моделей transformers"""
    
    # Пути к кешу transformers (зависит от ОС)
    cache_paths = []
    
    # Windows
    if os.name == 'nt':
        cache_dir = os.path.join(os.environ.get('USERPROFILE', ''), '.cache', 'huggingface')
        cache_paths.append(cache_dir)
    
    # Linux/Mac
    else:
        cache_dir = os.path.join(os.path.expanduser('~'), '.cache', 'huggingface')
        cache_paths.append(cache_dir)
    
    # Также проверяем переменную окружения
    if 'HF_HOME' in os.environ:
        cache_paths.append(os.path.join(os.environ['HF_HOME'], 'hub'))
    
    if 'TRANSFORMERS_CACHE' in os.environ:
        cache_paths.append(os.environ['TRANSFORMERS_CACHE'])
    
    print("=" * 80)
    print("ОЧИСТКА КЕША МОДЕЛЕЙ TRANSFORMERS")
    print("=" * 80)
    
    cleared = False
    for cache_path in cache_paths:
        if os.path.exists(cache_path):
            print(f"\n[INFO] Найден кеш: {cache_path}")
            
            # Ищем модели cointegrated
            model_dirs = []
            for root, dirs, files in os.walk(cache_path):
                if 'cointegrated' in root:
                    model_dirs.append(root)
            
            if model_dirs:
                print(f"[INFO] Найдено моделей cointegrated: {len(model_dirs)}")
                for model_dir in model_dirs:
                    print(f"  - {model_dir}")
                    try:
                        # Удаляем директорию модели
                        shutil.rmtree(model_dir)
                        print(f"  [OK] Удалено: {model_dir}")
                        cleared = True
                    except Exception as e:
                        print(f"  [ERROR] Не удалось удалить {model_dir}: {e}")
            else:
                print("[INFO] Модели cointegrated не найдены в кеше")
        else:
            print(f"[INFO] Кеш не найден: {cache_path}")
    
    if cleared:
        print("\n[OK] Кеш очищен! При следующем запуске модель загрузится заново.")
    else:
        print("\n[INFO] Кеш не найден или уже пуст.")
    
    print("=" * 80)
    print("\nДля принудительной перезагрузки модели используйте:")
    print("  python rm_main_ai.py --reload")
    print("=" * 80)

if __name__ == "__main__":
    clear_transformers_cache()

