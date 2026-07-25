import React from 'react';
import { ThumbsUp, ThumbsDown, RotateCcw } from 'lucide-react';
import './FeedbackButtons.css';

export function FeedbackButtons({ visible, submitted, selectedType, canSubmitFeedback, errorMessage, onFeedback, onReset }) {
    return (
        <div className={`feedback-buttons ${visible ? 'visible' : 'hidden'}`}>
            {canSubmitFeedback && (
                <div className="feedback-actions">
                    <button
                        className={`feedback-btn like-btn ${selectedType === 'positive' ? 'selected' : ''} ${submitted && selectedType !== 'positive' ? 'muted' : ''}`}
                        onClick={() => onFeedback?.('positive')}
                        aria-pressed={selectedType === 'positive'}
                        title="Good response"
                    >
                        <ThumbsUp size={20} color="#1f2937" strokeWidth={2} />
                    </button>
                    <button
                        className={`feedback-btn dislike-btn ${selectedType === 'negative' ? 'selected' : ''} ${submitted && selectedType !== 'negative' ? 'muted' : ''}`}
                        onClick={() => onFeedback?.('negative')}
                        aria-pressed={selectedType === 'negative'}
                        title="Bad response"
                    >
                        <ThumbsDown size={20} color="#1f2937" strokeWidth={2} />
                    </button>
                </div>
            )}

            {submitted && <div className="feedback-status">תודה על המשוב</div>}
            {errorMessage && <div className="feedback-error">{errorMessage}</div>}

            <button className="reset-btn" onClick={onReset}>
                <RotateCcw size={18} />
                <span>חזרה להתחלה</span>
            </button>
        </div>
    );
}
