import React, { useState, useEffect, useCallback } from 'react';

const PREFS = [
  { key: 'olympiads', label: 'Олимпиадная активность' },
  { key: 'bullying', label: 'Отношение к ребёнку (климат, буллинг)' },
  { key: 'staff', label: 'Поведение учителей и администрации' },
  { key: 'building', label: 'Ремонт и характеристики школы' },
  { key: 'exam', label: 'Обучение и сдача ЕГЭ' },
  { key: 'location', label: 'Близость расположения' },
];

const defaultForm = {
  olympiads: false,
  bullying: false,
  staff: false,
  building: false,
  exam: false,
  location: false,
  userLat: null,
  userLon: null,
};

export default function PreferenceModal({
  open,
  onBackdropClose,
  onSkipWithoutPrefs,
  onApply,
  initialForm,
  loading,
  onToast,
}) {
  const [form, setForm] = useState(() => ({ ...defaultForm, ...initialForm }));

  useEffect(() => {
    if (open) setForm({ ...defaultForm, ...initialForm });
  }, [open, initialForm]);

  const toggle = useCallback((key) => {
    setForm((f) => ({ ...f, [key]: !f[key] }));
  }, []);

  const anySelected = PREFS.some(({ key }) => form[key]);

  const requestGeo = useCallback(() => {
    if (!navigator.geolocation) {
      onToast?.({ message: 'Геолокация недоступна в браузере', type: 'error' });
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setForm((f) => ({
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
    if (!anySelected) {
      onToast?.({ message: 'Отметьте хотя бы один пункт или нажмите «Просто смотреть карту»', type: 'error' });
      return;
    }
    if (form.location && (form.userLat == null || form.userLon == null)) {
      onToast?.({ message: 'Для «Близости» нажмите «Моё местоположение» или снимите галочку', type: 'error' });
      return;
    }
    onApply(form);
  }, [anySelected, form, onApply, onToast]);

  if (!open) return null;

  return (
    <div className="preference-modal-backdrop" role="presentation" onClick={onBackdropClose}>
      <div
        className="preference-modal"
        role="dialog"
        aria-labelledby="preference-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="preference-modal-title" className="preference-modal-title">
          Что вам важно в школе?
        </h2>
        <p className="preference-modal-hint">
          Отметьте направления — список на карте отсортируется по совпадению (данные по отзывам и Госуслугам
          есть не у всех школ; где нет данных, используется нейтральная оценка).
        </p>
        <ul className="preference-modal-list">
          {PREFS.map(({ key, label }) => (
            <li key={key}>
              <label className="preference-modal-row">
                <input type="checkbox" checked={!!form[key]} onChange={() => toggle(key)} />
                <span>{label}</span>
              </label>
            </li>
          ))}
        </ul>
        {form.location && (
          <div className="preference-modal-geo">
            <button type="button" className="btn-geo" onClick={requestGeo} disabled={loading}>
              Моё местоположение
            </button>
            {form.userLat != null && form.userLon != null && (
              <span className="preference-modal-geo-ok">точка задана</span>
            )}
          </div>
        )}
        <div className="preference-modal-actions">
          <button type="button" className="btn-pref-skip" onClick={onSkipWithoutPrefs} disabled={loading}>
            Просто смотреть карту
          </button>
          <button type="button" className="btn-pref-apply" onClick={handleApply} disabled={loading}>
            {loading ? 'Загрузка…' : 'Применить подбор'}
          </button>
        </div>
      </div>
    </div>
  );
}

export { defaultForm, PREFS };
