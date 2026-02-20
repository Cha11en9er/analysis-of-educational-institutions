import React, { useEffect } from 'react';

export default function Toast({ message, type = 'info', onClose, autoHideMs = 5000 }) {
  useEffect(() => {
    if (!autoHideMs || !onClose) return;
    const t = setTimeout(onClose, autoHideMs);
    return () => clearTimeout(t);
  }, [autoHideMs, onClose]);

  if (!message) return null;

  return (
    <div className={`toast toast-${type}`} role="alert">
      {message}
    </div>
  );
}
