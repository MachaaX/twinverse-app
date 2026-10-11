/**
 * VoiceInput - Web Speech API for voice recognition
 */

export class VoiceInput {
  constructor() {
    this.recognition = null;
    this.isListening = false;
    this.isSupported = 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;
    this.currentLanguage = 'en-US';
    this.detectedLanguage = null;

    if (this.isSupported) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      this.recognition = new SpeechRecognition();
      this.recognition.continuous = false;
      this.recognition.interimResults = true;
      this.recognition.lang = this.currentLanguage;
      this.recognition.maxAlternatives = 1;
    }
  }

  /**
   * Set language for speech recognition
   * @param {string} language - Language code (e.g., 'en-US', 'es-ES', 'fr-FR')
   */
  setLanguage(language) {
    this.currentLanguage = language;
    if (this.recognition) {
      this.recognition.lang = language;
      console.log('[VoiceInput] Language set to:', language);
    }
  }

  /**
   * Get currently detected language
   */
  getDetectedLanguage() {
    return this.detectedLanguage || this.currentLanguage;
  }

  /**
   * Start listening for voice input
   * @param {Object} callbacks - { onResult, onEnd, onError, onStart, onLanguageDetected }
   */
  startListening(callbacks = {}) {
    if (!this.isSupported || !this.recognition) {
      console.error('[VoiceInput] Speech recognition not supported');
      if (callbacks.onError) callbacks.onError(new Error('Speech recognition not supported'));
      return;
    }

    if (this.isListening) {
      console.warn('[VoiceInput] Already listening');
      return;
    }

    console.log('[VoiceInput] Starting to listen in', this.currentLanguage);
    this.isListening = true;

    // Handle results
    this.recognition.onresult = (event) => {
      const result = event.results[event.results.length - 1];
      const transcript = result[0].transcript;
      const isFinal = result.isFinal;

      console.log('[VoiceInput] Result:', transcript, 'Final:', isFinal);

      // Detect language from transcript if final
      if (isFinal && transcript.trim()) {
        this.detectedLanguage = this.detectLanguageFromTranscript(transcript);
        console.log('[VoiceInput] Detected language:', this.detectedLanguage);

        if (callbacks.onLanguageDetected) {
          callbacks.onLanguageDetected(this.detectedLanguage);
        }
      }

      if (callbacks.onResult) {
        callbacks.onResult(transcript, isFinal, this.detectedLanguage);
      }
    };

    // Handle end
    this.recognition.onend = () => {
      console.log('[VoiceInput] Recognition ended');
      this.isListening = false;
      if (callbacks.onEnd) callbacks.onEnd();
    };

    // Handle errors
    this.recognition.onerror = (event) => {
      console.error('[VoiceInput] Recognition error:', event.error);
      this.isListening = false;
      if (callbacks.onError) callbacks.onError(event);
    };

    // Handle start
    this.recognition.onstart = () => {
      console.log('[VoiceInput] Recognition started');
      if (callbacks.onStart) callbacks.onStart();
    };

    try {
      this.recognition.start();
    } catch (error) {
      console.error('[VoiceInput] Failed to start:', error);
      this.isListening = false;
      if (callbacks.onError) callbacks.onError(error);
    }
  }

  /**
   * Stop listening
   */
  stopListening() {
    if (!this.recognition || !this.isListening) return;

    console.log('[VoiceInput] Stopping...');
    try {
      this.recognition.stop();
    } catch (error) {
      console.error('[VoiceInput] Error stopping:', error);
    }
    this.isListening = false;
  }

  /**
   * Detect language from transcript using heuristics
   * Returns language code for TTS (e.g., 'es', 'fr', 'de', 'en')
   */
  detectLanguageFromTranscript(text) {
    const lowerText = text.toLowerCase();

    // Spanish indicators
    const spanishPatterns = [
      /\b(el|la|los|las|un|una|es|está|estás|estoy|son|como|qué|por|para|con|si|no|sí|muy|pero|cuando|donde|aquí|ahí)\b/,
      /¿|¡/,
      /ción\b/
    ];

    // French indicators
    const frenchPatterns = [
      /\b(le|la|les|un|une|je|tu|il|elle|nous|vous|ils|elles|est|sont|avec|pour|dans|sur|sous|où|qui|quoi|comment)\b/,
      /ç/,
      /\bqu['']|d['']|l['']|n['']|s['']/
    ];

    // German indicators
    const germanPatterns = [
      /\b(der|die|das|den|dem|des|ein|eine|ich|du|er|sie|es|wir|ihr|ist|sind|haben|hat|mit|von|zu|auf|für)\b/,
      /ß/,
      /\b\w+(ung|heit|keit|schaft)\b/
    ];

    // Portuguese indicators
    const portuguesePatterns = [
      /\b(o|a|os|as|um|uma|é|está|são|estão|com|para|por|não|sim|muito|quando|onde|como|que)\b/,
      /ção\b/,
      /\b\w+ão\b/
    ];

    // Italian indicators
    const italianPatterns = [
      /\b(il|lo|la|i|gli|le|un|uno|una|è|sono|con|per|da|di|in|su|anche|quando|dove|come|che)\b/,
      /zione\b/,
      /\b\w+(mente|zione)\b/
    ];

    let spanishScore = 0;
    let frenchScore = 0;
    let germanScore = 0;
    let portugueseScore = 0;
    let italianScore = 0;

    spanishPatterns.forEach(pattern => {
      if (pattern.test(lowerText)) spanishScore++;
    });

    frenchPatterns.forEach(pattern => {
      if (pattern.test(lowerText)) frenchScore++;
    });

    germanPatterns.forEach(pattern => {
      if (pattern.test(lowerText)) germanScore++;
    });

    portuguesePatterns.forEach(pattern => {
      if (pattern.test(lowerText)) portugueseScore++;
    });

    italianPatterns.forEach(pattern => {
      if (pattern.test(lowerText)) italianScore++;
    });

    const maxScore = Math.max(spanishScore, frenchScore, germanScore, portugueseScore, italianScore);

    // Require at least 2 pattern matches to detect
    if (maxScore >= 2) {
      if (spanishScore === maxScore) return 'es';
      if (frenchScore === maxScore) return 'fr';
      if (germanScore === maxScore) return 'de';
      if (portugueseScore === maxScore) return 'pt';
      if (italianScore === maxScore) return 'it';
    }

    // Default to English
    return 'en';
  }

  /**
   * Check if voice input is supported
   */
  isAvailable() {
    return this.isSupported;
  }
}

// Create singleton instance
export const voiceInput = new VoiceInput();
