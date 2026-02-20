import React, { useState, useCallback, useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts';

export const TOPICS = [
  { key: 'ремонт', label: 'ремонт' },
  { key: 'учителя', label: 'учителя' },
  { key: 'еда', label: 'еда' },
  { key: 'администрация', label: 'администрация' },
  { key: 'буллинг', label: 'буллинг' },
  { key: 'инфраструктура', label: 'инфраструктура' },
  { key: 'охрана', label: 'охрана' },
  { key: 'уборка', label: 'уборка' },
];

const TOPIC_COLORS = [
  '#1f77b4',
  '#ff7f0e',
  '#2ca02c',
  '#d62728',
  '#9467bd',
  '#8c564b',
  '#e377c2',
  '#7f7f7f',
];

const HELP_POPUP_TEXT = `Были проанализированы отзывы и взяты критерии, по которым люди оценивают школы. Из них отобраны самые релевантные, и с помощью ИИ они найдены в текстах отзывов.

Если критерий упоминается в отзыве положительно («уборка хорошая», «еда вкусная», «парковку чистят зимой»), ему ставится положительный флаг. Если упоминается отрицательно («учителя грубые», «охрана спит на работе»), присваивается негативный флаг.

После этого строится график: по горизонтали — время, по вертикали — тональность (выше нуля — больше положительных упоминаний, ниже — отрицательных). По графику видно, как менялся тот или иной критерий со временем.

Пример: у школы был плохой ремонт — отзывы говорили о нём негативно. Сделали ремонт — отзывы изменились. Это видно на графике.`;

function getPeriodKey(dateStr, interval) {
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return null;
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  if (interval === 'year') return String(y);
  if (interval === 'month') return `${y}-${m}`;
  if (interval === 'week') {
    const start = new Date(d);
    const day = start.getDay();
    const diff = start.getDate() - day + (day === 0 ? -6 : 1);
    start.setDate(diff);
    const ys = start.getFullYear();
    const ms = String(start.getMonth() + 1).padStart(2, '0');
    const ds = String(start.getDate()).padStart(2, '0');
    return `${ys}-${ms}-${ds}`;
  }
  return null;
}

function formatPeriodLabel(key, interval) {
  if (interval === 'year') return key;
  if (interval === 'month') {
    const parts = key.split('-');
    if (parts.length >= 2) {
      const months = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
      return `${months[parseInt(parts[1], 10) - 1]} ${parts[0]}`;
    }
  }
  if (interval === 'week' && key.length >= 10) {
    const [y, m, d] = key.split('-');
    return `${d}.${m}`;
  }
  return key;
}

function buildChartData(reviews, appliedTopics, interval) {
  if (!reviews || reviews.length === 0 || !appliedTopics || appliedTopics.length === 0) return [];

  const byPeriod = {};
  for (const r of reviews) {
    const key = getPeriodKey(r.review_date, interval);
    if (!key) continue;
    if (!byPeriod[key]) byPeriod[key] = {};
    for (const topic of appliedTopics) {
      if (!byPeriod[key][topic]) byPeriod[key][topic] = { pos: 0, neg: 0, neutral: 0 };
      const val = r.topics && r.topics[topic];
      if (val === 'pos') byPeriod[key][topic].pos += 1;
      else if (val === 'neg') byPeriod[key][topic].neg += 1;
      else if (val === 'neutral') byPeriod[key][topic].neutral += 1;
    }
  }

  const sortedKeys = Object.keys(byPeriod).sort();
  return sortedKeys.map((key) => {
    const row = { period: key, label: formatPeriodLabel(key, interval) };
    for (const topic of appliedTopics) {
      const c = byPeriod[key][topic] || { pos: 0, neg: 0, neutral: 0 };
      const total = c.pos + c.neg + c.neutral;
      if (total === 0) row[topic] = null;
      else row[topic] = (c.pos - c.neg) / total;
    }
    return row;
  });
}

export function countTopicMentions(reviews, topic) {
  if (!reviews) return 0;
  let n = 0;
  for (const r of reviews) {
    if (r.topics && r.topics[topic] != null) n += 1;
  }
  return n;
}

export function AnalyticsChart({ reviews, appliedTopics, interval, loading }) {
  const [hoverTopic, setHoverTopic] = useState(null);
  const chartData = useMemo(
    () => buildChartData(reviews, appliedTopics, interval),
    [reviews, appliedTopics, interval]
  );

  if (loading) {
    return (
      <div className="chart-full-placeholder">
        Загрузка отзывов…
      </div>
    );
  }
  if (!appliedTopics || appliedTopics.length === 0) {
    return (
      <div className="chart-full-placeholder">
        Выберите темы слева и нажмите «применить темы»
      </div>
    );
  }
  if (chartData.length === 0) {
    return (
      <div className="chart-full-placeholder">
        Нет данных за выбранный период
      </div>
    );
  }

  return (
    <div className="chart-full-wrap">
      <div className="chart-full-title">Временной график тональности</div>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
          <YAxis
            domain={[-1, 1]}
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => (v === 0 ? '0' : v)}
            label={{ value: 'тональность', angle: -90, position: 'insideLeft', style: { fontSize: 11 } }}
          />
          <Tooltip
            formatter={(value) => (value != null ? value.toFixed(2) : '—')}
            labelFormatter={(label) => `Период: ${label}`}
          />
          <ReferenceLine y={0} stroke="#666" strokeDasharray="2 2" />
          <Legend
            formatter={(topicKey) => {
              const count = countTopicMentions(reviews, topicKey);
              const label = TOPICS.find((t) => t.key === topicKey)?.label || topicKey;
              return `${label} (${count} упом.)`;
            }}
          />
          {appliedTopics.map((topicKey, idx) => (
            <Line
              key={topicKey}
              type="monotone"
              dataKey={topicKey}
              name={topicKey}
              stroke={TOPIC_COLORS[idx % TOPIC_COLORS.length]}
              strokeWidth={hoverTopic === topicKey ? 3 : 2}
              strokeOpacity={hoverTopic == null || hoverTopic === topicKey ? 1 : 0.4}
              dot={{ r: 2 }}
              connectNulls
              onMouseEnter={() => setHoverTopic(topicKey)}
              onMouseLeave={() => setHoverTopic(null)}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function AnalyticsView({
  school,
  onBack,
  apiUrl,
  reviews,
  loading,
  appliedTopics,
  onApplyTopics,
  interval,
  onIntervalChange,
}) {
  const schoolName = school ? (school.name_2gis || school.name_ym || `Школа ${school.school_id}`) : '';

  const [selectedTopics, setSelectedTopics] = useState([]);
  const [helpOpen, setHelpOpen] = useState(false);

  const toggleTopic = useCallback((key) => {
    setSelectedTopics((prev) =>
      prev.includes(key) ? prev.filter((t) => t !== key) : [...prev, key]
    );
  }, []);

  const handleApply = useCallback(() => {
    onApplyTopics(selectedTopics.length ? [...selectedTopics] : []);
  }, [selectedTopics, onApplyTopics]);

  return (
    <aside className="side-panel side-panel-analytics">
      <h1 className="panel-title">Анализ школ Саратова</h1>
      <h2 className="school-name">{schoolName}</h2>

      <section className="analytics-block">
        <div className="detail-label">Выбор тем</div>
        <ul className="topics-list">
          {TOPICS.map(({ key, label }) => (
            <li key={key}>
              <button
                type="button"
                className={`topic-chip ${selectedTopics.includes(key) ? 'selected' : ''}`}
                onClick={() => toggleTopic(key)}
              >
                <span className="topic-bullet">{selectedTopics.includes(key) ? '●' : '○'}</span>
                {label}
              </button>
            </li>
          ))}
        </ul>
      </section>

      <button type="button" className="link-help" onClick={() => setHelpOpen(true)}>
        что такое темы, как они находятся и как с ними работать?
      </button>

      <div className="analytics-buttons">
        <button type="button" className="btn-apply" onClick={handleApply}>
          применить темы
        </button>
        <button type="button" className="btn-back" onClick={onBack}>
          назад к школам
        </button>
      </div>

      <div className="interval-selector">
        <span className="detail-label">Интервал:</span>
        {['week', 'month', 'year'].map((int) => (
          <label key={int} className="interval-option">
            <input
              type="radio"
              name="interval"
              checked={interval === int}
              onChange={() => onIntervalChange(int)}
            />
            {int === 'week' && 'недели'}
            {int === 'month' && 'месяцы'}
            {int === 'year' && 'годы'}
          </label>
        ))}
      </div>

      {helpOpen && (
        <div className="modal-overlay" onClick={() => setHelpOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3 className="modal-title">Что такое темы и как с ними работать</h3>
            <div className="modal-body">{HELP_POPUP_TEXT}</div>
            <button type="button" className="btn-close-modal" onClick={() => setHelpOpen(false)}>
              Закрыть
            </button>
          </div>
        </div>
      )}
    </aside>
  );
}
