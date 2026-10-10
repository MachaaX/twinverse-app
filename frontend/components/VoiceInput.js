/**
 * VoiceInput - Web Speech API for voice recognition
 */

export class VoiceInput {
  constructor() {
    this.recognition = null;
    this.isListening = false;
    this.isSupported = 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;

    if (this.isSupported) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      this.recognition = new SpeechRecognition();
      this.recognition.continuous = false;
      this.recognition.interimResults = true;
      this.recognition.lang = 'en-US';
      this.recognition.maxAlternatives = 1;
    }
  }

  /**
   * Start listening for voice input
   * @param {Object} callbacks - { onResult, onEnd, onError, onStart }
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

    console.log('[VoiceInput] Starting to listen...');
    this.isListening = true;

    // Handle results
    this.recognition.onresult = (event) => {
      const result = event.results[event.results.length - 1];
      const transcript = result[0].transcript;
      const isFinal = result.isFinal;

      console.log('[VoiceInput] Result:', transcript, 'Final:', isFinal);

      if (callbacks.onResult) {
        callbacks.onResult(transcript, isFinal);
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
   * Check if voice input is supported
   */
  isAvailable() {
    return this.isSupported;
  }
}

// Create singleton instance
export const voiceInput = new VoiceInput();
