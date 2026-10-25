import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts';
import { TOPICS } from './AnalyticsView';
import { StarRating, avgReviewRating } from './SchoolBottomCard';

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

// rating_ege — сам средний балл ЕГЭ (0–100), остальные — доли 0..1
const RATING_COMPONENTS = [
  { key: 'rating_ege', label: 'ЕГЭ', pct: (v) => Math.min(100, Math.round(v)) },
  { key: 'rating_olympiads', label: 'Олимпиады', pct: (v) => Math.round(v * 100) },
  { key: 'rating_teachers', label: 'Учителя', pct: (v) => Math.round(v * 100) },
  { key: 'rating_mto', label: 'Оснащённость', pct: (v) => Math.round(v * 100) },
  { key: 'rating_psychological_climate', label: 'Атмосфера', pct: (v) => Math.round(v * 100) },
  { key: 'rating_sports_infrastructure', label: 'Спорт', pct: (v) => Math.round(v * 100) },
];

/**
 * Полная страница анализа школы в стиле Replit-версии: светлый фон, белые
 * карточки r16, Inter. Тексты отзывов не отображаются — только агрегаты.
 */
export default function SchoolAnalysisPage({ school, rank, total, onBack, onShowDynamics }) {
  const [reviews, setReviews] = useState([]);
  const [loadingReviews, setLoadingReviews] = useState(true);

  useEffect(() => {
    if (!school) return undefined;
    let cancelled = false;
    setLoadingReviews(true);
    axios
      .get(`${API_URL}/api/schools/${school.school_id}/reviews/topics`)
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
    .map(({ key, label, pct }) => {
      const v = school?.[key];
      if (typeof v !== 'number' || !Number.isFinite(v)) return null;
      return { label, pct: Math.max(0, Math.min(100, pct(v))) };
    })
    .filter(Boolean), [school]);

  if (!school) return null;
  const name = school.name_ym || school.name_2gis || `Школа ${school.school_id}`;
  const sports = SPORTS_LABELS.filter(({ key }) => school[key] === true);
  const star = avgReviewRating(school);
  const totalMentions = sentimentData.reduce((acc, d) => acc + d.value, 0);

  return (
    <div className="analysis-page">
      <button type="button" className="analysis-back-btn" onClick={onBack}>
        ← Назад к рейтингу
      </button>

      <header className="ap-header">
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
            {school.rating_total != null ? Number(school.rating_total).toFixed(2) : '—'}
          </span>
          <span className="ap-score-caption">баллов</span>
        </div>
      </header>

      <div className="ap-metrics">
        <div className="ap-card ap-metric">
          <span className="ap-metric-label">Оценки пользователей</span>
          <div className="ap-metric-ratings">
            {school.rating_2gis != null && (
              <span className="ap-rating"><StarRating value={Number(school.rating_2gis)} /> <i>2ГИС</i></span>
            )}
            {school.rating_yandex != null && (
              <span className="ap-rating"><StarRating value={Number(school.rating_yandex)} /> <i>Яндекс</i></span>
            )}
            {school.rating_2gis == null && school.rating_yandex == null && <span className="ap-muted">Нет оценок</span>}
          </div>
        </div>
        <div className="ap-card ap-metric">
          <span className="ap-metric-label">Средний балл ЕГЭ{school.ege_year ? ` ${school.ege_year}` : ''}</span>
          <span className="ap-metric-value">{school.ege_average_score > 0 ? Number(school.ege_average_score).toFixed(1) : '—'}</span>
        </div>
        <div className="ap-card ap-metric">
          <span className="ap-metric-label">Олимпиады</span>
          <span className="ap-metric-value">{school.olympiad_winners_count || '—'}</span>
          {school.olympiad_winners_count > 0 && <span className="ap-metric-sub">победителей и призёров</span>}
        </div>
        <div className="ap-card ap-metric">
          <span className="ap-metric-label">Поступление в вузы{school.university_admission_year ? ` ${school.university_admission_year}` : ''}</span>
          <span className="ap-metric-value">
            {school.university_admission_percent != null ? `${Math.round(school.university_admission_percent)}%` : '—'}
          </span>
        </div>
      </div>

      <section className="ap-card ap-section">
        <h3>О здании</h3>
        <div className="ap-kv-grid">
          <div className="ap-kv"><span>Год постройки</span><b>{school.year_built ?? '—'}</b></div>
          <div className="ap-kv"><span>Год реконструкции</span><b>{school.reconstruction_year ?? '—'}</b></div>
          <div className="ap-kv"><span>Этажность</span><b>{school.floors ?? '—'}</b></div>
          <div className="ap-kv"><span>Вместимость</span><b>{school.capacity ? `${school.capacity} мест` : '—'}</b></div>
          <div className="ap-kv"><span>Площадь</span><b>{school.area_sqm ? `${Number(school.area_sqm).toLocaleString('ru-RU')} м²` : '—'}</b></div>
          <div className="ap-kv"><span>Материал</span><b>{school.wall_material || '—'}</b></div>
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

      {ratingBars.length > 0 && (
        <section className="ap-card ap-section">
          <h3>Структура рейтинга</h3>
          <p className="ap-muted ap-section-hint">Относительные показатели школы по ключевым метрикам</p>
          <div className="ap-bars">
            {ratingBars.map(({ label, pct }) => (
              <div className="ap-bar-row" key={label}>
                <span className="ap-bar-label">{label}</span>
                <div className="ap-bar-track"><div className="ap-bar-fill" style={{ width: `${pct}%` }} /></div>
                <span className="ap-bar-val">{pct}%</span>
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
          оценки — без исходных текстов.
          {loadingReviews ? ' Загрузка…' : totalMentions > 0 ? ` Основа: ${reviews.length} отзывов.` : ' Отзывов с анализом пока нет.'}
        </p>

        {!loadingReviews && totalMentions > 0 && (
          <>
            <div className="ap-reviews-grid">
              <div className="ap-reviews-block">
                <h4>Общая тональность</h4>
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
            {onShowDynamics && (
              <button type="button" className="ap-dynamics-btn" onClick={onShowDynamics}>
                Динамика отзывов по месяцам →
              </button>
            )}
          </>
        )}
      </section>
    </div>
  );
}

const tooltipStyle = { background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 10, fontSize: 13 };
