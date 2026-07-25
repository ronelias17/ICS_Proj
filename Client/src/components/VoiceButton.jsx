import React from 'react';
import { Mic } from 'lucide-react';
import './VoiceButton.css';

export function VoiceButton({ isListening = false, onClick }) {
    return (
        <button
            className={`voice-button ${isListening ? 'listening' : ''}`}
            onClick={onClick}
            disabled={isListening}
        >
            <Mic size={28} />
        </button>
    );
}
