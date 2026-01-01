import React from 'react';
import './SchoolSelector.css';

function SchoolSelector({ schools, selectedSchool, onSchoolChange, onSubmit, loading }) {
  return (
    <form className="school-selector" onSubmit={onSubmit}>
      <div className="selector-group">
        <label htmlFor="school">Школа:</label>
        <select
          id="school"
          value={selectedSchool}
          onChange={(e) => onSchoolChange(e.target.value)}
          required
        >
          <option value="">Выберите школу</option>
          {schools.map(school => (
            <option key={school.school_id} value={school.school_id}>
              {school.school_name || `Школа ${school.school_id}`}
            </option>
          ))}
        </select>
      </div>

      <button type="submit" disabled={loading} className="submit-btn">
        {loading ? 'Загрузка...' : 'Загрузить данные'}
      </button>
    </form>
  );
}

export default SchoolSelector;

