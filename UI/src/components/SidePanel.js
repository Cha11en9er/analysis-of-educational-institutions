import React, { useState, useCallback } from 'react';

const FILTER_KEYS = {
  year: 'Год постройки',
  rating: 'Рейтинг',
  sports: 'Наличие спорт объектов',
};

const SPORTS_OPTIONS = [
  { key: 'has_stadium', label: 'Футбольное поле' },
  { key: 'has_pool', label: 'Бассейн' },
  { key: 'has_sports_ground', label: 'Спорт площадка' },
  { key: 'has_sports_complex', label: 'Спорткомплекс' },
];

export default function SidePanel({
  searchQuery,
  onSearchChange,
  onSearchSubmit,
  filterState,
  onFilterChange,
  onApply,
  onReset,
  filtersApplied,
  loading,
  preferencesActive,
  onOpenPreferences,
}) {
  const [openFilter, setOpenFilter] = useState(null);

  const toggleFilter = useCallback((key) => {
    setOpenFilter((prev) => (prev === key ? null : key));
  }, []);

  const handleYearMin = (e) => {
    const v = e.target.value.trim();
    onFilterChange({ ...filterState, yearMin: v === '' ? null : v });
  };
  const handleYearMax = (e) => {
    const v = e.target.value.trim();
    onFilterChange({ ...filterState, yearMax: v === '' ? null : v });
  };
  const handleRatingMin = (e) => {
    const v = e.target.value.trim();
    onFilterChange({ ...filterState, ratingMin: v === '' ? null : v });
  };
  const handleRatingMax = (e) => {
    const v = e.target.value.trim();
    onFilterChange({ ...filterState, ratingMax: v === '' ? null : v });
  };
  const handleSportToggle = (key) => {
    const current = filterState.sports || {};
    onFilterChange({
      ...filterState,
      sports: { ...current, [key]: !current[key] },
    });
  };

  return (
    <aside className="side-panel">
      <h1 className="panel-title">Анализ школ Саратова</h1>
      <div className="preference-panel-row">
        <button
          type="button"
          className="btn-preferences"
          onClick={onOpenPreferences}
          disabled={loading}
        >
          Что вам важно в школе?
        </button>
        {preferencesActive && <span className="preference-badge">подбор вкл.</span>}
      </div>

      <section className="search-section">
        <label className="label">Поиск</label>
        <div className="search-row">
          <input
            type="text"
            className="search-input"
            placeholder="Введите запрос..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && onSearchSubmit()}
          />
          <button
            type="button"
            className="search-btn"
            onClick={onSearchSubmit}
            aria-label="Найти"
          >
            <span className="search-icon">🔍</span>
          </button>
        </div>
      </section>

      <section className="filters-section">
        <div className="filters-header">
          <span className="label">Фильтры</span>
        </div>

        {Object.entries(FILTER_KEYS).map(([key, label]) => (
          <div key={key} className="filter-block">
            <button
              type="button"
              className={`filter-trigger ${openFilter === key ? 'open' : ''}`}
              onClick={() => toggleFilter(key)}
            >
              {label}
              <span className="filter-chevron">{openFilter === key ? '▼' : '▶'}</span>
            </button>
            {openFilter === key && (
              <div className="filter-body">
                {key === 'year' && (
                  <div className="filter-year">
                    <label>От</label>
                    <input
                      type="number"
                      min={1800}
                      max={2100}
                      placeholder="год"
                      value={filterState.yearMin ?? ''}
                      onChange={handleYearMin}
                    />
                    <label>До</label>
                    <input
                      type="number"
                      min={1800}
                      max={2100}
                      placeholder="год"
                      value={filterState.yearMax ?? ''}
                      onChange={handleYearMax}
                    />
                  </div>
                )}
                {key === 'rating' && (
                  <div className="filter-rating">
                    <label>От</label>
                    <input
                      type="number"
                      min={1}
                      max={5}
                      step={0.1}
                      placeholder="1"
                      value={filterState.ratingMin ?? ''}
                      onChange={handleRatingMin}
                    />
                    <label>До</label>
                    <input
                      type="number"
                      min={1}
                      max={5}
                      step={0.1}
                      placeholder="5"
                      value={filterState.ratingMax ?? ''}
                      onChange={handleRatingMax}
                    />
                  </div>
                )}
                {key === 'sports' && (
                  <div className="filter-sports">
                    {SPORTS_OPTIONS.map(({ key: optKey, label: optLabel }) => (
                      <label key={optKey} className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={!!(filterState.sports && filterState.sports[optKey])}
                          onChange={() => handleSportToggle(optKey)}
                        />
                        {optLabel}
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        <div className="apply-row">
          <button
            type="button"
            className="btn-apply"
            onClick={onApply}
            disabled={loading}
          >
            {loading ? 'Загрузка…' : 'Применить'}
          </button>
          {filtersApplied && (
            <button type="button" className="btn-reset" onClick={onReset}>
              Сбросить фильтры
            </button>
          )}
        </div>
      </section>
    </aside>
  );
}
