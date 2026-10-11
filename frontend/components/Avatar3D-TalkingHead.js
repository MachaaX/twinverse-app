/**
 * Avatar3D Component - Using TalkingHead.js Library
 * Loads and renders 3D GLB models with built-in lip-sync
 */

import { ttsService } from './TTSService.js';

export class Avatar3D {
  constructor(containerElement, config = {}) {
    this.container = containerElement;
    this.config = {
      name: config.name || 'Patient',
      gender: config.gender || 'neutral',
      patientId: config.patientId || null,
      modelPath: config.modelPath || null,
      imageUrl: config.imageUrl || null,
      enableLipSync: config.enableLipSync !== false,
      language: config.language || 'en',
      ...config
    };

    this.isInitialized = false;
    this.isSpeaking = false;
    this.head = null;
    this.subtitleElement = null;
    this.currentLanguage = 'en';

    this.init();
  }

  async init() {
    // Create container structure with subtitle overlay
    this.container.innerHTML = `
      <div class="avatar-3d-wrapper">
        <div id="avatar-view-3d" style="width:100%;height:100%;min-height:500px;"></div>
        <div class="avatar-subtitle-overlay">
          <div class="avatar-subtitle" id="avatar-subtitle"></div>
        </div>
        <div class="avatar-status-3d">
          <div class="speaking-indicator-3d" style="display: none;">
            <span class="pulse-dot"></span>
            <span class="status-text">Speaking...</span>
          </div>
        </div>
        <div class="avatar-loading-3d">
          <span class="spinner"></span>
          <span>Loading 3D avatar...</span>
        </div>
      </div>
    `;

    this.viewElement = this.container.querySelector('#avatar-view-3d');
    this.subtitleElement = this.container.querySelector('#avatar-subtitle');
    this.loadingElement = this.container.querySelector('.avatar-loading-3d');
    this.indicatorElement = this.container.querySelector('.speaking-indicator-3d');

    // Determine model path
    const modelPath = this.config.modelPath || this.getModelPath();

    console.log('[Avatar3D] Starting initialization...');
    console.log('[Avatar3D] Config:', {
      name: this.config.name,
      gender: this.config.gender,
      patientId: this.config.patientId,
      modelPath: modelPath
    });

    try {
      // Load TalkingHead library (local copy for CSP compliance)
      console.log('[Avatar3D] Loading TalkingHead library...');
      const { TalkingHead } = await import('/lib/talkinghead.mjs');
      console.log('[Avatar3D] ✓ TalkingHead library loaded');

      console.log('[Avatar3D] Creating TalkingHead instance...');
      // Create TalkingHead instance with lipsync modules (critical!)
      // Support multiple languages for lip-sync
      this.head = new TalkingHead(this.viewElement, {
        ttsEndpoint: '/api/tts',
        lipsyncModules: ['en', 'es', 'fr', 'de', 'pt', 'it'],
        cameraView: 'upper',
        audioVolume: 1.0  // Ensure volume is set
      });
      console.log('[Avatar3D] ✓ TalkingHead instance created');

      console.log('[Avatar3D] Loading avatar model from:', modelPath);

      // Determine body based on gender (case-insensitive)
      const gender = (this.config.gender || '').toLowerCase();
      const bodyType = gender === 'male' ? 'M' : 'F';
      console.log('[Avatar3D] Body type:', bodyType, '(from gender:', this.config.gender + ')');

      // Load the avatar - match working implementation
      await this.head.showAvatar({
        url: modelPath,
        body: bodyType,
        avatarMood: 'neutral',
        lipsyncLang: 'en'
      });

      console.log('[Avatar3D] ✓✓✓ Avatar loaded successfully!');

      // Note: AudioContext will be suspended until user interaction
      // It will be resumed automatically on first button click
      if(this.head.audioCtx && this.head.audioCtx.state === 'suspended'){
        console.log('[Avatar3D] AudioContext suspended - will resume on user interaction');
      }

      // Force renderer to resize to container dimensions
      const width = this.viewElement.offsetWidth || this.container.offsetWidth;
      const height = this.viewElement.offsetHeight || this.container.offsetHeight;

      console.log('[Avatar3D] Container dimensions:', width, 'x', height);

      if (width > 0 && height > 0 && this.head.renderer) {
        this.head.renderer.setSize(width, height);
        console.log('[Avatar3D] Renderer resized to:', width, 'x', height);
      } else {
        console.warn('[Avatar3D] Cannot resize - dimensions:', width, height);
      }

      this.hideLoading();
      this.isInitialized = true;

    } catch (error) {
      console.error('[Avatar3D] ✗✗✗ FAILED to load 3D avatar');
      console.error('[Avatar3D] Error:', error.message);
      console.error('[Avatar3D] Error stack:', error.stack);
      console.error('[Avatar3D] Model path attempted:', modelPath);
      console.error('[Avatar3D] Full error object:', error);
      this.showFallback();
    }
  }

