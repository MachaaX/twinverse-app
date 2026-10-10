/**
 * Avatar3D Component - 3D GLB Model Avatar with Lip-Sync
 * Loads and renders 3D patient models with real-time lip-sync animation
 */

import { ttsService } from './TTSService.js';

// Import Three.js classes directly
import {
  Scene,
  PerspectiveCamera,
  WebGLRenderer,
  Color,
  AmbientLight,
  DirectionalLight,
  Clock,
  AnimationMixer
} from 'three';

import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

export class Avatar3D {
  constructor(containerElement, config = {}) {
    this.container = containerElement;
    this.config = {
      name: config.name || 'Patient',
      gender: config.gender || 'neutral',
      patientId: config.patientId || null,
      modelPath: config.modelPath || null,
      enableLipSync: config.enableLipSync !== false,
      enableIdleAnimation: config.enableIdleAnimation !== false,
      fallbackImage: config.imageUrl || null,
      ...config
    };

    // Three.js objects
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.model = null;
    this.mixer = null;
    this.clock = null;

    // Animation state
    this.isInitialized = false;
    this.isSpeaking = false;
    this.currentEmotion = 'neutral';
    this.animationFrame = null;
    this.lipSyncInterval = null;
    this.morphTargets = null;

    // Subtitle state
    this.currentSubtitle = '';
    this.subtitleElement = null;

    this.init();
  }

