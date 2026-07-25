import React from 'react';
import { MessageView } from './MessageView';
import { FeedbackButtons } from './FeedbackButtons';
import { useTypewriter } from '../hooks/useTypewriter';

export function ResponseState({ userQuestion, aiResponse, isComplete, isSpeaking, feedbackSubmitted, feedbackType, canSubmitFeedback, errorMessage, onFeedback, onReset }) {
    // Typewriter effect for AI response
    const { displayedText } = useTypewriter(aiResponse, 30);

    return (
        <>
            <div className="conversation-view">
                <MessageView message={userQuestion} isUserMessage={true} />
                <MessageView message={displayedText} isUserMessage={false} />
            </div>

            {isSpeaking && (
                <div className="speaking-status" dir="rtl" aria-live="polite">
                    <span className="speaking-bars" aria-hidden="true">
                        <span />
                        <span />
                        <span />
                    </span>
                    <span>מקריא תשובה...</span>
                </div>
            )}

            <FeedbackButtons
                visible={isComplete}
                submitted={feedbackSubmitted}
                selectedType={feedbackType}
                canSubmitFeedback={canSubmitFeedback}
                errorMessage={errorMessage}
                onFeedback={onFeedback}
                onReset={onReset}
            />
        </>
    );
}
