import React from 'react';

const KIND_LABELS = {
  sport_do: 'Спортивное учреждение',
  arts_do: 'Творческое учреждение',
  preschool: 'Детский сад',
  internat_cadet: 'Кадетская школа / интернат',
  spo: 'СПО',
  vuz: 'Вуз',
  general: 'Школа',
  other: 'Иное',
};

/**
 * Нижняя карточка учреждения (единый вид со школьной): имя, тип, адрес,
 * телефон, сайт. Учреждения не имеют школьного рейтинга.
 */
export default function InstitutionBottomCard({ institution, onClose }) {
  if (!institution) return null;
  const kind = KIND_LABELS[institution.kind] || 'Учреждение';
  return (
    <div className="school-bottom-card">
      <button type="button" className="bottom-card-close" onClick={onClose} aria-label="Закрыть карточку">✕</button>
      <div className="bottom-card-head">
        <div className="bottom-card-title">
          <div className="bottom-card-name">{institution.name}</div>
          <div className="bottom-card-address">{institution.address || 'Адрес не указан'}</div>
        </div>
      </div>
      <div className="bottom-card-chips">
        <span className="chip">{kind}</span>
        {institution.city && <span className="chip">{institution.city}</span>}
      </div>
      <div className="bottom-card-actions">
        {institution.phone && <span className="inst-phone">{institution.phone}</span>}
        {institution.site && (
          <a href={institution.site} target="_blank" rel="noopener noreferrer" className="bottom-link">
            Сайт учреждения
          </a>
        )}
      </div>
    </div>
  );
}
