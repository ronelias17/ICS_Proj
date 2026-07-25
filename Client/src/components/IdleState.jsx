import React from 'react';
import { SuggestionChips } from './SuggestionChips';
import { VoiceButton } from './VoiceButton';

export function IdleState({ suggestions, suggestionRotationKey, suggestionsRotating, onStartTalking, onSuggestionClick }) {
    return (
        <div className="idle-stage">
            <div className="idle-heading" dir="rtl">
                <h1>מה תרצו לדעת?</h1>
            </div>
            <SuggestionChips
                suggestions={suggestions}
                rotationKey={suggestionRotationKey}
                rotating={suggestionsRotating}
                visible={true}
                onSuggestionClick={onSuggestionClick}
            />
            <VoiceButton onClick={onStartTalking} />
            <div className="voice-hint" dir="rtl">לחצו ושאלו בקול</div>
        </div>
    );
}
