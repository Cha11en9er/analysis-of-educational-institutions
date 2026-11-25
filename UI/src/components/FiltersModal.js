import React, { useState, useEffect, useCallback } from 'react';

const PREFS = [
  { key: 'olympiads', label: 'Олимпиадная активность' },
  { key: 'bullying', label: 'Отношение к ребёнку (климат, буллинг)' },
  { key: 'staff', label: 'Поведение учителей и администрации' },
  { key: 'building', label: 'Ремонт и характеристики школы' },
  { key: 'exam', label: 'Обучение и сдача ЕГЭ' },
  { key: 'location', label: 'Близость расположения' },
];

const SPORTS_OPTIONS = [
  { key: 'has_stadium', label: 'Футбольное поле' },
  { key: 'has_pool', label: 'Бассейн' },
  { key: 'has_sports_ground', label: 'Спорт площадка' },
  { key: 'has_sports_complex', label: 'Спорткомплекс' },
];

const defaultPrefs = {
  olympiads: false,
  bullying: false,
  staff: false,
  building: false,
  exam: false,
  location: false,
  userLat: null,
  userLon: null,
};

const defaultFilters = {
  yearMin: null,
  yearMax: null,
  ratingMin: null,
  ratingMax: null,
  sports: {},
};

/**
 * Единая модалка фильтров: «Что вам важно в школе?» (подбор) и параметры
 * списка школ (год постройки, итоговый рейтинг, спортобъекты).
 * Заменяет отдельную модалку предпочтений и свёрнутые фильтры в сайдбаре.
 */
export default function FiltersModal({
  open,
  onClose,
  onApply,
  initialFilters,
  initialPrefs,
  loading,
  onToast,
}) {
  const [filters, setFilters] = useState(() => ({ ...defaultFilters, ...initialFilters }));
  const [prefs, setPrefs] = useState(() => ({ ...defaultPrefs, ...initialPrefs }));

  useEffect(() => {
    if (open) {
      setFilters({ ...defaultFilters, sports: {}, ...initialFilters });
      setPrefs({ ...defaultPrefs, ...initialPrefs });
    }
  }, [open, initialFilters, initialPrefs]);

  const togglePref = useCallback((key) => {
    setPrefs((f) => ({ ...f, [key]: !f[key] }));
  }, []);

  const toggleSport = useCallback((key) => {
    setFilters((f) => ({
      ...f,
      sports: { ...(f.sports || {}), [key]: !(f.sports || {})[key] },
    }));
  }, []);

  const requestGeo = useCallback(() => {
    if (!navigator.geolocation) {
      onToast?.({ message: 'Геолокация недоступна в браузере', type: 'error' });
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setPrefs((f) => ({
          ...f,
          location: true,
          userLat: pos.coords.latitude,
          userLon: pos.coords.longitude,
        }));
        onToast?.({ message: 'Координаты сохранены для расчёта близости', type: 'info' });
      },
      () => {
        onToast?.({ message: 'Не удалось получить координаты. Разрешите доступ или отключите «Близость».', type: 'error' });
      },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 }
    );
  }, [onToast]);

  const handleApply = useCallback(() => {
    onApply(filters, prefs);
  }, [filters, prefs, onApply]);

  const handleResetAll = useCallback(() => {
    setFilters({ ...defaultFilters, sports: {} });
    setPrefs({ ...defaultPrefs });
    onApply({ ...defaultFilters, sports: {} }, { ...defaultPrefs });
  }, [onApply]);

  if (!open) return null;

  return (
    <div className="fm-backdrop" onClick={onClose}>
      <div className="fm-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Фильтры и подбор школы">
        <div className="fm-head">
          <span className="fm-title">Фильтры и подбор школы</span>
          <button type="button" className="fm-close" onClick={onClose} aria-label="Закрыть">✕</button>
        </div>

        <div className="fm-body">
          <section className="fm-section">
            <h4 className="fm-section-title">Что вам важно в школе?</h4>
            <p className="fm-hint">Отметьте пункты — школы на карте и в списке отсортируются по вашему приоритету.</p>
            <div className="fm-checks">
              {PREFS.map(({ key, label }) => (
                <label key={key} className={`fm-check ${prefs[key] ? 'on' : ''}`}>
                  <input type="checkbox" checked={!!prefs[key]} onChange={() => togglePref(key)} />
                  <span>{label}</span>
                </label>
              ))}
            </div>
            {prefs.location && (
              <div className="fm-geo-row">
                {prefs.userLat != null && prefs.userLon != null ? (
                  <span className="fm-geo-ok">Местоположение сохранено</span>
                ) : (
                  <button type="button" className="fm-geo-btn" onClick={requestGeo}>Моё местоположение</button>
                )}
              </div>
            )}
          </section>

          <section className="fm-section">
            <h4 className="fm-section-title">Параметры школ</h4>

            <div className="fm-field">
              <span className="fm-label">Год постройки</span>
              <div className="fm-range">
                <input
                  type="number" min={1800} max={2100} placeholder="от"
                  value={filters.yearMin ?? ''}
                  onChange={(e) => setFilters((f) => ({ ...f, yearMin: e.target.value.trim() || null }))}
                />
                <input
                  type="number" min={1800} max={2100} placeholder="до"
                  value={filters.yearMax ?? ''}
                  onChange={(e) => setFilters((f) => ({ ...f, yearMax: e.target.value.trim() || null }))}
                />
              </div>
            </div>

            <div className="fm-field">
              <span className="fm-label">Итоговый рейтинг (0–110 баллов)</span>
              <div className="fm-range">
                <input
                  type="number" min={0} max={110} step={0.1} placeholder="от"
                  value={filters.ratingMin ?? ''}
                  onChange={(e) => setFilters((f) => ({ ...f, ratingMin: e.target.value.trim() || null }))}
                />
                <input
                  type="number" min={0} max={110} step={0.1} placeholder="до"
                  value={filters.ratingMax ?? ''}
                  onChange={(e) => setFilters((f) => ({ ...f, ratingMax: e.target.value.trim() || null }))}
                />
              </div>
            </div>

            <div className="fm-field">
              <span className="fm-label">Спортобъекты</span>
              <div className="fm-checks">
                {SPORTS_OPTIONS.map(({ key, label }) => (
                  <label key={key} className={`fm-check ${(filters.sports || {})[key] ? 'on' : ''}`}>
                    <input
                      type="checkbox"
                      checked={!!(filters.sports || {})[key]}
                      onChange={() => toggleSport(key)}
                    />
                    <span>{label}</span>
                  </label>
                ))}
              </div>
            </div>
          </section>
        </div>

        <div className="fm-actions">
          <button type="button" className="fm-btn fm-btn-ghost" onClick={handleResetAll}>
            Сбросить всё
          </button>
          <button type="button" className="fm-btn fm-btn-primary" onClick={handleApply} disabled={loading}>
            {loading ? 'Загрузка…' : 'Применить'}
          </button>
        </div>
      </div>
    </div>
  );
}
