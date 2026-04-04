import React from 'react';
import { isGeocodeTestSchool } from '../utils/geocodeTestSchool';
import geocodedAddresses from '../data/geocoded_addresses_sosh6.json';
import streetPolygons from '../data/street_polygons_sosh6.json';

const SPORTS_LABELS = [
  { key: 'has_sports_complex', label: 'Спорткомплекс' },
  { key: 'has_pool', label: 'Бассейн' },
  { key: 'has_stadium', label: 'Футбольное поле' },
  { key: 'has_sports_ground', label: 'Спорт площадка' },
];

export default function SchoolDetailPanel({ school, onBack, onStatistics }) {
  if (!school) return null;

  const name = school.name_2gis || school.name_ym || `Школа ${school.school_id}`;
  const sportsPresent = SPORTS_LABELS.filter(({ key }) => school[key] === true);
  const sportsNone = sportsPresent.length === 0;
  const geocodeTest = isGeocodeTestSchool(school);
  const nHouses = geocodedAddresses?.length ?? 0;
  const nStreets = streetPolygons?.length ?? 0;

  return (
    <aside className="side-panel side-panel-school">
      <h1 className="panel-title">Анализ школ Саратова</h1>

      <h2 className="school-name">{name}</h2>

      <section className="detail-block">
        <div className="detail-row">
          <span className="detail-label">Адрес</span>
          <span className="detail-value">{school.school_address || '—'}</span>
        </div>
      </section>

      {geocodeTest && (
        <section className="detail-block detail-block-geocode-test">
          <div className="detail-label">Тест: привязанные адреса (геокод)</div>
          <p className="detail-geocode-hint">
            На карте показаны <strong>{nHouses}</strong> домов (точки) и <strong>{nStreets}</strong>{' '}
            полигонов улиц из <code>geocode_test</code>. Данные в{' '}
            <code>UI/src/data/geocoded_addresses_sosh6.json</code> и{' '}
            <code>street_polygons_sosh6.json</code> (копия из <code>geocoding/geocode_test/</code>).
          </p>
        </section>
      )}

      <section className="detail-block">
        <div className="detail-row">
          <span className="detail-label">Тип здания</span>
          <span className="detail-value">{school.building_type || '—'}</span>
        </div>
      </section>

      <section className="detail-block">
        <div className="detail-row">
          <span className="detail-label">Кол-во этажей</span>
          <span className="detail-value">{school.floors != null ? school.floors : '—'}</span>
        </div>
      </section>

      <section className="detail-block">
        <div className="detail-label">Ссылки на школу в 2ГИС / Яндекс.Карты</div>
        <div className="detail-links">
          {school.link_2gis && (
            <a href={school.link_2gis} target="_blank" rel="noopener noreferrer" className="detail-link">
              Ссылка на школу в 2ГИС
            </a>
          )}
          {school.link_yandex && (
            <a href={school.link_yandex} target="_blank" rel="noopener noreferrer" className="detail-link">
              Ссылка на школу в Яндекс.Картах
            </a>
          )}
          {!school.link_2gis && !school.link_yandex && <span className="detail-value">—</span>}
        </div>
      </section>

      <section className="detail-block">
        <div className="detail-row">
          <span className="detail-label">Год постройки</span>
          <span className="detail-value">{school.year_built != null ? school.year_built : '—'}</span>
        </div>
      </section>

      <section className="detail-block">
        <div className="detail-row">
          <span className="detail-label">Год реконструкции</span>
          <span className="detail-value">
            {school.reconstruction_year != null && school.reconstruction_year !== ''
              ? school.reconstruction_year
              : 'Реконструкция не проводилась'}
          </span>
        </div>
      </section>

      <section className="detail-block detail-block-sports">
        <div className="detail-label">Наличие спортивных объектов на территории школы</div>
        {sportsNone ? (
          <span className="detail-value">Нет данных</span>
        ) : (
          <ul className="sports-list">
            {sportsPresent.map(({ label }) => (
              <li key={label}>{label}</li>
            ))}
          </ul>
        )}
      </section>

      <button type="button" className="btn-statistics" onClick={onStatistics}>
        Статистика по комментариям
      </button>

      <button type="button" className="btn-back" onClick={onBack}>
        Обратно ко всем школам
      </button>
    </aside>
  );
}
