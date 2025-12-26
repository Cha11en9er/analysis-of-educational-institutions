import React from 'react';
import './Filters.css';

function Filters({
  schools,
  topics,
  selectedSchools,
  selectedTopic,
  dateStart,
  dateEnd,
  onSchoolToggle,
  onTopicChange,
  onDateStartChange,
  onDateEndChange,
  onSubmit,
  loading
}) {
  const handleSchoolToggle = (schoolId) => {
    onSchoolToggle(schoolId);
  };

  return (
    <form className="filters" onSubmit={onSubmit}>
      <div className="filter-group school-list">
        <label>Школы для сравнения (макс. 2):</label>
        <div className="school-checkboxes">
          {schools.map(school => {
            const isChecked = selectedSchools.includes(school.school_id);
            const isDisabled = !isChecked && selectedSchools.length >= 2;
            const schoolName = school.school_name || `Школа ${school.school_id}`;
            
            return (
              <label key={school.school_id} className="school-checkbox-label">
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={() => handleSchoolToggle(school.school_id)}
                  disabled={isDisabled}
                />
                <span className={isDisabled ? 'disabled' : ''}>{schoolName}</span>
              </label>
            );
          })}
        </div>
      </div>

      <div className="filter-group">
        <label htmlFor="topic">Топик:</label>
        <select
          id="topic"
          value={selectedTopic}
          onChange={(e) => onTopicChange(e.target.value)}
          required
        >
          <option value="">Выберите топик</option>
          {topics.map(topic => (
            <option key={topic} value={topic}>
              {topic.charAt(0).toUpperCase() + topic.slice(1)}
            </option>
          ))}
        </select>
      </div>

      <div className="filter-group">
        <label htmlFor="dateStart">Дата от:</label>
        <input
          type="date"
          id="dateStart"
          value={dateStart}
          onChange={(e) => onDateStartChange(e.target.value)}
        />
      </div>

      <div className="filter-group">
        <label htmlFor="dateEnd">Дата до:</label>
        <input
          type="date"
          id="dateEnd"
          value={dateEnd}
          onChange={(e) => onDateEndChange(e.target.value)}
        />
      </div>

      <button type="submit" disabled={loading} className="submit-btn">
        {loading ? 'Загрузка...' : 'Подтвердить'}
      </button>
    </form>
  );
}

export default Filters;

