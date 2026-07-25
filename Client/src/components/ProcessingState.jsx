import React from 'react';
import { MessageView } from './MessageView';

export function ProcessingState({ userQuestion }) {
    return (
        <div className="voice-input-container">
            <MessageView message={userQuestion} isUserMessage={true} />

            <div className="processing-card" dir="rtl">
                <div className="graph-search" aria-hidden="true">
                    <span className="graph-line line-a" />
                    <span className="graph-line line-b" />
                    <span className="graph-line line-c" />
                    <span className="graph-node node-a" />
                    <span className="graph-node node-b" />
                    <span className="graph-node node-c" />
                    <span className="graph-node node-center" />
                    <span className="graph-scan" />
                </div>
                <div className="processing-copy">
                    <div className="processing-title">בודק את המידע</div>
                    <div className="processing-subtitle">מחפש תשובה מבוססת במקורות</div>
                </div>
                <div className="processing-meter" aria-hidden="true">
                    <span />
                </div>
            </div>
        </div>
    );
}
