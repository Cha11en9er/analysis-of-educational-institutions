/**
 * Загрузка Yandex Maps JS API v3.
 *
 * Ключ (по приоритету):
 * 1) REACT_APP_YANDEX_API_KEY / REACT_APP_YANDEX_MAPS_API_KEY (сборка CRA)
 * 2) GET /api/config → yandex_api_key из корневого .env (YANDEX_API_KEY на сервере)
 */

let loadPromise = null;
let resolvedKeyPromise = null;

function keyFromBuildEnv() {
  return (
    process.env.REACT_APP_YANDEX_API_KEY ||
    process.env.REACT_APP_YANDEX_MAPS_API_KEY ||
    ''
  ).trim();
}

async function resolveApiKey(explicit) {
  if (explicit && String(explicit).trim()) {
    return String(explicit).trim();
  }
  const fromEnv = keyFromBuildEnv();
  if (fromEnv) return fromEnv;

  if (!resolvedKeyPromise) {
    const base =
      process.env.REACT_APP_API_URL !== undefined
        ? process.env.REACT_APP_API_URL
        : '';
    resolvedKeyPromise = fetch(`${base}/api/config`)
      .then((r) => (r.ok ? r.json() : {}))
      .then((data) => (data && data.yandex_api_key ? String(data.yandex_api_key).trim() : ''))
      .catch(() => '');
  }
  return resolvedKeyPromise;
}

export function getYandexMapsApiKey() {
  return keyFromBuildEnv();
}

export function loadYmaps3(apiKey) {
  if (typeof window === 'undefined') {
    return Promise.reject(new Error('ymaps3 только в браузере'));
  }
  if (window.ymaps3) {
    return window.ymaps3.ready.then(() => window.ymaps3);
  }
  if (loadPromise) return loadPromise;

  loadPromise = (async () => {
    const key = await resolveApiKey(apiKey);
    if (!key) {
      throw new Error(
        'Не задан YANDEX_API_KEY (в /opt/uchgrad/.env) или REACT_APP_YANDEX_API_KEY'
      );
    }

    if (!window.ymaps3) {
      await new Promise((resolve, reject) => {
        const existing = document.querySelector('script[data-ymaps3]');
        if (existing) {
          existing.addEventListener('load', () => resolve());
          existing.addEventListener('error', () =>
            reject(new Error('Не удалось загрузить Yandex Maps API'))
          );
          return;
        }
        const script = document.createElement('script');
        script.src = `https://api-maps.yandex.ru/v3/?apikey=${encodeURIComponent(key)}&lang=ru_RU`;
        script.async = true;
        script.dataset.ymaps3 = '1';
        script.onload = () => resolve();
        script.onerror = () => reject(new Error('Не удалось загрузить Yandex Maps API'));
        document.head.appendChild(script);
      });
    }

    await window.ymaps3.ready;
    return window.ymaps3;
  })();

  return loadPromise;
}
