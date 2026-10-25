import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts';
import { TOPICS } from './AnalyticsView';

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

const SENTIMENT_COLORS = { pos: '#22c55e', neutral: '#94a3b8', neg: '#ef4444' };

const RATING_COMPONENTS = [
  { key: 'rating_ege', label: 'ЕГЭ' },
  { key: 'rating_olympiads', label: 'Олимпиады' },
  { key: 'rating_teachers', label: 'Учителя' },
  { key: 'rating_mto', label: 'Оснащённость' },
  { key: 'rating_psychological_climate', label: 'Атмосфера' },
  { key: 'rating_sports_infrastructure', label: 'Спорт' },
];

function Section({ title, children }) {
  return (
    <section className="analysis-section">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

/**
 * Полная страница анализа школы. Отзывные тексты не отображаются:
 * только агрегированная статистика тем и тональности.
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
    const counts = { pos: 0, neutral: 0, neg: 0 };
    reviews.forEach((r) => {
      const vals = Object.values(r.topics || {});
      if (vals.length === 0) return;
      vals.forEach((v) => {
        if (v === 'pos') counts.pos += 1;
        else if (v === 'neg') counts.neg += 1;
        else counts.neutral += 1;
      });
    });
    return [
      { name: 'Позитивные', value: counts.pos },
      { name: 'Нейтральные', value: counts.neutral },
      { name: 'Негативные', value: counts.neg },
    ].filter((d) => d.value > 0);
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
    .map(({ key, label }) => ({ name: label, value: school?.[key] }))
    .filter((d) => typeof d.value === 'number' && Number.isFinite(d.value)), [school]);

  if (!school) return null;
  const name = school.name_ym || school.name_2gis || `Школа ${school.school_id}`;
  const sports = SPORTS_LABELS.filter(({ key }) => school[key] === true);
  const totalMentions = sentimentData.reduce((acc, d) => acc + d.value, 0);

  return (
    <div className="analysis-page">
      <div className="analysis-header">
        <button type="button" className="btn-back" onClick={onBack}>← Назад к рейтингу</button>
        <div className="analysis-head-main">
          <div className="analysis-rank">
            {rank != null && <span className="rank-badge">#{rank} из {total}</span>}
            {school.administrative_district && <span className="district">{school.administrative_district} район</span>}
          </div>
          <h1>{name}</h1>
          <p>{school.school_address}{school.city ? ` · ${school.city}` : ''}</p>
        </div>
        <div className="analysis-score">
          <span className="score-value">{school.rating_total != null ? Number(school.rating_total).toFixed(1) : '—'}</span>
          <span className="score-caption">итоговый балл</span>
        </div>
      </div>

      <div className="analysis-metrics">
        <div className="metric"><span className="metric-label">2ГИС</span><span className="metric-value">{school.rating_2gis != null ? Number(school.rating_2gis).toFixed(1) : '—'}</span></div>
        <div className="metric"><span className="metric-label">Яндекс</span><span className="metric-value">{school.rating_yandex != null ? Number(school.rating_yandex).toFixed(1) : '—'}</span></div>
        <div className="metric">
          <span className="metric-label">Ср. балл ЕГЭ{school.ege_year ? ` ${school.ege_year}` : ''}</span>
          <span className="metric-value">{school.ege_average_score > 0 ? Number(school.ege_average_score).toFixed(1) : '—'}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Олимпиады</span>
          <span className="metric-value">{school.olympiad_winners_count || '—'}</span>
        </div>
        <div className="metric">
          <span className="metric-label">В вузы{school.university_admission_year ? ` ${school.university_admission_year}` : ''}</span>
          <span className="metric-value">
            {school.university_admission_percent != null ? `${Math.round(school.university_admission_percent)}%` : '—'}
          </span>
        </div>
      </div>

      <div className="analysis-columns">
        <Section title="О здании">
          <div className="kv"><span>Год постройки</span><b>{school.year_built ?? '—'}</b></div>
          <div className="kv"><span>Реконструкция</span><b>{school.reconstruction_year ?? '—'}</b></div>
          <div className="kv"><span>Этажность</span><b>{school.floors ?? '—'}</b></div>
          <div className="kv"><span>Тип здания</span><b>{school.building_type || '—'}</b></div>
        </Section>

        <Section title="Инфраструктура">
          {sports.length
            ? <div className="chips">{sports.map(({ label }) => <span className="chip" key={label}>{label}</span>)}</div>
            : <p className="muted">Нет данных</p>}
        </Section>

        <Section title="Чаще всего упоминают">
          {(school.top_tags || []).length
            ? <div className="chips">{school.top_tags.map((t) => <span className="chip chip-tag" key={t}>{t}</span>)}</div>
            : <p className="muted">Нет данных</p>}
        </Section>
      </div>

      {ratingBars.length > 0 && (
        <Section title="Структура рейтинга">
          <div className="chart-box">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={ratingBars} margin={{ top: 8, right: 16, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} />
                <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8 }} />
                <Bar dataKey="value" name="Значение" fill="#fb923c" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Section>
      )}

      <Section title="Анализ отзывов">
        <div className="analysis-reviews-head">
          <p className="muted">
            Агрегированная статистика по темам из отзывов открытых источников (обработка нейросетью).
            {loadingReviews ? ' Загрузка…' : totalMentions > 0 ? ` Основа: ${reviews.length} отзывов.` : ' Отзывов с анализом нет.'}
          </p>
          {onShowDynamics && !loadingReviews && reviews.length > 0 && (
            <button type="button" className="bottom-details-btn" onClick={onShowDynamics}>
              Динамика по месяцам →
            </button>
          )}
        </div>
        {!loadingReviews && totalMentions > 0 && (
          <div className="analysis-charts-row">
            <div className="chart-box half">
              <h4>Общая тональность упоминаний</h4>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={sentimentData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={80} paddingAngle={3}>
                    {sentimentData.map((d) => (
                      <Cell key={d.name} fill={SENTIMENT_COLORS[d.name === 'Позитивные' ? 'pos' : d.name === 'Негативные' ? 'neg' : 'neutral']} />
                    ))}
                  </Pie>
                  <Legend />
                  <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="chart-box half">
              <h4>Упоминания по темам</h4>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={topicData} layout="vertical" margin={{ top: 0, right: 16, left: 40, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                  <YAxis type="category" dataKey="topic" tick={{ fill: '#94a3b8', fontSize: 12 }} width={100} />
                  <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8 }} />
                  <Legend />
                  <Bar dataKey="Позитивно" stackId="a" fill="#22c55e" radius={[0, 0, 0, 0]} />
                  <Bar dataKey="Нейтрально" stackId="a" fill="#94a3b8" />
                  <Bar dataKey="Негативно" stackId="a" fill="#ef4444" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </Section>
    </div>
  );
}
