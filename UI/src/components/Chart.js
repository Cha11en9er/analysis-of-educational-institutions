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

function Chart({ data, selectedSchools, schools }) {
  // Цвета для школ
  const colors = ['#4a90e2', '#ff6b6b', '#4ecdc4', '#ffe66d', '#95e1d3'];

  // Получаем названия школ для отображения
  const schoolNames = selectedSchools.map(schoolId => {
    const school = schools.find(s => String(s.school_id) === String(schoolId));
    return school ? (school.school_name || `Школа ${schoolId}`) : `Школа ${schoolId}`;
  });

  return (
    <div className="chart-container">
      <h2>Сравнение школ по динамике позитивных упоминаний</h2>
      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis 
            dataKey="date" 
            angle={-45}
            textAnchor="end"
            height={80}
          />
          <YAxis />
          <Tooltip />
          <Legend />
          {schoolNames.map((schoolName, index) => (
            <Line
              key={schoolName}
              type="monotone"
              dataKey={schoolName}
              stroke={colors[index % colors.length]}
              strokeWidth={2}
              name={schoolName}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default Chart;

