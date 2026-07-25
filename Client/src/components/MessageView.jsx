import React from 'react';
import { User, Bot } from 'lucide-react';
import './MessageView.css';

export function MessageView({ message, isUserMessage = true }) {
    return (
            <div className={`message ${isUserMessage ? 'user-message' : 'ai-message'}`}>
                <div className={`message-icon ${isUserMessage ? 'user-icon' : 'ai-icon'}`}>
                    {isUserMessage ? <User size={20} /> : <Bot size={20} />}
                </div>
                <div className="message-content" dir="rtl">
                    {message}
                </div>
            </div>
    );
}
