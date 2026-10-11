/**
 * TTS Service - Web Speech API wrapper for text-to-speech
 * Provides audio generation with event callbacks for animation sync
 */

class TTSService {
  constructor() {
    this.synthesis = window.speechSynthesis;
    this.voice = null;
    this.speaking = false;
    this.currentUtterance = null;
    this.currentLanguage = 'en';

    // Initialize voices
    this.voices = [];
    this.loadVoices();

    // Reload voices when they change (some browsers load async)
    if (this.synthesis.onvoiceschanged !== undefined) {
      this.synthesis.onvoiceschanged = () => this.loadVoices();
    }
  }

  loadVoices() {
    this.voices = this.synthesis.getVoices();
    this.selectVoiceForLanguage(this.currentLanguage);
  }

  /**
   * Select appropriate voice for language
   */
  selectVoiceForLanguage(language) {
    // Map language codes to browser voice language prefixes
    const langMap = {
      'en': 'en',
      'es': 'es',
      'fr': 'fr',
      'de': 'de',
      'pt': 'pt',
      'it': 'it'
    };

    const langPrefix = langMap[language] || 'en';

    // Prefer natural-sounding voices for the language
    const preferred = this.voices.find(v =>
      v.lang.startsWith(langPrefix) && (
        v.name.includes('Natural') ||
        v.name.includes('Enhanced') ||
        v.name.includes('Premium')
      )
    );

    // Fallback to any voice in that language
    this.voice = preferred || this.voices.find(v => v.lang.startsWith(langPrefix)) || this.voices[0];

    console.log('[TTSService] Selected voice:', this.voice?.name, 'for language:', language);
  }

  /**
   * Set language for speech synthesis
   */
  setLanguage(language) {
    this.currentLanguage = language;
    this.selectVoiceForLanguage(language);
  }

  /**
   * Speak text with animation callbacks
   * @param {string} text - Text to speak
   * @param {object} callbacks - {onStart, onEnd, onWord, onError}
   * @param {string} emotion - Emotion hint: neutral, empathetic, concerned, cheerful
   * @returns {Promise} Resolves when speech completes
   */
  speak(text, callbacks = {}, emotion = 'neutral') {
    return new Promise((resolve, reject) => {
      if (!this.synthesis) {
        reject(new Error('Speech synthesis not available'));
        return;
      }

      // Cancel any ongoing speech
      this.stop();

      const utterance = new SpeechSynthesisUtterance(text);
      this.currentUtterance = utterance;

      // Set voice
      if (this.voice) {
        utterance.voice = this.voice;
      }

      // Adjust speech parameters based on emotion
      const emotionSettings = {
        neutral: { rate: 1.0, pitch: 1.0, volume: 1.0 },
        empathetic: { rate: 0.9, pitch: 1.1, volume: 0.9 },
        concerned: { rate: 0.85, pitch: 0.95, volume: 1.0 },
        cheerful: { rate: 1.1, pitch: 1.15, volume: 1.0 }
      };

      const settings = emotionSettings[emotion] || emotionSettings.neutral;
      utterance.rate = settings.rate;
      utterance.pitch = settings.pitch;
      utterance.volume = settings.volume;

      // Event handlers
      utterance.onstart = () => {
        this.speaking = true;
        if (callbacks.onStart) callbacks.onStart();
      };

      utterance.onend = () => {
        this.speaking = false;
        this.currentUtterance = null;
        if (callbacks.onEnd) callbacks.onEnd();
        resolve();
      };

      utterance.onerror = (event) => {
        this.speaking = false;
        this.currentUtterance = null;
        if (callbacks.onError) callbacks.onError(event);
        reject(event);
      };

      // Word boundary events for animation sync
      utterance.onboundary = (event) => {
        if (event.name === 'word' && callbacks.onWord) {
          callbacks.onWord(event);
        }
      };

      // Start speaking
      this.synthesis.speak(utterance);
    });
  }

  /**
   * Stop current speech
   */
  stop() {
    if (this.synthesis && this.speaking) {
      this.synthesis.cancel();
      this.speaking = false;
      this.currentUtterance = null;
    }
  }

  /**
   * Pause speech
   */
  pause() {
    if (this.synthesis && this.speaking) {
      this.synthesis.pause();
    }
  }

  /**
   * Resume paused speech
   */
  resume() {
    if (this.synthesis) {
      this.synthesis.resume();
    }
  }

  /**
   * Check if TTS is available
   */
  isAvailable() {
    return !!(window.speechSynthesis && window.SpeechSynthesisUtterance);
  }

  /**
   * Get available voices
   */
  getVoices() {
    return this.voices;
  }

  /**
   * Set voice by name
   */
  setVoice(voiceName) {
    const voice = this.voices.find(v => v.name === voiceName);
    if (voice) {
      this.voice = voice;
      return true;
    }
    return false;
  }
}

// Export singleton instance
export const ttsService = new TTSService();
