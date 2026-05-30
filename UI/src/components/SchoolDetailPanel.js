import React from 'react';
import { getAttachedAddressesForKey, getSchoolAttachmentKey } from '../utils/schoolAttachment';

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
  const attachKey = getSchoolAttachmentKey(school);
  const attachList = attachKey ? getAttachedAddressesForKey(attachKey) : [];
  const nHouses = attachList.length;
  const showAttachBlock = nHouses > 0;

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

      {showAttachBlock && (
        <section className="detail-block detail-block-geocode-test">
          <div className="detail-label">Прикреплённые адреса (геокод)</div>
          <p className="detail-geocode-hint">
            На карте для <strong>{nHouses}</strong> адресов: оранжевые кружки — точки (отладка), синий контур —
            острые полигоны (кластер до 200 м + оболочка). Данные:{' '}
            <code>UI/src/data/geocoded_addresses_by_school.json</code> (ключ <code>{attachKey}</code>). Обновление:{' '}
            <code>python geocoding/scripts/geocode_ans_stage1_bundle.py</code>.
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
