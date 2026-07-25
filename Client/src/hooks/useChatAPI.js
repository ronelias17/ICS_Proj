import { useState, useCallback } from 'react';
import { API_BASE_URL } from '../config/api';

export function useChatAPI() {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);

    const fetchResponse = useCallback(async (userText) => {
        setIsLoading(true);
        setError(null);

        try {
            const response = await fetch(`${API_BASE_URL}/api/ask`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: userText })
            });
            const data = await response.json();
            if (!response.ok && !data.answer) {
                throw new Error(data.detail || 'Request failed');
            }
            return {
                id: data.id || null,
                answer: data.answer || ''
            };
        } catch (err) {
            setError(err.message);
            console.error('Error fetching response:', err);
            throw err;
        } finally {
            setIsLoading(false);
        }
    }, []);

    return {
        fetchResponse,
        isLoading,
        error
    };
}
