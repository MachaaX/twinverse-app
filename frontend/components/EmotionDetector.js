/**
 * EmotionDetector - Analyzes text for emotional content
 * Maps emotions to avatar moods
 */

export class EmotionDetector {
  constructor() {
    // Emotion patterns with keywords
    this.patterns = {
      offensive: {
        keywords: ['stupid', 'idiot', 'dumb', 'shut up', 'whatever', 'don\'t care', 'annoying', 'waste', 'useless', 'ridiculous', 'pathetic', 'hate', 'dislike'],
        mood: 'sad',
        intensity: 0.8
      },
      angry: {
        keywords: ['angry', 'mad', 'furious', 'frustrated', 'irritated', 'annoyed'],
        mood: 'angry',
        intensity: 0.7
      },
      empathetic: {
        keywords: ['understand', 'sorry', 'concerned', 'care about', 'here for you', 'support', 'help you', 'listening', 'must be', 'difficult', 'hard for you'],
        mood: 'fear', // TalkingHead uses 'fear' for concerned/empathetic
        intensity: 0.6
      },
      cheerful: {
        keywords: ['great', 'wonderful', 'excellent', 'fantastic', 'amazing', 'glad', 'happy', 'good news', 'proud', 'well done', 'congratulations'],
        mood: 'happy',
        intensity: 0.7
      },
      dismissive: {
        keywords: ['whatever', 'don\'t care', 'not important', 'doesn\'t matter', 'who cares', 'so what'],
        mood: 'sad',
        intensity: 0.6
      },
      concerned: {
        keywords: ['worried', 'afraid', 'scared', 'anxious', 'concerned', 'nervous', 'frightened'],
        mood: 'fear',
        intensity: 0.5
      }
    };
  }

  /**
   * Analyze text and detect emotion
   * @param {string} text - Text to analyze
   * @returns {Object} - { emotion: string, mood: string, intensity: number, detected: boolean }
   */
  analyze(text) {
    if (!text || typeof text !== 'string') {
      return { emotion: 'neutral', mood: 'neutral', intensity: 0, detected: false };
    }

    const lowerText = text.toLowerCase();
    let detectedEmotion = null;
    let maxIntensity = 0;

    // Check each emotion pattern
    for (const [emotion, config] of Object.entries(this.patterns)) {
      const matchCount = config.keywords.filter(keyword =>
        lowerText.includes(keyword.toLowerCase())
      ).length;

      if (matchCount > 0) {
        const intensity = Math.min(config.intensity * matchCount, 1.0);

        if (intensity > maxIntensity) {
          maxIntensity = intensity;
          detectedEmotion = {
            emotion,
            mood: config.mood,
            intensity,
            detected: true
          };
        }
      }
    }

    // Check for question marks (curious/neutral)
    if (!detectedEmotion && text.includes('?')) {
      return { emotion: 'curious', mood: 'neutral', intensity: 0.3, detected: true };
    }

    // Return detected emotion or default neutral
    return detectedEmotion || { emotion: 'neutral', mood: 'neutral', intensity: 0, detected: false };
  }

  /**
   * Get avatar reaction based on emotion
   * @param {string} studentText - What the student said
   * @returns {Object} - { mood: string, duration: number, message: string }
   */
  getAvatarReaction(studentText) {
    const analysis = this.analyze(studentText);

    const reactions = {
      offensive: {
        mood: 'sad',
        duration: 3000,
        message: 'The patient looks hurt and withdrawn'
      },
      angry: {
        mood: 'angry',
        duration: 2500,
        message: 'The patient appears upset'
      },
      dismissive: {
        mood: 'sad',
        duration: 2500,
        message: 'The patient seems disappointed'
      },
      empathetic: {
        mood: 'fear', // Concerned/empathetic mood
        duration: 2000,
        message: 'The patient appears comforted'
      },
      cheerful: {
        mood: 'happy',
        duration: 2000,
        message: 'The patient smiles'
      },
      concerned: {
        mood: 'fear',
        duration: 2000,
        message: 'The patient looks worried'
      },
      curious: {
        mood: 'neutral',
        duration: 1000,
        message: null
      },
      neutral: {
        mood: 'neutral',
        duration: 1000,
        message: null
      }
    };

    const reaction = reactions[analysis.emotion] || reactions.neutral;

    return {
      ...reaction,
      emotion: analysis.emotion,
      intensity: analysis.intensity,
      detected: analysis.detected
    };
  }
}

// Create singleton instance
export const emotionDetector = new EmotionDetector();
