import React from 'react';
import { VoiceButton } from './VoiceButton';
import { MessageView } from './MessageView';
import { X } from 'lucide-react';

export function ListeningState({ transcript, onCancel }) {
    return (
        <div className="voice-input-container">
            {/* Same button as start, but gray/disabled */}
            <VoiceButton isListening={true} />

            {/* Show user message with live transcript */}
            {transcript && (
                <MessageView
                    message={transcript}
                    isUserMessage={true}
                />
            )}

            <button className="cancel-button" onClick={onCancel}>
                <X size={16} style={{ marginLeft: '6px' }} />
                ביטול
            </button>
        </div>
    );
}
