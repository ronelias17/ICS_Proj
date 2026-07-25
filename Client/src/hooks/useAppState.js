import { useState, useEffect, useRef, useCallback } from 'react';
import { useSpeechRecognition } from './useSpeechRecognition';
import { useSpeechSynthesis } from './useSpeechSynthesis';
import { useChatAPI } from './useChatAPI';
import { useSuggestions } from './useSuggestions';
import { useFeedback } from './useFeedback';

// App states
const STATES = {
    IDLE: 'idle',
    LISTENING: 'listening',
    PROCESSING: 'processing',
    RESPONDING: 'responding',
    COMPLETE: 'complete',
    ERROR: 'error'
};

export function useAppState() {
    const [appState, setAppState] = useState(STATES.IDLE);
    const [userQuestion, setUserQuestion] = useState('');
    const [aiResponse, setAiResponse] = useState('');
    const [answerId, setAnswerId] = useState(null);
    const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
    const [feedbackType, setFeedbackType] = useState(null);
    const [errorMessage, setErrorMessage] = useState('');
    const timeoutRef = useRef(null);

    // Hooks - suggestions fetched once and persisted here!
    const { visibleSuggestions, rotationKey, isRotating } = useSuggestions({ rotationEnabled: appState === STATES.IDLE });

    const {
        finalTranscript,
        interimTranscript,
        liveTranscript,
        isListening,
        startListening,
        abortListening,
    } = useSpeechRecognition();

    const { speak, cancel: cancelSpeech } = useSpeechSynthesis();
    const { fetchResponse } = useChatAPI();
    const { submitFeedback } = useFeedback();

    const submitQuestion = useCallback(async (questionText) => {
        const cleanQuestion = questionText.trim();
        if (!cleanQuestion) {
            return;
        }

        setUserQuestion(cleanQuestion);
        setAiResponse('');
        setAnswerId(null);
        setFeedbackSubmitted(false);
        setFeedbackType(null);
        setErrorMessage('');
        setAppState(STATES.PROCESSING);

        try {
            const result = await fetchResponse(cleanQuestion);
            setAnswerId(result.id);
            setAiResponse(result.answer);
            setAppState(STATES.RESPONDING);
            await speak(result.answer);
            setAppState((current) => current === STATES.RESPONDING ? STATES.COMPLETE : current);
        } catch {
            setAiResponse('כרגע לא ניתן להתחבר לשירות. נסו שוב בעוד רגע.');
            setErrorMessage('');
            setAppState(STATES.ERROR);
        }
    }, [fetchResponse, speak]);

    // Handle "Start Talking" button
    const handleStartTalking = useCallback(() => {
        setAppState(STATES.LISTENING);
        setUserQuestion('');
        setAiResponse('');
        setAnswerId(null);
        setFeedbackSubmitted(false);
        setFeedbackType(null);
        setErrorMessage('');
        startListening();
    }, [startListening]);

    // Handle suggestion chip click - auto-activate
    const handleSuggestionClick = useCallback((suggestionText) => {
        submitQuestion(suggestionText);
    }, [submitQuestion]);

    // Handle cancel during listening
    const handleCancel = useCallback(() => {
        abortListening();
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
        }
        cancelSpeech();
        setAppState(STATES.IDLE);
        setUserQuestion('');
        setErrorMessage('');
    }, [abortListening, cancelSpeech]);

    // Handle reset
    const handleReset = useCallback(() => {
        cancelSpeech();
        setAppState(STATES.IDLE);
        setUserQuestion('');
        setAiResponse('');
        setAnswerId(null);
        setFeedbackSubmitted(false);
        setFeedbackType(null);
        setErrorMessage('');
    }, [cancelSpeech]);

    // Handle feedback
    const handleFeedback = useCallback(async (type) => {
        if (feedbackSubmitted) {
            return;
        }
        try {
            await submitFeedback(answerId, type);
            setFeedbackSubmitted(true);
            setFeedbackType(type);
        } catch {
            setErrorMessage('לא ניתן לשמור את המשוב כרגע.');
        }
    }, [answerId, feedbackSubmitted, submitFeedback]);

    // When user finishes speaking
    useEffect(() => {
        if (appState === STATES.LISTENING && finalTranscript && !isListening) {
            const timer = setTimeout(() => submitQuestion(finalTranscript), 0);
            return () => clearTimeout(timer);
        }
        return undefined;
    }, [appState, finalTranscript, isListening, submitQuestion]);

    // Timeout when listening with no speech
    useEffect(() => {
        if (appState === STATES.LISTENING) {
            timeoutRef.current = setTimeout(() => {
                if (!finalTranscript) {
                    abortListening();
                    setAppState(STATES.IDLE);
                }
            }, 10000);
        }

        return () => {
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }
        };
    }, [appState, finalTranscript, abortListening]);

    return {
        // State
        appState,
        STATES,
        userQuestion,
        aiResponse,
        suggestions: visibleSuggestions,
        suggestionRotationKey: rotationKey,
        suggestionsRotating: isRotating,
        transcript: liveTranscript || finalTranscript || interimTranscript,
        isComplete: appState === STATES.COMPLETE,
        isSpeaking: appState === STATES.RESPONDING,
        feedbackSubmitted,
        feedbackType,
        canSubmitFeedback: Boolean(answerId),
        errorMessage,

        // Handlers
        handleStartTalking,
        handleSuggestionClick,
        handleCancel,
        handleReset,
        handleFeedback,
    };
}
