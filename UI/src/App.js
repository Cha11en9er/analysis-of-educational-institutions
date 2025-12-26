import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';
import Filters from './components/Filters';
import Chart from './components/Chart';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Топики из rm_main.py
const TOPICS = [
  'ремонт',
  'учителя',
  'еда',
  'администрация',
  'буллинг',
  'инфраструктура',
  'охрана',
  'уборка'
];

function App() {
  const [schools, setSchools] = useState([]);
  const [selectedSchools, setSelectedSchools] = useState([]); // Массив выбранных школ (макс. 2)
  const [selectedTopic, setSelectedTopic] = useState('');
  const [dateStart, setDateStart] = useState('');
  const [dateEnd, setDateEnd] = useState('');
  const [reviewsBySchool, setReviewsBySchool] = useState({}); // { schoolId: [reviews] }
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Загружаем список школ при монтировании
  useEffect(() => {
    const fetchSchools = async () => {
      try {
        const response = await axios.get(`${API_URL}/schools`);
        setSchools(response.data.schools || []);
      } catch (err) {
        setError('Ошибка загрузки школ: ' + err.message);
      }
    };
    fetchSchools();
  }, []);

  // Функция для обработки данных отзывов и построения графика
  // Теперь группируем по школам, а не по топикам
  const processReviewsData = () => {
    if (!selectedTopic || selectedSchools.length === 0) {
      return [];
    }

    // Собираем все даты из всех отзывов
    const allDates = new Set();
    selectedSchools.forEach(schoolId => {
      const reviews = reviewsBySchool[schoolId] || [];
      reviews.forEach(review => {
        const date = review.review_date ? review.review_date.split('T')[0] : review.date;
        if (date) allDates.add(date);
      });
    });

    if (allDates.size === 0) {
      return [];
    }

    // Создаем структуру данных для графика: { date: '2024-01-01', 'Школа 1': 5, 'Школа 2': 3 }
    const dataByDate = {};
    const sortedDates = Array.from(allDates).sort();

    // Инициализируем все даты
    sortedDates.forEach(date => {
      dataByDate[date] = { date };
      selectedSchools.forEach(schoolId => {
        const school = schools.find(s => String(s.school_id) === String(schoolId));
        const schoolName = school ? (school.school_name || `Школа ${schoolId}`) : `Школа ${schoolId}`;
        dataByDate[date][schoolName] = 0;
      });
    });

    // Подсчитываем позитивные упоминания выбранного топика для каждой школы
    selectedSchools.forEach(schoolId => {
      const reviews = reviewsBySchool[schoolId] || [];
      const school = schools.find(s => String(s.school_id) === String(schoolId));
      const schoolName = school ? (school.school_name || `Школа ${schoolId}`) : `Школа ${schoolId}`;

      reviews.forEach(review => {
        const date = review.review_date ? review.review_date.split('T')[0] : review.date;
        if (!date) return;

        // Парсим topics из JSON строки или объекта
        let topics = {};
        try {
          if (typeof review.review_topic === 'string') {
            topics = JSON.parse(review.review_topic);
          } else if (typeof review.review_topic === 'object') {
            topics = review.review_topic;
          } else if (review.topics) {
            topics = typeof review.topics === 'string' ? JSON.parse(review.topics) : review.topics;
          }
        } catch (e) {
          return;
        }

        // Проверяем наличие выбранного топика и его тональность
        if (topics[selectedTopic] === 'pos') {
          if (dataByDate[date] && dataByDate[date][schoolName] !== undefined) {
            dataByDate[date][schoolName] = (dataByDate[date][schoolName] || 0) + 1;
          }
        }
      });
    });

    // Преобразуем в массив
    const chartData = sortedDates.map(date => dataByDate[date]);

    return chartData;
  };

  // Обработчик переключения школы
  const handleSchoolToggle = (schoolId) => {
    setSelectedSchools(prev => {
      if (prev.includes(schoolId)) {
        // Убираем школу из списка
        return prev.filter(id => id !== schoolId);
      } else {
        // Добавляем школу, но максимум 2
        if (prev.length < 2) {
          return [...prev, schoolId];
        }
        return prev;
      }
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (selectedSchools.length === 0) {
      setError('Выберите хотя бы одну школу');
      return;
    }

    if (!selectedTopic) {
      setError('Выберите топик');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const params = {};
      if (dateStart) params.date_start = dateStart;
      if (dateEnd) params.date_end = dateEnd;

      // Загружаем отзывы для всех выбранных школ
      const reviewsPromises = selectedSchools.map(schoolId =>
        axios.get(`${API_URL}/schools/${schoolId}/reviews`, { params })
          .then(response => ({ schoolId, reviews: response.data.reviews || [] }))
      );

      const results = await Promise.all(reviewsPromises);
      
      // Сохраняем отзывы по школам
      const newReviewsBySchool = {};
      results.forEach(({ schoolId, reviews }) => {
        newReviewsBySchool[schoolId] = reviews;
      });

      setReviewsBySchool(newReviewsBySchool);
    } catch (err) {
      setError('Ошибка загрузки отзывов: ' + err.message);
      setReviewsBySchool({});
    } finally {
      setLoading(false);
    }
  };

  const chartData = processReviewsData();

  return (
    <div className="App">
      <h1>Визуализация школ и отзывов</h1>
      
      <Filters
        schools={schools}
        topics={TOPICS}
        selectedSchools={selectedSchools}
        selectedTopic={selectedTopic}
        dateStart={dateStart}
        dateEnd={dateEnd}
        onSchoolToggle={handleSchoolToggle}
        onTopicChange={setSelectedTopic}
        onDateStartChange={setDateStart}
        onDateEndChange={setDateEnd}
        onSubmit={handleSubmit}
        loading={loading}
      />

      {error && <div className="error">{error}</div>}

      {chartData.length > 0 && (
        <Chart data={chartData} selectedSchools={selectedSchools} schools={schools} />
      )}

      {!loading && chartData.length === 0 && selectedSchools.length > 0 && selectedTopic && (
        <div className="no-data">Нет данных для отображения</div>
      )}
    </div>
  );
}

export default App;

