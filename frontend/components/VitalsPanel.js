/**
 * VitalsPanel - Interactive vital signs measurement
 * Buttons unlock based on conversation context
 */

export class VitalsPanel {
  constructor() {
    this.vitals = {
      heartRate: {
        name: 'Heart Rate',
        icon: '❤️',
        unit: 'bpm',
        unlocked: false,
        measured: false,
        value: null,
        keywords: ['chest', 'heart', 'palpitations', 'racing', 'pulse', 'beats', 'cardiac', 'pain'],
        generateValue: (patient) => {
          // Normal: 60-100, adjust based on conditions
          const base = 70 + Math.floor(Math.random() * 20);
          return patient.anxious ? base + 15 : base;
        }
      },
      bloodPressure: {
        name: 'Blood Pressure',
        icon: '🩺',
        unit: 'mmHg',
        unlocked: false,
        measured: false,
        value: null,
        keywords: ['dizzy', 'lightheaded', 'pressure', 'headache', 'vision', 'blood pressure', 'hypertension'],
        generateValue: (patient) => {
          const systolic = 110 + Math.floor(Math.random() * 20);
          const diastolic = 70 + Math.floor(Math.random() * 15);
          return `${systolic}/${diastolic}`;
        }
      },
      temperature: {
        name: 'Temperature',
        icon: '🌡️',
        unit: '°F',
        unlocked: false,
        measured: false,
        value: null,
        keywords: ['fever', 'chills', 'hot', 'cold', 'sweating', 'temperature', 'warm'],
        generateValue: (patient) => {
          const base = 98.0 + Math.random() * 0.8;
          return patient.fever ? (99.5 + Math.random() * 2).toFixed(1) : base.toFixed(1);
        }
      },
      respiratoryRate: {
        name: 'Respiratory Rate',
        icon: '🫁',
        unit: 'breaths/min',
        unlocked: false,
        measured: false,
        value: null,
        keywords: ['breath', 'breathing', 'shortness', 'wheeze', 'cough', 'chest', 'respiratory', 'lungs'],
        generateValue: (patient) => {
          return 12 + Math.floor(Math.random() * 8);
        }
      },
      oxygenSaturation: {
        name: 'Oxygen Saturation',
        icon: '💨',
        unit: '%',
        unlocked: false,
        measured: false,
        value: null,
        keywords: ['breath', 'breathing', 'shortness', 'oxygen', 'dizzy', 'tired', 'fatigue'],
        generateValue: (patient) => {
          return 95 + Math.floor(Math.random() * 5);
        }
      },
      weight: {
        name: 'Weight',
        icon: '⚖️',
        unit: 'lbs',
        unlocked: false,
        measured: false,
        value: null,
        keywords: ['weight', 'gained', 'lost', 'appetite', 'eating', 'diet'],
        generateValue: (patient) => {
          return 120 + Math.floor(Math.random() * 80);
        }
      }
    };
  }

  /**
   * Check conversation text and unlock relevant vitals
   */
  checkForUnlocks(conversationText) {
    const lowerText = conversationText.toLowerCase();
    const unlocked = [];

    for (const [key, vital] of Object.entries(this.vitals)) {
      if (!vital.unlocked) {
        const matches = vital.keywords.some(keyword =>
          lowerText.includes(keyword.toLowerCase())
        );

        if (matches) {
          vital.unlocked = true;
          unlocked.push(vital.name);
          console.log('[VitalsPanel] Unlocked:', vital.name);
        }
      }
    }

    return unlocked;
  }

  /**
   * Measure a vital sign
   */
  measureVital(vitalKey, patientContext = {}) {
    const vital = this.vitals[vitalKey];

    if (!vital) {
      console.error('[VitalsPanel] Unknown vital:', vitalKey);
      return null;
    }

    if (!vital.unlocked) {
      console.warn('[VitalsPanel] Vital not unlocked:', vitalKey);
      return null;
    }

    // Generate realistic value
    vital.value = vital.generateValue(patientContext);
    vital.measured = true;
    vital.timestamp = new Date().toISOString();

    console.log('[VitalsPanel] Measured', vital.name, ':', vital.value, vital.unit);

    return {
      name: vital.name,
      value: vital.value,
      unit: vital.unit,
      timestamp: vital.timestamp,
      icon: vital.icon
    };
  }

  /**
   * Get all measured vitals
   */
  getMeasuredVitals() {
    return Object.entries(this.vitals)
      .filter(([_, vital]) => vital.measured)
      .map(([key, vital]) => ({
        key,
        name: vital.name,
        value: vital.value,
        unit: vital.unit,
        icon: vital.icon,
        timestamp: vital.timestamp
      }));
  }

  /**
   * Get vital status for UI
   */
  getVitalStatus(vitalKey) {
    const vital = this.vitals[vitalKey];
    return {
      unlocked: vital.unlocked,
      measured: vital.measured,
      value: vital.value,
      unit: vital.unit
    };
  }

  /**
   * Reset all vitals
   */
  reset() {
    for (const vital of Object.values(this.vitals)) {
      vital.unlocked = false;
      vital.measured = false;
      vital.value = null;
      vital.timestamp = null;
    }
  }
}

// Create singleton instance
export const vitalsPanel = new VitalsPanel();
