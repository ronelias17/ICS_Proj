import { useState, useCallback, useEffect } from 'react';
import { API_BASE_URL } from '../config/api';

const VISIBLE_SUGGESTIONS = 4;
const ROTATION_INTERVAL_MS = 20000;
const ROTATION_ANIMATION_MS = 950;

export function useSuggestions({ rotationEnabled = true } = {}) {
    const [suggestions, setSuggestions] = useState([]);
    const [startIndex, setStartIndex] = useState(0);
    const [rotationKey, setRotationKey] = useState(0);
    const [isRotating, setIsRotating] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);

    const fetchSuggestions = useCallback(async () => {
        setIsLoading(true);
        setError(null);

        try {
            const response = await fetch(`${API_BASE_URL}/api/suggestions`);
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.detail || 'Could not load suggestions');
            }
            setSuggestions(data.suggestions || []);
            setStartIndex(0);
            setRotationKey(0);
        } catch (err) {
            setError(err.message);
            console.error('Error fetching suggestions:', err);
        } finally {
            setIsLoading(false);
        }
    }, []);

    // Auto-fetch on mount
    useEffect(() => {
        fetchSuggestions();
    }, [fetchSuggestions]);

    useEffect(() => {
        if (!rotationEnabled || suggestions.length <= VISIBLE_SUGGESTIONS) {
            return undefined;
        }

        const timer = setInterval(() => {
            setIsRotating(true);
            window.setTimeout(() => {
                setStartIndex((current) => (current - 1 + suggestions.length) % suggestions.length);
                setRotationKey((current) => current + 1);
                setIsRotating(false);
            }, ROTATION_ANIMATION_MS);
        }, ROTATION_INTERVAL_MS);

        return () => clearInterval(timer);
    }, [rotationEnabled, suggestions.length]);

    const visibleSuggestions = suggestions.length <= VISIBLE_SUGGESTIONS
        ? suggestions
        : Array.from({ length: VISIBLE_SUGGESTIONS }, (_, offset) => {
            const index = (startIndex + offset) % suggestions.length;
            return suggestions[index];
        });

    return {
        suggestions,
        visibleSuggestions,
        rotationKey,
        isRotating,
        isLoading,
        error,
        refetch: fetchSuggestions
    };
}
