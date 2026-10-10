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
      ...config
    };

    this.isInitialized = false;
    this.isSpeaking = false;
    this.head = null;
    this.subtitleElement = null;

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
      this.head = new TalkingHead(this.viewElement, {
        ttsEndpoint: '/api/tts',
        lipsyncModules: ['en'],
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
   * Speak text with lip-sync and subtitles using Amazon Polly
   */
  async speak(text, emotion = 'neutral') {
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

      // Select voice based on gender
      const gender = (this.config.gender || '').toLowerCase();
      const voice = gender === 'male' ? 'Matthew' : 'Joanna';
      console.log('[Avatar3D] Using voice:', voice, 'for gender:', gender);

      const response = await fetch('/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, voice })
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
        await this.head.speakAudio({
          audio: audioBuffer,  // AudioBuffer object
          words: data.words || [],
          wtimes: data.wtimes || [],
          wdurations: data.wdurations || [],
          lipsyncLang: 'en'
        });

        console.log('[Avatar3D] ✓ Polly speech with lip-sync complete');
      } else {
        // Fallback to browser TTS if Polly unavailable
        console.log('[Avatar3D] Polly unavailable, using browser TTS');
        if (ttsService.isAvailable()) {
          await ttsService.speak(text, {}, emotion);
        }
      }

      this.onSpeechEnd();

    } catch (error) {
      console.error('[Avatar3D] Speech error:', error);

      // Fallback to browser TTS on error
      try {
        if (ttsService.isAvailable()) {
          console.log('[Avatar3D] Falling back to browser TTS');
          await ttsService.speak(text, {}, emotion);
        }
      } catch (fallbackErr) {
        console.error('[Avatar3D] Fallback TTS also failed:', fallbackErr);
      }

      this.onSpeechEnd();
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
      <div class="avatar-fallback" style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;padding:40px;background:linear-gradient(135deg,#e8eddf 0%,#d4ddc7 100%);">
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