  /**
   * Get model path based on patient configuration
   */
  getModelPath() {
    // Normalize gender to lowercase for comparison
    const gender = (this.config.gender || '').toLowerCase();

    const genderMap = {
      'male': 'male_default',
      'female': 'female_default',
      'non-binary': 'female_default'  // Use female as fallback
    };

    const modelName = genderMap[gender] || 'female_default';
    console.log('[Avatar3D] Gender:', this.config.gender, '→ Model:', modelName);
    return `/public/models/${modelName}.glb`;
  }

  /**
   * Set language for speech synthesis
   * @param {string} language - Language code (e.g., 'en', 'es', 'fr')
   */
  setLanguage(language) {
    this.currentLanguage = language;
    console.log('[Avatar3D] Language set to:', language);
  }

  /**
   * Get voice ID based on language and gender
   */
  getVoiceForLanguage(language, gender) {
    const voiceMap = {
      'en': {
        'male': 'Matthew',
        'female': 'Joanna'
      },
      'es': {
        'male': 'Miguel',
        'female': 'Lucia'
      },
      'fr': {
        'male': 'Mathieu',
        'female': 'Lea'
      },
      'de': {
        'male': 'Hans',
        'female': 'Vicki'
      },
      'pt': {
        'male': 'Ricardo',
        'female': 'Vitoria'
      },
      'it': {
        'male': 'Giorgio',
        'female': 'Bianca'
      }
    };

    const genderKey = (gender || '').toLowerCase() === 'male' ? 'male' : 'female';
    return voiceMap[language]?.[genderKey] || voiceMap['en'][genderKey];
  }

  /**
   * Speak text with lip-sync and subtitles using Amazon Polly
   * @param {string} text - Text to speak
   * @param {string} emotion - Emotion for mood
   * @param {string} language - Language code (optional, uses current language if not provided)
   */
  async speak(text, emotion = 'neutral', language = null) {
    // Use provided language or current language
    const speakLanguage = language || this.currentLanguage;
    console.log('[Avatar3D] Speaking in language:', speakLanguage);
    if (!this.isInitialized || !this.head) {
      console.warn('[Avatar3D] Not initialized, falling back to TTS only');
      if (ttsService.isAvailable()) {
        await ttsService.speak(text, {}, emotion);
      }
      return;
    }

    this.isSpeaking = true;
    this.showSpeakingIndicator(true);
    this.showSubtitle(text);

    try {
      // Set avatar mood based on emotion
      const moodMap = {
        'neutral': 'neutral',
        'empathetic': 'fear',
        'concerned': 'sad',
        'cheerful': 'happy',
        'worried': 'fear',
        'pain': 'sad'
      };
      const mood = moodMap[emotion] || 'neutral';

      try {
        this.head.setMood(mood);
      } catch (moodErr) {
        console.warn('[Avatar3D] Could not set mood:', moodErr);
      }

      this.onSpeechStart();

      // Get audio and timing from Amazon Polly
      console.log('[Avatar3D] Fetching audio from Polly TTS...');

      // Select voice based on language and gender
      const gender = this.config.gender;
      const voice = this.getVoiceForLanguage(speakLanguage, gender);
      console.log('[Avatar3D] Using voice:', voice, 'for language:', speakLanguage, 'and gender:', gender);

      const response = await fetch('/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, voice, language: speakLanguage })
      });

      if (!response.ok) {
        throw new Error(`TTS request failed: ${response.status}`);
      }

      const data = await response.json();

      // Check if we got audio data (Polly is available)
      if (data.audioContent && data.audioContent.length > 0) {
        console.log('[Avatar3D] Using Polly TTS with lip-sync');
        console.log('[Avatar3D] Words:', data.words?.length || 0);

        // Decode base64 audio to ArrayBuffer
        const binaryString = atob(data.audioContent);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
          bytes[i] = binaryString.charCodeAt(i);
        }
        const arrayBuffer = bytes.buffer;

        // Decode MP3 to AudioBuffer using TalkingHead's audio context
        // This ensures audio plays through the same context TalkingHead uses
        const audioBuffer = await this.head.audioCtx.decodeAudioData(arrayBuffer);

        console.log('[Avatar3D] Audio decoded, duration:', audioBuffer.duration, 'seconds');

        // Use TalkingHead's speakAudio for precise lip-sync
        // Use appropriate lip-sync language
        const lipsyncLang = speakLanguage === 'pt' ? 'pt' : speakLanguage;
        console.log('[Avatar3D] Using lipsyncLang:', lipsyncLang);

        await this.head.speakAudio({
          audio: audioBuffer,  // AudioBuffer object
          words: data.words || [],
          wtimes: data.wtimes || [],
          wdurations: data.wdurations || [],
          lipsyncLang: lipsyncLang
        });

        console.log('[Avatar3D] ✓ Polly speech with lip-sync complete');
      } else {
        // Polly unavailable: browser voice, with lip-sync driven by estimated word timings
        console.log('[Avatar3D] Polly unavailable, using browser TTS with estimated lip-sync');
        await this.speakWithBrowserVoice(text, emotion, speakLanguage);
      }