  async init() {
    // Create container structure with subtitle overlay
    this.container.innerHTML = `
      <div class="avatar-3d-wrapper" data-emotion="${this.currentEmotion}">
        <canvas id="avatar-canvas-3d" class="avatar-canvas-3d"></canvas>
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

    this.canvas = this.container.querySelector('#avatar-canvas-3d');
    this.subtitleElement = this.container.querySelector('#avatar-subtitle');
    this.loadingElement = this.container.querySelector('.avatar-loading-3d');
    this.indicatorElement = this.container.querySelector('.speaking-indicator-3d');

    // Determine model path
    const modelPath = this.config.modelPath || this.getModelPath();

    try {
      await this.initThreeJS();
      await this.loadModel(modelPath);
      this.hideLoading();
      this.isInitialized = true;
    } catch (error) {
      console.error('Failed to load 3D model:', error);
      this.showFallback();
    }
  }

  /**
   * Initialize Three.js scene, camera, renderer
   */
  initThreeJS() {
    const width = this.canvas.offsetWidth || 640;
    const height = this.canvas.offsetHeight || 480;

    // Scene
    this.scene = new Scene();
    this.scene.background = new Color(0xf5f7f2);

    // Camera - positioned to show head and upper torso
    this.camera = new PerspectiveCamera(35, width / height, 0.1, 1000);
    this.camera.position.set(0, 1.5, 2.5);
    this.camera.lookAt(0, 1.5, 0);

    // Renderer
    this.renderer = new WebGLRenderer({
      canvas: this.canvas,
      antialias: true,
      alpha: true
    });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.shadowMap.enabled = true;

    // Lighting
    const ambientLight = new AmbientLight(0xffffff, 0.6);
    this.scene.add(ambientLight);

    const directionalLight = new DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(2, 3, 2);
    directionalLight.castShadow = true;
    this.scene.add(directionalLight);

    const fillLight = new DirectionalLight(0xffffff, 0.3);
    fillLight.position.set(-2, 1, -2);
    this.scene.add(fillLight);

    // Animation clock
    this.clock = new Clock();

    // Handle resize
    window.addEventListener('resize', () => this.onResize());

    // Start render loop
    this.animate();
  }

  /**
   * Load GLB model
   */
  async loadModel(modelPath) {
    return new Promise((resolve, reject) => {
      const loader = new GLTFLoader();

      loader.load(
        modelPath,
        (gltf) => {
          this.model = gltf.scene;

          // Scale and position model
          this.model.scale.set(1, 1, 1);
          this.model.position.set(0, 0, 0);

          this.scene.add(this.model);

          // Find morph targets for lip-sync (common in Ready Player Me and similar models)
          this.findMorphTargets();

          // Setup animations if available
          if (gltf.animations && gltf.animations.length > 0) {
            this.mixer = new AnimationMixer(this.model);
            // Play idle animation if available
            const idleAnimation = gltf.animations.find(a =>
              a.name.toLowerCase().includes('idle') ||
              a.name.toLowerCase().includes('breathe')
            );
            if (idleAnimation && this.config.enableIdleAnimation) {
              const action = this.mixer.clipAction(idleAnimation);
              action.play();
            }
          }

          resolve();
        },
        (progress) => {
          const percent = (progress.loaded / progress.total * 100).toFixed(0);
          this.updateLoadingText(`Loading 3D avatar... ${percent}%`);
        },
        (error) => {
          reject(error);
        }
      );
    });
  }

  /**
   * Find morph targets for facial animations
   */
  findMorphTargets() {
    this.morphTargets = {};

    if (!this.model) return;

    this.model.traverse((child) => {
      if (child.isMesh && child.morphTargetDictionary && child.morphTargetInfluences) {
        // Store reference to mesh with morph targets
        // Common morph target names for speech (ARKit standard)
        const lipSyncTargets = [
          'mouthOpen', 'jawOpen', 'mouthSmile', 'mouthFunnel',
          'mouthPucker', 'mouthClose', 'viseme_aa', 'viseme_E',
          'viseme_I', 'viseme_O', 'viseme_U'
        ];

        lipSyncTargets.forEach(targetName => {
          if (child.morphTargetDictionary[targetName] !== undefined) {
            if (!this.morphTargets[targetName]) {
              this.morphTargets[targetName] = [];
            }
            this.morphTargets[targetName].push({
              mesh: child,
              index: child.morphTargetDictionary[targetName]
            });
          }
        });
      }
    });
  }

  /**
   * Get model path based on patient configuration
   */
  getModelPath() {
    // Try to determine model path from patient data
    if (this.config.patientId) {
      // Map patient IDs to model files
      // This can be customized based on your patient data structure
      return `/public/models/patient_${this.config.patientId}.glb`;
    }

    // Default model based on gender
    const genderMap = {
      'Male': 'male_default',
      'Female': 'female_default',
      'Non-binary': 'neutral_default'
    };

    const modelName = genderMap[this.config.gender] || 'neutral_default';
    return `/public/models/${modelName}.glb`;
  }

  /**
   * Animation loop
   */
  animate() {
    this.animationFrame = requestAnimationFrame(() => this.animate());

    const delta = this.clock.getDelta();

    // Update mixer for animations
    if (this.mixer) {
      this.mixer.update(delta);
    }

    // Render scene
    if (this.renderer && this.scene && this.camera) {
      this.renderer.render(this.scene, this.camera);
    }
  }

  /**
   * Handle window resize
   */
  onResize() {
    if (!this.camera || !this.renderer || !this.canvas) return;

    const width = this.canvas.offsetWidth || 640;
    const height = this.canvas.offsetHeight || 480;

    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }

  /**
   * Speak text with lip-sync and subtitles
   */
  async speak(text, emotion = 'neutral') {
    if (!this.isInitialized) {
      throw new Error('Avatar not initialized');
    }

    this.setEmotion(emotion);
    this.isSpeaking = true;
    this.showSpeakingIndicator(true);
    this.showSubtitle(text);

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
        onWord: (event) => {
          // Update subtitle to show current word/phrase
          this.updateSubtitleProgress(text, event.charIndex);
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
   * Start lip-sync animation using morph targets
   */
  startLipSync() {
    if (!this.config.enableLipSync) return;

    // Animate morph targets to simulate speech
    const lipSyncShapes = ['mouthOpen', 'jawOpen', 'mouthSmile', 'mouthFunnel'];
    let shapeIndex = 0;

    this.lipSyncInterval = setInterval(() => {
      if (!this.isSpeaking) {
        this.resetMorphTargets();
        return;
      }

      // Randomly vary mouth shapes
      if (Math.random() > 0.2) {
        shapeIndex = (shapeIndex + 1) % lipSyncShapes.length;
      }

      const currentShape = lipSyncShapes[shapeIndex];
      const intensity = 0.3 + Math.random() * 0.5; // Vary intensity

      // Apply morph target
      this.setMorphTarget(currentShape, intensity);

      // Reset others
      lipSyncShapes.forEach(shape => {
        if (shape !== currentShape) {
          this.setMorphTarget(shape, 0);
        }
      });

    }, 80); // ~12 Hz for natural speech animation
  }

  /**
   * Set morph target value
   */
  setMorphTarget(targetName, value) {
    if (!this.morphTargets || !this.morphTargets[targetName]) return;

    this.morphTargets[targetName].forEach(({ mesh, index }) => {
      if (mesh.morphTargetInfluences) {
        mesh.morphTargetInfluences[index] = value;
      }
    });
  }

  /**
   * Reset all morph targets to neutral
   */
  resetMorphTargets() {
    if (!this.morphTargets) return;

    Object.keys(this.morphTargets).forEach(targetName => {
      this.setMorphTarget(targetName, 0);
    });
  }

  /**
   * Stop lip-sync
   */
  stopLipSync() {
    if (this.lipSyncInterval) {
      clearInterval(this.lipSyncInterval);
      this.lipSyncInterval = null;
    }
    this.resetMorphTargets();
  }

  /**
   * Show subtitle text
   */
  showSubtitle(text) {
    if (this.subtitleElement) {
      this.currentSubtitle = text;
      this.subtitleElement.textContent = text;
      this.subtitleElement.classList.add('active');
    }
  }

  /**
   * Update subtitle to show progress (optional enhancement)
   */
  updateSubtitleProgress(fullText, charIndex) {
    // Optional: Could highlight current word or show streaming text
    // For now, just show the full text
  }

  /**
   * Hide subtitle
   */
  hideSubtitle() {
    if (this.subtitleElement) {
      this.subtitleElement.classList.remove('active');
      setTimeout(() => {
        this.subtitleElement.textContent = '';
        this.currentSubtitle = '';
      }, 300);
    }
  }

  /**
   * Set emotion
   */
  setEmotion(emotion) {
    this.currentEmotion = emotion;
    const wrapper = this.container.querySelector('.avatar-3d-wrapper');
    if (wrapper) {
      wrapper.setAttribute('data-emotion', emotion);
    }

    // Adjust lighting based on emotion (optional)
    if (this.scene) {
      // Could adjust scene lighting or colors here
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
    this.stopLipSync();
    this.hideSubtitle();
    this.showSpeakingIndicator(false);

    const wrapper = this.container.querySelector('.avatar-3d-wrapper');
    wrapper?.classList.remove('speaking');

    this.setEmotion('neutral');
  }

  /**
   * Stop speaking
   */
  stop() {
    ttsService.stop();
    this.onSpeechEnd();
  }

  /**
   * Show fallback 2D avatar
   */
  showFallback() {
    this.hideLoading();
    const fallbackHTML = this.config.fallbackImage
      ? `<img src="${this.config.fallbackImage}" alt="${this.config.name}" class="avatar-fallback-image">`
      : `<div class="avatar-fallback-placeholder">${this.config.name.split(' ').map(n => n[0]).join('')}</div>`;

    this.container.querySelector('.avatar-3d-wrapper').innerHTML = `
      <div class="avatar-fallback">
        ${fallbackHTML}
        <p class="avatar-fallback-message">3D model unavailable</p>
      </div>
      <div class="avatar-subtitle-overlay">
        <div class="avatar-subtitle" id="avatar-subtitle"></div>
      </div>
    `;

    this.subtitleElement = this.container.querySelector('#avatar-subtitle');
    this.isInitialized = true; // Allow subtitle-only mode
  }

  /**
   * Update loading text
   */
  updateLoadingText(text) {
    if (this.loadingElement) {
      const textEl = this.loadingElement.querySelector('span:last-child');
      if (textEl) textEl.textContent = text;
    }
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
    this.stopLipSync();

    if (this.animationFrame) {
      cancelAnimationFrame(this.animationFrame);
    }

    if (this.renderer) {
      this.renderer.dispose();
    }

    if (this.scene) {
      this.scene.traverse((object) => {
        if (object.geometry) object.geometry.dispose();
        if (object.material) {
          if (Array.isArray(object.material)) {
            object.material.forEach(material => material.dispose());
          } else {
            object.material.dispose();
          }
        }
      });
    }

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
