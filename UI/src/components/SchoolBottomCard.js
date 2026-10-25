import React from 'react';

const SPORTS_LABELS = [
  { key: 'has_sports_complex', label: 'ФОК' },
  { key: 'has_pool', label: 'Бассейн' },
  { key: 'has_stadium', label: 'Стадион' },
  { key: 'has_sports_ground', label: 'Спортплощадка' },
];

// Компоненты рейтинга — показываем натуральные значения, не проценты:
// ЕГЭ — средний балл; Олимпиады — число победителей/призёров;
// Учителя/Оснащённость/Атмосфера — индекс по отзывам, шкала 0–10.
export const RATING_COMPONENTS = [
  { key: 'rating_ege', label: 'ЕГЭ', kind: 'ege' },
  { key: 'olympiad_winners_count', label: 'Олимпиады', kind: 'olympiads' },
  { key: 'rating_teachers', label: 'Учителя', kind: 'score10' },
  { key: 'rating_mto', label: 'Оснащённость', kind: 'score10' },
  { key: 'rating_psychological_climate', label: 'Атмосфера', kind: 'score10' },
];

export function formatWinners(n) {
  const abs = Math.abs(n) % 100;
  const last = abs % 10;
  if (n === 0) return 'нет победителей';
  if (abs > 10 && abs < 20) return `${n} победителей`;
  if (last > 1 && last < 5) return `${n} победителя`;
  if (last === 1) return `${n} победитель`;
  return `${n} победителей`;
}

/**
 * Число для отображения и ширина полоски (0–100) для компонента рейтинга.
 * maxima — максимумы по текущей выборке школ (для относительного масштаба).
 */
export function componentValue(school, comp, maxima) {
  const v = school?.[comp.key];
  if (typeof v !== 'number' || !Number.isFinite(v)) return null;
  switch (comp.kind) {
    case 'ege':
      return { text: v.toFixed(1), width: Math.max(0, Math.min(100, v)) };
    case 'olympiads': {
      const max = maxima?.olympiads || 0;
      const width = max > 0 ? Math.round((v / max) * 100) : v > 0 ? 100 : 0;
      return { text: formatWinners(v), width: Math.min(100, width) };
    }
    default:
      return { text: `${(v * 10).toFixed(1)}/10`, width: Math.round(Math.min(1, v) * 100) };
  }
}

export function StarRating({ value, size = 14 }) {
  if (value == null || !Number.isFinite(Number(value))) return null;
  return (
    <span className="star-rating" title={`Средняя оценка отзывов: ${Number(value).toFixed(1)}`}>
      <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
        <path
          d="M12 2l2.9 6.3 6.9.8-5.1 4.7 1.4 6.8L12 17.2l-6.1 3.4 1.4-6.8L2.2 9.1l6.9-.8z"
          fill="#f59e0b"
        />
      </svg>
      <b>{Number(value).toFixed(1)}</b>
    </span>
  );
}

export function avgReviewRating(school) {
  const vals = [school.rating_2gis, school.rating_yandex]
    .map((v) => Number(v))
    .filter((v) => Number.isFinite(v) && v > 0);
  if (!vals.length) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

/**
 * Нижняя карточка выбранной школы поверх карты (белая, как на Replit-версии).
 * Тексты отзывов не показываются нигде — только агрегаты.
 */
export default function SchoolBottomCard({ school, rank, total, maxima, onClose, onOpenDetails }) {
  if (!school) return null;
  const name = school.name_ym || school.name_2gis || `Школа ${school.school_id}`;
  const sports = SPORTS_LABELS.filter(({ key }) => school[key] === true);
  const components = RATING_COMPONENTS
    .map((comp) => ({ label: comp.label, ...componentValue(school, comp, maxima) }))
    .filter((c) => c.text != null);
  const star = avgReviewRating(school);

  return (
    <div className="school-bottom-card">
      <button type="button" className="bottom-card-close" onClick={onClose} aria-label="Закрыть карточку">✕</button>
      <div className="bottom-card-main">
        <div className="bottom-card-head">
          <div className="bottom-card-rank">
            {rank != null ? `#${rank}` : ''}
            <span className="bottom-card-rank-total">из {total}</span>
          </div>
          <div className="bottom-card-title">
            <div className="bottom-card-name">
              {name}
              <StarRating value={star} />
            </div>
            <div className="bottom-card-address">{school.school_address}</div>
          </div>
          <div className="bottom-card-score">
            <span className="score-value">{school.rating_total != null ? Number(school.rating_total).toFixed(1) : '—'}</span>
            <span className="score-caption">баллов</span>
          </div>
        </div>

        <div className="bottom-card-facts">
          {school.rating_2gis != null && (
            <div className="fact"><span className="fact-src">2ГИС</span><span className="fact-val">{Number(school.rating_2gis).toFixed(1)}</span></div>
          )}
          {school.rating_yandex != null && (
            <div className="fact"><span className="fact-src">Яндекс</span><span className="fact-val">{Number(school.rating_yandex).toFixed(1)}</span></div>
          )}
          {school.ege_average_score != null && school.ege_average_score > 0 && (
            <div className="fact"><span className="fact-src">ЕГЭ{school.ege_year ? ` ${school.ege_year}` : ''}</span><span className="fact-val">{Number(school.ege_average_score).toFixed(1)}</span></div>
          )}
          {school.olympiad_winners_count != null && school.olympiad_winners_count > 0 && (
            <div className="fact"><span className="fact-src">Олимпиады</span><span className="fact-val">{school.olympiad_winners_count}</span></div>
          )}
        </div>

        {components.length > 0 && (
          <div className="bottom-card-components">
            <div className="components-title">Компоненты рейтинга</div>
            {components.map(({ label, text, width }) => (
              <div className="component-row" key={label}>
                <span className="component-label">{label}</span>
                <div className="component-track">
                  <div className="component-bar" style={{ width: `${width}%` }} />
                </div>
                <span className="component-val">{text}</span>
              </div>
            ))}
          </div>
        )}

        {sports.length > 0 && (
          <div className="bottom-card-chips">
            {sports.map(({ label }) => <span className="chip" key={label}>{label}</span>)}
          </div>
        )}

        <div className="bottom-card-actions">
          {school.link_2gis && (
            <a href={school.link_2gis} target="_blank" rel="noopener noreferrer" className="bottom-link">Открыть в 2ГИС</a>
          )}
          {school.link_yandex && (
            <a href={school.link_yandex} target="_blank" rel="noopener noreferrer" className="bottom-link">Открыть в Яндекс Картах</a>
          )}
          <button type="button" className="bottom-details-btn" onClick={onOpenDetails}>
            Подробный анализ →
          </button>
        </div>
      </div>
    </div>
  );
}