      this.onSpeechEnd();

    } catch (error) {
      console.error('[Avatar3D] Speech error:', error);

      // Fallback to browser TTS on error
      try {
        console.log('[Avatar3D] Falling back to browser TTS');
        await this.speakWithBrowserVoice(text, emotion, speakLanguage);
      } catch (fallbackErr) {
        console.error('[Avatar3D] Fallback TTS also failed:', fallbackErr);
      }

      this.onSpeechEnd();
    }
  }

  /**
   * Browser speech has no audio data or word timings up front, so estimate when
   * each word is spoken (syllables and punctuation pauses), start the mouth when
   * the voice starts, and re-sync to the spoken word if the estimate drifts.
   * Lip-sync from Amazon Polly (server /api/tts) is more precise when available.
   */
  async speakWithBrowserVoice(text, emotion = 'neutral', language = 'en') {
    if (!ttsService.isAvailable()) return;
    const rate = { empathetic: 0.9, concerned: 0.85, cheerful: 1.1 }[emotion] || 1.0;

    // Set voice language for browser TTS
    ttsService.setLanguage(language);
    const tokens = [...text.matchAll(/\S+/g)].map(m => ({ word: m[0], index: m.index }));
    const syllables = w => Math.max(1, (w.toLowerCase().replace(/[^a-z]/g, '').match(/[aeiouy]+/g) || []).length);
    const pause = w => /[.!?]["')\]]*$/.test(w) ? 380 : /[,;:]["')\]]*$/.test(w) ? 180 : 0;
    let plan = null;

    const schedule = from => {
      if (!this.head) return;
      const words = [], wtimes = [], wdurations = [], starts = {};
      let t = 0;
      for (let i = from; i < tokens.length; i++) {
        const d = (syllables(tokens[i].word) * 190 + 50) / rate;
        const clean = tokens[i].word.replace(/[^\w'-]/g, '');
        starts[i] = t;
        if (clean) { words.push(clean); wtimes.push(t); wdurations.push(d); }
        t += d + pause(tokens[i].word) / rate;
      }
      try { this.head.stopSpeaking(); } catch (e) { /* nothing queued yet */ }
      if (words.length) {
        // TalkingHead only times visemes against an audio clip; without one it fires them
        // all at once. A silent clip of the estimated length gives the mouth a clock while
        // the browser voice does the actual speaking.
        const ctx = this.head.audioCtx;
        if (ctx.state === 'suspended') ctx.resume().catch(() => {});
        const silent = ctx.createBuffer(1, Math.max(1, Math.ceil(ctx.sampleRate * (t + 200) / 1000)), ctx.sampleRate);
        const lipsyncLang = language === 'pt' ? 'pt' : language;
        this.head.speakAudio({ audio: silent, words, wtimes, wdurations }, { lipsyncLang });
      }
      plan = { started: performance.now(), starts };
    };

    try {
      await ttsService.speak(text, {
        onStart: () => schedule(0),
        onWord: event => {
          if (!plan) return;
          let i = tokens.findIndex(tok => tok.index >= event.charIndex);
          if (i < 0) i = tokens.length - 1;
          if (!(i in plan.starts)) return;
          const drift = (performance.now() - plan.started) - plan.starts[i];
          if (Math.abs(drift) > 250) schedule(i);  // the voice is ahead or behind: re-sync from this word
        },
        onEnd: () => { try { this.head && this.head.stopSpeaking(); } catch (e) { /* already idle */ } }
      }, emotion);
    } catch (error) {
      console.error('[Avatar3D] Browser speech failed:', error);
      try { this.head && this.head.stopSpeaking(); } catch (e) { /* already idle */ }
    }
  }

  /**
   * Show subtitle text
   */
  showSubtitle(text) {
    if (this.subtitleElement) {
      this.subtitleElement.textContent = text;
      this.subtitleElement.classList.add('active');
    }
  }

  /**
   * Hide subtitle
   */
  hideSubtitle() {
    if (this.subtitleElement) {
      this.subtitleElement.classList.remove('active');
      setTimeout(() => {
        this.subtitleElement.textContent = '';
      }, 300);
    }
  }

  /**
   * Show/hide speaking indicator
   */
  showSpeakingIndicator(show) {
    if (this.indicatorElement) {
      this.indicatorElement.style.display = show ? 'flex' : 'none';
    }
  }

  /**
   * Speech callbacks
   */
  onSpeechStart() {
    const wrapper = this.container.querySelector('.avatar-3d-wrapper');
    wrapper?.classList.add('speaking');
  }

  onSpeechEnd() {
    this.isSpeaking = false;
    this.hideSubtitle();
    this.showSpeakingIndicator(false);

    const wrapper = this.container.querySelector('.avatar-3d-wrapper');
    wrapper?.classList.remove('speaking');
  }

  /**
   * Stop speaking
   */
  stop() {
    try {
      // Stop TalkingHead speech
      if (this.head && this.head.stopSpeaking) {
        this.head.stopSpeaking();
      }
    } catch (err) {
      console.warn('[Avatar3D] Error stopping TalkingHead speech:', err);
    }

    // Also stop fallback TTS
    ttsService.stop();

    this.onSpeechEnd();
  }

  /**
   * Set emotion
   */
  setEmotion(emotion) {
    if (!this.head) return;

    const moodMap = {
      'neutral': 'neutral',
      'empathetic': 'sad',
      'concerned': 'serious',
      'cheerful': 'happy'
    };
    const mood = moodMap[emotion] || 'neutral';
    this.head.avatarMood = mood;
  }

  /**
   * Show fallback 2D avatar
   */
  showFallback() {
    this.hideLoading();
    const fallbackHTML = this.config.imageUrl
      ? `<img src="${this.config.imageUrl}" alt="${this.config.name}" class="avatar-fallback-image" style="max-width:300px;max-height:400px;object-fit:cover;border-radius:12px;">`
      : `<div class="avatar-fallback-placeholder" style="width:200px;height:200px;border-radius:50%;background:var(--green);color:white;display:grid;place-items:center;font-size:64px;font-weight:600;">${this.config.name.split(' ').map(n => n[0]).join('')}</div>`;

    this.container.querySelector('.avatar-3d-wrapper').innerHTML = `
      <div class="avatar-fallback" style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;padding:40px;background:linear-gradient(135deg,#e4edf2 0%,#d2e5e9 100%);">
        ${fallbackHTML}
        <p style="margin-top:20px;font-size:11px;color:var(--muted);text-align:center;">3D model unavailable - using 2D mode</p>
      </div>
      <div class="avatar-subtitle-overlay" style="position:absolute;bottom:0;left:0;right:0;padding:30px 40px;background:linear-gradient(to top,rgba(0,0,0,.75) 0%,rgba(0,0,0,.4) 50%,transparent 100%);pointer-events:none;">
        <div class="avatar-subtitle" id="avatar-subtitle"></div>
      </div>
    `;

    this.subtitleElement = this.container.querySelector('#avatar-subtitle');
    this.isInitialized = true; // Allow subtitle-only mode
  }

  /**
   * Hide loading indicator
   */
  hideLoading() {
    if (this.loadingElement) {
      this.loadingElement.style.display = 'none';
    }
  }

  /**
   * Destroy and clean up
   */
  destroy() {
    this.stop();

    try {
      if (this.head) {
        // Try both stop and disconnect methods
        if (this.head.stop) {
          this.head.stop();
        }
        if (this.head.disconnect) {
          this.head.disconnect();
        }
      }
    } catch (err) {
      console.warn('[Avatar3D] Error during cleanup:', err);
    }

    this.head = null;
    this.isInitialized = false;
  }

  /**
   * Update configuration
   */
  updateConfig(newConfig) {
    this.config = { ...this.config, ...newConfig };
    if (newConfig.modelPath || newConfig.patientId) {
      this.destroy();
      this.init();
    }
  }
}

export default Avatar3D;
