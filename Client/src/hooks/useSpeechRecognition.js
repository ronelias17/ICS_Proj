import { useState, useEffect, useRef, useCallback } from 'react';

// Hook for Hebrew speech recognition (Speech Recognition API)
export function useSpeechRecognition() {
  const recognitionSupported = Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);
  // Final clean transcript (only finals)
  const [finalTranscript, setFinalTranscript] = useState('');
  // Interim transcript
  const [interimTranscript, setInterimTranscript] = useState('');
  const [liveTranscript, setLiveTranscript] = useState('');
  // Is currently listening
  const [isListening, setIsListening] = useState(false);
  // Is user speaking right now
  const [isUserSpeaking, setIsUserSpeaking] = useState(false);
  const [error, setError] = useState(recognitionSupported ? null : 'Speech Recognition not supported in this browser');

  const recognitionRef = useRef(null);
  const silenceTimerRef = useRef(null);
  const accumulatedFinalRef = useRef(''); // Accumulates only finals
  const interimStableRef = useRef('');

  useEffect(() => {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!Recognition) {
      return;
    }

    const recognition = new Recognition();
    recognition.lang = 'he-IL';
    recognition.interimResults = true;
    recognition.continuous = false;

    // Recording started
    recognition.onstart = () => {
      setIsListening(true);
      setIsUserSpeaking(false);
      setError(null);
    };

    // User started speaking
    recognition.onspeechstart = () => {
      setIsUserSpeaking(true);
    };

    // User stopped speaking - waits 2.5s of silence then stops
    recognition.onspeechend = () => {
      setIsUserSpeaking(false);
      silenceTimerRef.current = setTimeout(() => {
        recognition.stop();
      }, 2500);
    };

    // Process recognition results
    recognition.onresult = (event) => {
      let newFinal = '';
      let newInterim = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const trans = result[0].transcript.trim();

        if (result.isFinal) {
          newFinal += (newFinal ? ' ' : '') + trans;
        } else {
          newInterim = trans;
        }
      }

      // Add only new final to accumulator
      if (newFinal) {
        accumulatedFinalRef.current += (accumulatedFinalRef.current ? ' ' : '') + newFinal;
        setFinalTranscript(accumulatedFinalRef.current);
        interimStableRef.current = '';
      }

      if (newInterim) {
        interimStableRef.current = mergeInterimText(interimStableRef.current, newInterim);
      }

      const visibleText = [accumulatedFinalRef.current, interimStableRef.current]
        .filter(Boolean)
        .join(' ')
        .replace(/\s+/g, ' ')
        .trim();

      setInterimTranscript(interimStableRef.current);
      setLiveTranscript(visibleText);
    };

    // Recording ended - cleanup
    recognition.onend = () => {
      clearTimeout(silenceTimerRef.current);
      setIsListening(false);
      setIsUserSpeaking(false);
      setInterimTranscript('');
      setLiveTranscript(accumulatedFinalRef.current);
      interimStableRef.current = '';
    };

    // Handle errors
    recognition.onerror = (event) => {
      setError(event.error);
      setIsListening(false);
    };

    recognitionRef.current = recognition;

    return () => {
      if (recognitionRef.current) recognitionRef.current.abort();
      clearTimeout(silenceTimerRef.current);
    };
  }, []);

  // Start new recording
  const startListening = useCallback(() => {
    if (recognitionRef.current && !isListening) {
      // Full reset for new session
      setFinalTranscript('');
      setInterimTranscript('');
      setLiveTranscript('');
      accumulatedFinalRef.current = '';
      interimStableRef.current = '';
      recognitionRef.current.start();
    }
  }, [isListening]);

  // Stop recording (finish what's there)
  const stopListening = useCallback(() => {
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop();
    }
  }, [isListening]);

  // Abort recording (cancel everything)
  const abortListening = useCallback(() => {
    if (recognitionRef.current && isListening) {
      recognitionRef.current.abort();
    }
  }, [isListening]);

  return {
    finalTranscript,      // Final clean text to send to backend (finals only)
    interimTranscript,    // Only temporary part (gray/italic)
    liveTranscript,
    isListening,
    isUserSpeaking,
    error,
    startListening,
    stopListening,
    abortListening,
  };
}

function mergeInterimText(previous, next) {
  const cleanPrevious = normalizeSpeechText(previous);
  const cleanNext = normalizeSpeechText(next);
  if (!cleanPrevious) return cleanNext;
  if (!cleanNext) return cleanPrevious;
  if (cleanNext.startsWith(cleanPrevious) || cleanPrevious.includes(cleanNext)) {
    return cleanNext.length >= cleanPrevious.length ? cleanNext : cleanPrevious;
  }

  const previousWords = cleanPrevious.split(' ');
  const nextWords = cleanNext.split(' ');
  for (let overlap = Math.min(previousWords.length, nextWords.length); overlap > 0; overlap--) {
    if (previousWords.slice(-overlap).join(' ') === nextWords.slice(0, overlap).join(' ')) {
      return [...previousWords, ...nextWords.slice(overlap)].join(' ');
    }
  }

  return `${cleanPrevious} ${cleanNext}`.trim();
}

function normalizeSpeechText(text) {
  return String(text || '').replace(/\s+/g, ' ').trim();
}
