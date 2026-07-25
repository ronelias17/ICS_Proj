import React from 'react';
import './SuggestionChips.css';

export function SuggestionChips({ suggestions = [], rotationKey = 0, rotating = false, visible, onSuggestionClick }) {
  if (!suggestions || suggestions.length === 0) {
    return null; // Don't show if no suggestions
  }

  return (
    <div key={rotationKey} className={`suggestion-chips ${visible ? 'visible' : 'hidden'} ${rotating ? 'rotating' : ''}`}>
      {suggestions.map((suggestion, index) => {
        const id = typeof suggestion === 'string' ? suggestion : suggestion.id;
        const question = typeof suggestion === 'string' ? suggestion : suggestion.question;
        return (
        <button
          key={id || `${question}-${index}`}
          className="suggestion-chip"
          style={{ '--chip-index': index }}
          onClick={() => onSuggestionClick?.(question)}
        >
          {question}
        </button>
      )})}
    </div>
  );
}
