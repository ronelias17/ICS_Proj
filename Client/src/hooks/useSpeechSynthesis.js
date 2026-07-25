// Hook for text-to-speech (TTS) - natural Hebrew voice
import { useState, useEffect, useCallback } from 'react';

export function useSpeechSynthesis() {
  // Is currently speaking
  const [isSpeaking, setIsSpeaking] = useState(false);
  // Available voices list
  const [voices, setVoices] = useState([]);

  // Load available voices
  useEffect(() => {
    const loadVoices = () => {
      const availableVoices = window.speechSynthesis.getVoices();
      setVoices(availableVoices);
    };

    loadVoices();
    window.speechSynthesis.onvoiceschanged = loadVoices;

    return () => {
      window.speechSynthesis.cancel();
    };
  }, []);

  // Speak text in Hebrew
  const speak = useCallback((text) => {
    if (!text) return Promise.resolve();

    // Cancel previous speech if any
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'he-IL';

    // Hebrew voice (Google preferred)
    const hebrewVoice = voices.find(v => v.lang === 'he-IL') ||
      voices.find(v => v.lang.startsWith('he')) ||
      voices[0];

    if (hebrewVoice) {
      utterance.voice = hebrewVoice;
    }

    setIsSpeaking(true);

    return new Promise((resolve) => {
      utterance.onend = () => {
        setIsSpeaking(false);
        resolve();
      };
      utterance.onerror = () => {
        setIsSpeaking(false);
        resolve();
      };

      window.speechSynthesis.speak(utterance);
    });
  }, [voices]);

  // Cancel current speech
  const cancel = useCallback(() => {
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
  }, []);

  return {
    speak,
    cancel,
    isSpeaking,
  };
}
