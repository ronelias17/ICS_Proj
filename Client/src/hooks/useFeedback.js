import { useState, useCallback } from 'react';
import { API_BASE_URL } from '../config/api';

export function useFeedback() {
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState(null);

    const submitFeedback = useCallback(async (responseId, type) => {
        setIsSubmitting(true);
        setError(null);

        try {
            if (!responseId) {
                throw new Error('Missing answer id');
            }

            const response = await fetch(`${API_BASE_URL}/api/feedback`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id: responseId,
                    feedback_positive: type === 'positive'
                })
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.detail || 'Could not submit feedback');
            }
            return data;
        } catch (err) {
            setError(err.message);
            console.error('Error submitting feedback:', err);
            throw err;
        } finally {
            setIsSubmitting(false);
        }
    }, []);

    return {
        submitFeedback,
        isSubmitting,
        error
    };
}
