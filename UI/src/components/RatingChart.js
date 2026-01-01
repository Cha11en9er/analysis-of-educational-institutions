import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';
import './Chart.css';

function RatingChart({ reviews, schoolName }) {
  // Отладочная информация
  console.log('RatingChart - reviews:', reviews);
  console.log('RatingChart - reviews count:', reviews.length);
  if (reviews.length > 0) {
    console.log('RatingChart - first review keys:', Object.keys(reviews[0]));
    console.log('RatingChart - first review:', reviews[0]);
  }
  
  // Преобразуем отзывы в данные для графика
  // Фильтруем: нужна дата и рейтинг (от 1 до 5)
  const chartData = reviews
    .filter(review => {
      const hasDate = review.review_date || review.date;
      // Проверяем наличие рейтинга (от 1 до 5)
      const rating = review.review_rating;
      // Преобразуем в число для проверки
      const ratingNum = rating !== null && rating !== undefined && rating !== '' ? Number(rating) : null;
      const hasRating = ratingNum !== null && !isNaN(ratingNum) && ratingNum >= 1 && ratingNum <= 5;
      
      // Отладочная информация для первых нескольких отзывов
      if (reviews.indexOf(review) < 5) {
        console.log('Review sample:', {
          id: review.review_id,
          date: review.review_date || review.date,
          rating: rating,
          ratingRaw: review.review_rating,
          ratingType: typeof rating,
          ratingNum: ratingNum,
          hasRating: hasRating,
          allKeys: Object.keys(review)
        });
      }
      
      if (!hasDate) {
        console.log('Review filtered out - no date:', review.review_id);
      }
      if (!hasRating) {
        console.log('Review filtered out - no rating:', review.review_id, 'rating value:', rating, 'type:', typeof rating, 'ratingNum:', ratingNum);
      }
      return hasDate && hasRating;
    })
    .map(review => {
      const date = review.review_date ? review.review_date.split('T')[0] : (review.date ? review.date.split('T')[0] : null);
      return {
        date: date,
        rating: Number(review.review_rating), // Преобразуем в число
        review: review // Сохраняем весь объект отзыва для tooltip
      };
    })
    .filter(item => item.date !== null) // Убираем записи без даты
    .sort((a, b) => new Date(a.date) - new Date(b.date));
  
  console.log('RatingChart - chartData:', chartData);
  console.log('RatingChart - chartData count:', chartData.length);

  // Кастомный Tooltip для отображения полной информации об отзыве
  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      const review = data.review;
      
      // Парсим topics, если это объект или строка
      let topicsDisplay = null;
      if (review.topics || review.review_topic) {
        const topics = review.topics || review.review_topic;
        if (typeof topics === 'string') {
          try {
            topicsDisplay = JSON.parse(topics);
          } catch (e) {
            topicsDisplay = topics;
          }
        } else {
          topicsDisplay = topics;
        }
      }
      
      return (
        <div className="custom-tooltip">
          <div className="tooltip-header">
            <strong>ID отзыва:</strong> {review.review_id}
          </div>
          <div><strong>Дата:</strong> {data.date || 'Не указана'}</div>
          <div><strong>Рейтинг:</strong> {data.rating}</div>
          {review.review_text && (
            <div className="tooltip-text">
              <strong>Текст отзыва:</strong> {review.review_text.substring(0, 300)}
              {review.review_text.length > 300 ? '...' : ''}
            </div>
          )}
          {topicsDisplay && Object.keys(topicsDisplay).length > 0 && (
            <div>
              <strong>Топики:</strong> {JSON.stringify(topicsDisplay, null, 2)}
            </div>
          )}
          {review.review_overall && (
            <div><strong>Общая тональность:</strong> {review.review_overall}</div>
          )}
          {review.review_likes !== null && review.review_likes !== undefined && (
            <div><strong>Лайки:</strong> {review.review_likes}</div>
          )}
          {review.review_dislikes !== null && review.review_dislikes !== undefined && (
            <div><strong>Дизлайки:</strong> {review.review_dislikes}</div>
          )}
        </div>
      );
    }
    return null;
  };

  if (chartData.length === 0) {
    const totalReviews = reviews.length;
    const reviewsWithRating = reviews.filter(r => {
      const rating = r.review_rating;
      const ratingNum = rating !== null && rating !== undefined && rating !== '' ? Number(rating) : null;
      return ratingNum !== null && !isNaN(ratingNum) && ratingNum >= 1 && ratingNum <= 5;
    }).length;
    const reviewsWithDate = reviews.filter(r => r.review_date || r.date).length;
    
    // Отладочная информация
    const sampleRatings = reviews.slice(0, 5).map(r => ({
      id: r.review_id,
      rating: r.review_rating,
      ratingType: typeof r.review_rating,
      hasRating: r.review_rating !== null && r.review_rating !== undefined
    }));
    console.log('Sample ratings from reviews:', sampleRatings);
    
    return (
      <div className="chart-container">
        <h2>Рейтинг отзывов: {schoolName}</h2>
        <div className="no-data">
          Нет данных с рейтингами для отображения
          <br />
          <small>
            Всего отзывов: {totalReviews} | 
            С рейтингом (1-5): {reviewsWithRating} | 
            С датой: {reviewsWithDate}
          </small>
        </div>
      </div>
    );
  }

  return (
    <div className="chart-container">
      <h2>Рейтинг отзывов: {schoolName}</h2>
      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis 
            dataKey="date" 
            angle={-45}
            textAnchor="end"
            height={80}
          />
          <YAxis 
            domain={[0, 5]}
            label={{ value: 'Рейтинг', angle: -90, position: 'insideLeft' }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend />
          <Line
            type="monotone"
            dataKey="rating"
            stroke="#4a90e2"
            strokeWidth={2}
            dot={{ r: 4 }}
            name="Рейтинг"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default RatingChart;

