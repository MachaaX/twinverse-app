/**
 * Avatar Canvas Component - Animated talking head
 * Supports basic lip-sync, emotions, and idle animations
 * Can be upgraded to WebGL/Three.js for full 3D rendering
 */

import { ttsService } from './TTSService.js';

export class AvatarCanvas {
  constructor(containerElement, config = {}) {
    this.container = containerElement;
    this.config = {
      name: config.name || 'Patient',
      gender: config.gender || 'neutral',
      imageUrl: config.imageUrl || null,
      enableLipSync: config.enableLipSync !== false,
      enableIdleAnimation: config.enableIdleAnimation !== false,
      ...config
    };

    this.isInitialized = false;
    this.isSpeaking = false;
    this.currentEmotion = 'neutral';
    this.animationFrame = null;
    this.lipSyncInterval = null;

    this.init();
  }

  init() {
    // Create avatar container structure
    this.container.innerHTML = `
      <div class="avatar-wrapper" data-emotion="${this.currentEmotion}">
        <div class="avatar-container">
          ${this.config.imageUrl ? `
            <div class="avatar-image-layer">
              <img src="${this.config.imageUrl}" alt="${this.config.name}" class="avatar-base-image">
            </div>
          ` : `
            <div class="avatar-placeholder">
              <div class="avatar-head">
                <div class="avatar-face">
                  <div class="avatar-eyes">
                    <div class="avatar-eye left">
                      <div class="avatar-pupil"></div>
                    </div>
                    <div class="avatar-eye right">
                      <div class="avatar-pupil"></div>
                    </div>
                  </div>
                  <div class="avatar-mouth">
                    <div class="avatar-mouth-shape"></div>
                  </div>
                </div>
              </div>
            </div>
          `}

          <div class="avatar-overlay">
            <div class="avatar-mouth-overlay">
              <div class="mouth-shape" data-shape="closed"></div>
            </div>
          </div>

          <div class="avatar-status">
            <div class="speaking-indicator" style="display: none;">
              <span class="pulse-dot"></span>
              <span class="status-text">Speaking...</span>
            </div>
          </div>
        </div>
      </div>
    `;

    this.elements = {
      wrapper: this.container.querySelector('.avatar-wrapper'),
      mouth: this.container.querySelector('.mouth-shape'),
      indicator: this.container.querySelector('.speaking-indicator'),
      eyes: this.container.querySelectorAll('.avatar-eye'),
      overlay: this.container.querySelector('.avatar-overlay')
    };

    if (this.config.enableIdleAnimation) {
      this.startIdleAnimation();
    }

    this.isInitialized = true;
  }

  /**
   * Speak text with synchronized lip animation
   */
  async speak(text, emotion = 'neutral') {
    if (!this.isInitialized) {
      throw new Error('Avatar not initialized');
    }

    // Set emotion
    this.setEmotion(emotion);
    this.isSpeaking = true;
    this.showSpeakingIndicator(true);

    try {
      // Start lip-sync animation
      this.startLipSync();

      // Speak using TTS
      await ttsService.speak(text, {
        onStart: () => {
          this.onSpeechStart();
        },
        onEnd: () => {
          this.onSpeechEnd();
        },
        onError: (error) => {
          console.error('TTS error:', error);
          this.onSpeechEnd();
        }
      }, emotion);

    } catch (error) {
      console.error('Avatar speech error:', error);
      this.onSpeechEnd();
      throw error;
    }
  }

  /**
   * Stop speaking
   */
  stop() {
    ttsService.stop();
    this.onSpeechEnd();
  }

  /**
   * Set avatar emotion
   */
  setEmotion(emotion) {
    this.currentEmotion = emotion;
    if (this.elements.wrapper) {
      this.elements.wrapper.setAttribute('data-emotion', emotion);
    }
  }

  /**
   * Start lip-sync animation
   */
  startLipSync() {
    if (!this.config.enableLipSync || !this.elements.mouth) return;

    const mouthShapes = ['closed', 'open', 'wide', 'smile'];
    let shapeIndex = 0;

    // Animate mouth shapes at ~15 Hz (66ms interval)
    this.lipSyncInterval = setInterval(() => {
      if (!this.isSpeaking) {
        this.elements.mouth.setAttribute('data-shape', 'closed');
        return;
      }

      // Cycle through mouth shapes with some randomness
      if (Math.random() > 0.3) {
        shapeIndex = (shapeIndex + 1) % mouthShapes.length;
      }
      this.elements.mouth.setAttribute('data-shape', mouthShapes[shapeIndex]);
    }, 66);
  }

  /**
   * Stop lip-sync animation
   */
  stopLipSync() {
    if (this.lipSyncInterval) {
      clearInterval(this.lipSyncInterval);
      this.lipSyncInterval = null;
    }
    if (this.elements.mouth) {
      this.elements.mouth.setAttribute('data-shape', 'closed');
    }
  }

  /**
   * Start idle animations (blinking, breathing)
   */
  startIdleAnimation() {
    // Blink animation
    const blink = () => {
      if (this.elements.eyes) {
        this.elements.eyes.forEach(eye => eye.classList.add('blinking'));
        setTimeout(() => {
          this.elements.eyes.forEach(eye => eye.classList.remove('blinking'));
        }, 150);
      }

      // Random blink interval between 2-6 seconds
      const nextBlink = 2000 + Math.random() * 4000;
      setTimeout(blink, nextBlink);
    };

    // Start blinking after initial delay
    setTimeout(blink, 2000);

    // Gentle breathing animation is handled by CSS
  }

  /**
   * Show/hide speaking indicator
   */
  showSpeakingIndicator(show) {
    if (this.elements.indicator) {
      this.elements.indicator.style.display = show ? 'flex' : 'none';
    }
  }

  /**
   * Speech started callback
   */
  onSpeechStart() {
    this.elements.wrapper?.classList.add('speaking');
  }

  /**
   * Speech ended callback
   */
  onSpeechEnd() {
    this.isSpeaking = false;
    this.stopLipSync();
    this.showSpeakingIndicator(false);
    this.elements.wrapper?.classList.remove('speaking');
    this.setEmotion('neutral');
  }

  /**
   * Destroy avatar and clean up
   */
  destroy() {
    this.stop();
    this.stopLipSync();
    if (this.animationFrame) {
      cancelAnimationFrame(this.animationFrame);
    }
    this.isInitialized = false;
  }

  /**
   * Update configuration
   */
  updateConfig(newConfig) {
    this.config = { ...this.config, ...newConfig };
    if (newConfig.imageUrl !== undefined || newConfig.name !== undefined) {
      this.init();
    }
  }
}

export default AvatarCanvas;