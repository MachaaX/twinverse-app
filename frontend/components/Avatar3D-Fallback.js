/**
 * Avatar3D Fallback - Simple fallback when Three.js fails to load
 */

import { ttsService } from './TTSService.js';

export class Avatar3D {
  constructor(containerElement, config = {}) {
    this.container = containerElement;
    this.config = {
      name: config.name || 'Patient',
      fallbackImage: config.imageUrl || null,
      ...config
    };

    this.isInitialized = false;
    this.isSpeaking = false;
    this.subtitleElement = null;

    this.init();
  }

  async init() {
    console.log('[Avatar3D Fallback] Using 2D fallback mode');

    // Create simple fallback with subtitle support
    this.container.innerHTML = `
      <div class="avatar-3d-wrapper" style="position:relative;width:100%;height:100%;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#e8eddf 0%,#d4ddc7 100%);border-radius:16px;">
        ${this.config.fallbackImage
          ? `<img src="${this.config.fallbackImage}" alt="${this.config.name}" style="max-width:300px;max-height:400px;object-fit:cover;border-radius:12px;box-shadow:0 8px 30px rgba(0,0,0,0.15);">`
          : `<div style="width:200px;height:200px;border-radius:50%;background:var(--green);color:white;display:grid;place-items:center;font-size:64px;font-weight:600;box-shadow:0 8px 30px rgba(0,0,0,0.15);">${this.config.name.split(' ').map(n => n[0]).join('')}</div>`
        }
        <div class="avatar-subtitle-overlay" style="position:absolute;bottom:0;left:0;right:0;padding:30px 40px;background:linear-gradient(to top,rgba(0,0,0,.75) 0%,rgba(0,0,0,.4) 50%,transparent 100%);pointer-events:none;">
          <div class="avatar-subtitle" id="avatar-subtitle" style="background:rgba(255,255,255,.95);color:var(--ink);padding:16px 24px;border-radius:12px;font-size:15px;line-height:1.75;text-align:center;box-shadow:0 4px 20px rgba(0,0,0,.15);opacity:0;transform:translateY(20px);transition:opacity .3s ease,transform .3s ease;max-width:90%;margin:0 auto;"></div>
        </div>
        <div style="position:absolute;top:10px;right:10px;background:rgba(255,255,255,0.9);padding:6px 12px;border-radius:8px;font-size:10px;color:var(--muted);">2D Mode</div>
      </div>
    `;

    this.subtitleElement = this.container.querySelector('#avatar-subtitle');
    this.isInitialized = true;
  }

  async speak(text, emotion = 'neutral') {
    if (!this.isInitialized) return;

    this.isSpeaking = true;
    this.showSubtitle(text);

    try {
      if (ttsService.isAvailable()) {
        await ttsService.speak(text, {
          onEnd: () => {
            this.onSpeechEnd();
          }
        }, emotion);
      } else {
        // Show subtitle for 3 seconds if no TTS
        setTimeout(() => {
          this.onSpeechEnd();
        }, Math.max(3000, text.length * 50));
      }
    } catch (error) {
      console.error('Speech error:', error);
      this.onSpeechEnd();
    }
  }

  showSubtitle(text) {
    if (this.subtitleElement) {
      this.subtitleElement.textContent = text;
      this.subtitleElement.style.opacity = '1';
      this.subtitleElement.style.transform = 'translateY(0)';
    }
  }

  hideSubtitle() {
    if (this.subtitleElement) {
      this.subtitleElement.style.opacity = '0';
      this.subtitleElement.style.transform = 'translateY(20px)';
      setTimeout(() => {
        this.subtitleElement.textContent = '';
      }, 300);
    }
  }

  onSpeechEnd() {
    this.isSpeaking = false;
    this.hideSubtitle();
  }

  stop() {
    if (ttsService.isAvailable()) {
      ttsService.stop();
    }
    this.onSpeechEnd();
  }

  setEmotion(emotion) {
    // No-op in fallback mode
  }

  destroy() {
    this.stop();
    this.isInitialized = false;
  }

  updateConfig(newConfig) {
    this.config = { ...this.config, ...newConfig };
  }
}

export default Avatar3D;
