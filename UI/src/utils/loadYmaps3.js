/**
 * Загрузка Yandex Maps JS API v3 один раз на страницу.
 * Ключ: REACT_APP_YANDEX_MAPS_API_KEY (сборка CRA).
 */

let loadPromise = null;

export function getYandexMapsApiKey() {
  return (process.env.REACT_APP_YANDEX_MAPS_API_KEY || '').trim();
}

export function loadYmaps3(apiKey) {
  if (typeof window === 'undefined') {
    return Promise.reject(new Error('ymaps3 только в браузере'));
  }
  if (window.ymaps3) {
    return window.ymaps3.ready.then(() => window.ymaps3);
  }
  if (loadPromise) return loadPromise;

  const key = (apiKey || getYandexMapsApiKey()).trim();
  if (!key) {
    return Promise.reject(new Error('Не задан REACT_APP_YANDEX_MAPS_API_KEY'));
  }

  loadPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector('script[data-ymaps3]');
    if (existing) {
      existing.addEventListener('load', () => {
        window.ymaps3.ready.then(() => resolve(window.ymaps3)).catch(reject);
      });
      existing.addEventListener('error', () => reject(new Error('Не удалось загрузить Yandex Maps API')));
      return;
    }

    const script = document.createElement('script');
    script.src = `https://api-maps.yandex.ru/v3/?apikey=${encodeURIComponent(key)}&lang=ru_RU`;
    script.async = true;
    script.dataset.ymaps3 = '1';
    script.onload = () => {
      window.ymaps3.ready.then(() => resolve(window.ymaps3)).catch(reject);
    };
    script.onerror = () => reject(new Error('Не удалось загрузить Yandex Maps API'));
    document.head.appendChild(script);
  });

  return loadPromise;
}
