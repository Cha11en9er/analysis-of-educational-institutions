import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts';
import { TOPICS } from './AnalyticsView';
import { StarRating, avgReviewRating, RATING_COMPONENTS, TOTAL_PARTS, componentValue, formatWinners } from './SchoolBottomCard';

const API_URL =
  process.env.REACT_APP_API_URL !== undefined
    ? process.env.REACT_APP_API_URL
    : (typeof window !== 'undefined' &&
      /^(localhost|127\.0\.0\.1)$/.test(window.location.hostname)
        ? 'http://localhost:8000'
        : '');

const SPORTS_LABELS = [
  { key: 'has_sports_complex', label: 'ФОК' },
  { key: 'has_pool', label: 'Бассейн' },
  { key: 'has_stadium', label: 'Стадион' },
  { key: 'has_sports_ground', label: 'Спортплощадка' },
];

const SENTIMENT_COLORS = { 'Позитивные': '#22c55e', 'Нейтральные': '#94a3b8', 'Негативные': '#ef4444' };

/**
 * Полная страница анализа школы в стиле Replit-версии: светлый фон, белые
 * карточки r16, Inter. Тексты отзывов не отображаются — только агрегаты.
 */
export default function SchoolAnalysisPage({ school, rank, total, maxima, onBack }) {
  const [reviews, setReviews] = useState([]);
  const [loadingReviews, setLoadingReviews] = useState(true);

  useEffect(() => {
    if (!school) return undefined;
    let cancelled = false;
    setLoadingReviews(true);
    axios
      .get(`${API_URL}/api/schools/${school.school_id}/reviews/topics`, { headers: { 'Cache-Control': 'no-cache' } })
      .then(({ data }) => { if (!cancelled) setReviews(data.reviews || []); })
      .catch(() => { if (!cancelled) setReviews([]); })
      .finally(() => { if (!cancelled) setLoadingReviews(false); });
    return () => { cancelled = true; };
  }, [school]);

  const sentimentData = useMemo(() => {
    const counts = { 'Позитивные': 0, 'Нейтральные': 0, 'Негативные': 0 };
    reviews.forEach((r) => {
      Object.values(r.topics || {}).forEach((v) => {
        if (v === 'pos') counts['Позитивные'] += 1;
        else if (v === 'neg') counts['Негативные'] += 1;
        else counts['Нейтральные'] += 1;
      });
    });
    return Object.entries(counts).map(([name, value]) => ({ name, value })).filter((d) => d.value > 0);
  }, [reviews]);

  const topicData = useMemo(() => TOPICS.map(({ key, label }) => {
    let pos = 0; let neg = 0; let neutral = 0;
    reviews.forEach((r) => {
      const v = (r.topics || {})[key];
      if (v === 'pos') pos += 1;
      else if (v === 'neg') neg += 1;
      else if (v === 'neutral') neutral += 1;
    });
    return { topic: label, Позитивно: pos, Нейтрально: neutral, Негативно: neg };
  }).filter((d) => d.Позитивно + d.Нейтрально + d.Негативно > 0), [reviews]);

  const ratingBars = useMemo(() => RATING_COMPONENTS
    .map((comp) => ({ label: comp.label, ...componentValue(school, comp, maxima) }))
    .filter((c) => c.text != null), [school, maxima]);

  if (!school) return null;
  const totalParts = TOTAL_PARTS.filter(({ key }) => typeof school[key] === 'number')
    .map(({ key, label }) => ({ label, value: Number(school[key]).toFixed(1) }));
  if (school.has_second_shift === true && school.rating_total != null) {
    totalParts.push({ label: 'Вторая смена', value: '-10.0' });
  }
  const name = school.name_ym || school.name_2gis || `Школа ${school.school_id}`;
  const sports = SPORTS_LABELS.filter(({ key }) => school[key] === true);
  const subjects = Array.isArray(school.ege_subjects) ? school.ege_subjects : [];
  const subjectsYear = subjects.find((s) => s.year)?.year || null;
  const star = avgReviewRating(school);
  const totalMentions = sentimentData.reduce((acc, d) => acc + d.value, 0);

  return (
    <div className="analysis-page">
      <button type="button" className="analysis-back-btn" onClick={onBack}>
        ← Назад к рейтингу
      </button>

      <header className="ap-header">
        <div className="ap-header-row">
          <div className="ap-header-main">
            <div className="ap-badges">
              {rank != null && <span className="ap-badge ap-badge-rank">#{rank} из {total}</span>}
              {school.building_type && <span className="ap-badge">{school.building_type}</span>}
              {school.administrative_district && <span className="ap-badge">{school.administrative_district} район</span>}
            </div>
            <h1 className="ap-title">
              {name}
              <StarRating value={star} size={20} />
            </h1>
            <p className="ap-address">{school.school_address}{school.city ? ` · ${school.city}` : ''}</p>
          </div>
          <div className="ap-score">
            <span className="ap-score-label">Итоговый балл</span>
            <span className="ap-score-value">
              {school.rating_total != null ? Number(school.rating_total).toFixed(2) : 'нет данных'}
            </span>
            <span className="ap-score-caption">баллов</span>
          </div>
        </div>

        {school.photo && (
          <img className="ap-photo-wide" src={school.photo} alt={name} loading="lazy" />
        )}

        <div className="ap-facts">
          {school.rating_2gis != null && (
            <div className="ap-fact"><span>2ГИС</span><b>{Number(school.rating_2gis).toFixed(1)}</b></div>
          )}
          {school.rating_yandex != null && (
            <div className="ap-fact"><span>Яндекс</span><b>{Number(school.rating_yandex).toFixed(1)}</b></div>
          )}
          {school.ege_average_score != null && school.ege_average_score > 0 && (
            <div className="ap-fact">
              <span>ЕГЭ{school.ege_year ? ` ${school.ege_year}` : ''}</span>
              <b>{Number(school.ege_average_score).toFixed(1)}</b>
            </div>
          )}
          {school.university_admission_percent != null && school.university_admission_percent > 0 && (
            <div className="ap-fact">
              <span>В вузы{school.university_admission_year ? ` ${school.university_admission_year}` : ''}</span>
              <b>{Math.round(school.university_admission_percent)}%</b>
            </div>
          )}
          {school.olympiad_winners_count != null && school.olympiad_winners_count > 0 && (
            <div className="ap-fact"><span>Олимпиады</span><b>{school.olympiad_winners_count}</b></div>
          )}
          {school.price_median != null && school.price_median > 0 && (
            <div className="ap-fact"><span>Медиана жилья</span><b>{(school.price_median / 1e6).toFixed(1)} млн</b></div>
          )}
        </div>

        <div className="ap-links">
          {school.link_2gis && (
            <a href={school.link_2gis} target="_blank" rel="noopener noreferrer" className="ap-link">Открыть в 2ГИС</a>
          )}
          {school.link_yandex && (
            <a href={school.link_yandex} target="_blank" rel="noopener noreferrer" className="ap-link">Открыть в Яндекс Картах</a>
          )}
          {school.link_gosuslugi && (
            <a
              href={school.link_gosuslugi}
              target="_blank"
              rel="noopener noreferrer"
              className="ap-link"
              title="Официальный сайт школы на Госуслугах"
            >
              Госуслуги школы
            </a>
          )}
        </div>
      </header>

      {subjects.length > 0 && (
        <section className="ap-card ap-section">
          <h3>Баллы ЕГЭ по предметам{subjectsYear ? `, ${subjectsYear}` : ''}</h3>
          <p className="ap-section-hint">
            Школа публикует баллы по отдельным предметам, общий средний балл на сайте не указан.
            В общий рейтинг эти значения не входят.
          </p>
          <div className="ap-kv-grid">
            {subjects.map((s) => (
              <div className="ap-kv" key={s.subject}>
                <span>{s.subject}</span>
                <b>{s.score != null ? Number(s.score).toFixed(1) : '—'}</b>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="ap-card ap-section">
        <h3>О здании</h3>
        <div className="ap-kv-grid">
          <div className="ap-kv"><span>Год постройки</span><b>{school.year_built ?? 'нет данных'}</b></div>
          <div className="ap-kv"><span>Год реконструкции</span><b>{school.reconstruction_year ?? 'нет данных'}</b></div>
          <div className="ap-kv"><span>Этажность</span><b>{school.floors ?? 'нет данных'}</b></div>
          <div className="ap-kv"><span>Вместимость</span><b>{school.capacity ? `${school.capacity} мест` : 'нет данных'}</b></div>
          <div className="ap-kv"><span>Площадь</span><b>{school.area_sqm ? `${Number(school.area_sqm).toLocaleString('ru-RU')} м²` : 'нет данных'}</b></div>
          <div className="ap-kv"><span>Материал</span><b>{school.wall_material || 'нет данных'}</b></div>
        </div>
      </section>

      <section className="ap-card ap-section">
        <h3>Инфраструктура</h3>
        {sports.length
          ? <div className="ap-chips">{sports.map(({ label }) => <span className="chip" key={label}>{label}</span>)}</div>
          : <p className="ap-muted">Нет данных</p>}
      </section>

      {(school.top_tags || []).length > 0 && (
        <section className="ap-card ap-section">
          <h3>Чаще всего упоминают</h3>
          <div className="ap-chips">{school.top_tags.map((t) => <span className="chip chip-tag" key={t}>{t}</span>)}</div>
        </section>
      )}

      {totalParts.length > 0 && (
        <section className="ap-card ap-section">
          <h3>Слагаемые рейтинга</h3>
          <p className="ap-muted ap-section-hint">
            Итоговый балл складывается из подтверждённых показателей; отсутствующие просто не добавляются.
            Показатели из отзывов (учителя, оснащённость, атмосфера) в итог не входят.
          </p>
          <div className="ap-bars">
            {totalParts.map(({ label, value }) => (
              <div className="ap-bar-row" key={label}>
                <span className="ap-bar-label">{label}</span>
                <div className="ap-bar-track" />
                <span className="ap-bar-val">{value}</span>
              </div>
            ))}
            <div className="ap-bar-row">
              <span className="ap-bar-label"><b>Итоговый балл</b></span>
              <div className="ap-bar-track" />
              <span className="ap-bar-val"><b>{school.rating_total != null ? Number(school.rating_total).toFixed(1) : '—'}</b></span>
            </div>
          </div>
        </section>
      )}

      {ratingBars.length > 0 && (
        <section className="ap-card ap-section">
          <h3>Показатели из отзывов</h3>
          <p className="ap-muted ap-section-hint">Шкала 0–10 по тематическому анализу отзывов</p>
          <div className="ap-bars">
            {ratingBars.map(({ label, text, width }) => (
              <div className="ap-bar-row" key={label}>
                <span className="ap-bar-label">{label}</span>
                <div className="ap-bar-track"><div className="ap-bar-fill" style={{ width: `${width}%` }} /></div>
                <span className="ap-bar-val">{text}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="ap-card ap-section ap-reviews">
        <h2>Анализ отзывов</h2>
        <p className="ap-muted ap-section-hint">
          Мы проанализировали отзывы о школе из открытых источников с помощью нейросетей, чтобы выделить
          главные темы и общую тональность мнений родителей и учеников. Публикуются только агрегированные
          оценки, без исходных текстов.
          {loadingReviews ? ' Загрузка…' : totalMentions > 0 ? ` Основа: ${reviews.length} отзывов.` : ' Отзывов с анализом пока нет.'}
        </p>

        {!loadingReviews && totalMentions > 0 && (
          <>
            <div className="ap-reviews-grid">
              <div className="ap-reviews-block">
                <h4>Тональность тематических упоминаний</h4>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie data={sentimentData} dataKey="value" nameKey="name" innerRadius={52} outerRadius={76} paddingAngle={3}>
                      {sentimentData.map((d) => <Cell key={d.name} fill={SENTIMENT_COLORS[d.name]} />)}
                    </Pie>
                    <Tooltip contentStyle={tooltipStyle} />
                  </PieChart>
                </ResponsiveContainer>
                <ul className="ap-legend">
                  {sentimentData.map((d) => (
                    <li key={d.name}><span className="ap-dot" style={{ background: SENTIMENT_COLORS[d.name] }} />{d.name}: {d.value}</li>
                  ))}
                </ul>
              </div>
              <div className="ap-reviews-block">
                <h4>Упоминания по темам</h4>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={topicData} layout="vertical" margin={{ top: 0, right: 12, left: 44, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis type="number" tick={{ fill: '#64748b', fontSize: 12 }} />
                    <YAxis type="category" dataKey="topic" tick={{ fill: '#64748b', fontSize: 12 }} width={96} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Bar dataKey="Позитивно" stackId="a" fill="#22c55e" radius={[3, 0, 0, 3]} />
                    <Bar dataKey="Нейтрально" stackId="a" fill="#cbd5e1" />
                    <Bar dataKey="Негативно" stackId="a" fill="#ef4444" radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  );
}

const tooltipStyle = { background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 10, fontSize: 13 };
