import React from 'react';
import { Maximize2, Minimize2 } from 'lucide-react';
import { useAppState } from '../hooks/useAppState';
import { useFullscreen } from '../hooks/useFullscreen';
import { IdleState } from './IdleState';
import { ListeningState } from './ListeningState';
import { ProcessingState } from './ProcessingState';
import { ResponseState } from './ResponseState';
import ruppinLogo from '../assets/ruppin-logo-transparent.png';
import './Home.css';

export function Home() {
    const {
        appState,
        STATES,
        userQuestion,
        aiResponse,
        suggestions,
        suggestionRotationKey,
        suggestionsRotating,
        transcript,
        isComplete,
        isSpeaking,
        feedbackSubmitted,
        feedbackType,
        canSubmitFeedback,
        errorMessage,
        handleStartTalking,
        handleSuggestionClick,
        handleCancel,
        handleReset,
        handleFeedback,
    } = useAppState();

    const { isFullscreen, isSupported: isFullscreenSupported, toggleFullscreen } = useFullscreen();

    return (
        <div className="home-container">
            {isFullscreenSupported && (
                <button
                    type="button"
                    className={`fullscreen-toggle ${isFullscreen ? 'fullscreen-active' : ''}`}
                    onClick={toggleFullscreen}
                    aria-label={isFullscreen ? 'יציאה ממסך מלא' : 'מסך מלא'}
                    title={isFullscreen ? 'יציאה ממסך מלא' : 'מסך מלא'}
                >
                    {isFullscreen ? <Minimize2 size={20} /> : <Maximize2 size={20} />}
                </button>
            )}
            <header className="brand-header" dir="rtl" aria-label="המרכז האקדמי רופין">
                <img src={ruppinLogo} alt="" className="brand-logo" />
                <span className="brand-name">המרכז האקדמי רופין</span>
            </header>

            {appState === STATES.IDLE && (
                <IdleState
                    suggestions={suggestions}
                    suggestionRotationKey={suggestionRotationKey}
                    suggestionsRotating={suggestionsRotating}
                    onStartTalking={handleStartTalking}
                    onSuggestionClick={handleSuggestionClick}
                />
            )}

            {appState === STATES.LISTENING && (
                <ListeningState
                    transcript={transcript}
                    onCancel={handleCancel}
                />
            )}

            {appState === STATES.PROCESSING && (
                <ProcessingState userQuestion={userQuestion} />
            )}

            {(appState === STATES.RESPONDING || appState === STATES.COMPLETE) && (
                <ResponseState
                    userQuestion={userQuestion}
                    aiResponse={aiResponse}
                    isComplete={isComplete}
                    isSpeaking={isSpeaking}
                    feedbackSubmitted={feedbackSubmitted}
                    feedbackType={feedbackType}
                    canSubmitFeedback={canSubmitFeedback}
                    errorMessage={errorMessage}
                    onFeedback={handleFeedback}
                    onReset={handleReset}
                />
            )}

            {appState === STATES.ERROR && (
                <ResponseState
                    userQuestion={userQuestion}
                    aiResponse={aiResponse}
                    isComplete={true}
                    isSpeaking={false}
                    feedbackSubmitted={false}
                    feedbackType={null}
                    canSubmitFeedback={false}
                    errorMessage={errorMessage}
                    onReset={handleReset}
                />
            )}
        </div>
    );
}
