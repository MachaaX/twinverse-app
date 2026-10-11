/**
 * VitalsPanel - Interactive vital signs measurement
 * Buttons unlock based on conversation context
 */

export class VitalsPanel {
  constructor() {
    this.vitals = {
      heartRate: {
        name: 'HR',
        fullName: 'Heart Rate',
        icon: 'heart',
        unit: 'bpm',
        unlocked: false,
        measured: false,
        value: null,
        keywords: ['chest', 'heart', 'palpitations', 'racing', 'pulse', 'beats', 'cardiac', 'pain'],
        generateValue: (patient) => {
          // Use consistent random based on patient ID
          const base = this.getConsistentRandom(patient.id, 'heartRate', 65, 75);

          // Adjust based on patient condition
          let adjustment = 0;
          if (patient.chestPain || patient.cardiac) adjustment += 20;
          if (patient.anxious || patient.panic) adjustment += 15;
          if (patient.fever) adjustment += 10;
          if (patient.pain) adjustment += 8;
          if (patient.age > 70) adjustment -= 5;

          return Math.min(base + adjustment, 120); // Cap at 120
        }
      },
      bloodPressure: {
        name: 'BP',
        fullName: 'Blood Pressure',
        icon: 'activity',
        unit: 'mmHg',
        unlocked: false,
        measured: false,
        value: null,
        keywords: ['dizzy', 'lightheaded', 'pressure', 'headache', 'vision', 'blood pressure', 'hypertension'],
        generateValue: (patient) => {
          let systolic = this.getConsistentRandom(patient.id, 'bpSystolic', 115, 125);
          let diastolic = this.getConsistentRandom(patient.id, 'bpDiastolic', 75, 82);

          // Adjust based on conditions
          if (patient.hypertension || patient.headache) {
            systolic += 20;
            diastolic += 10;
          }
          if (patient.anxious) {
            systolic += 10;
            diastolic += 5;
          }
          if (patient.pain) {
            systolic += 8;
            diastolic += 5;
          }
          if (patient.age > 60) {
            systolic += 10;
          }

          return `${systolic}/${diastolic}`;
        }
      },
      temperature: {
        name: 'Temp',
        fullName: 'Temperature',
        icon: 'thermometer',
        unit: '°F',
        unlocked: false,
        measured: false,
        value: null,
        keywords: ['fever', 'chills', 'hot', 'cold', 'sweating', 'temperature', 'warm'],
        generateValue: (patient) => {
          const seed = patient.id.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
          const random = this.seededRandom(seed + 50);

          if (patient.fever || patient.infection) {
            return (99.8 + random * 2.5).toFixed(1); // 99.8-102.3°F
          } else {
            return (97.8 + random * 1.0).toFixed(1); // 97.8-98.8°F
          }
        }
      },
      respiratoryRate: {
        name: 'RR',
        fullName: 'Respiratory Rate',
        icon: 'wind',
        unit: '/min',
        unlocked: false,
        measured: false,
        value: null,
        keywords: ['breath', 'breathing', 'shortness', 'wheeze', 'cough', 'chest', 'respiratory', 'lungs'],
        generateValue: (patient) => {
          const base = this.getConsistentRandom(patient.id, 'respRate', 14, 18);

          // Adjust based on respiratory issues
          let adjustment = 0;
          if (patient.shortnessOfBreath || patient.respiratory) adjustment += 6;
          if (patient.asthma || patient.copd) adjustment += 4;
          if (patient.anxious || patient.panic) adjustment += 5;
          if (patient.fever) adjustment += 3;
          if (patient.chestPain) adjustment += 2;

          return Math.min(base + adjustment, 30); // Cap at 30
        }
      },
      oxygenSaturation: {
        name: 'SpO₂',
        fullName: 'Oxygen Saturation',
        icon: 'droplet',
        unit: '%',
        unlocked: false,
        measured: false,
        value: null,
        keywords: ['breath', 'breathing', 'shortness', 'oxygen', 'dizzy', 'tired', 'fatigue'],
        generateValue: (patient) => {
          let base = this.getConsistentRandom(patient.id, 'spo2', 97, 99);

          // Decrease based on respiratory issues
          if (patient.shortnessOfBreath || patient.respiratory) base -= 5;
          if (patient.asthma || patient.copd) base -= 3;
          if (patient.chestPain && patient.cardiac) base -= 2;

          return Math.max(base, 88); // Don't go below 88%
        }
      },
      weight: {
        name: 'Wt',
        fullName: 'Weight',
        icon: 'scale',
        unit: 'lbs',
        unlocked: false,
        measured: false,
        value: null,
        keywords: ['weight', 'gained', 'lost', 'appetite', 'eating', 'diet'],
        generateValue: (patient) => {
          // Base weight on gender and age
          let base;
          if (patient.gender && patient.gender.toLowerCase() === 'male') {
            base = this.getConsistentRandom(patient.id, 'weight', 160, 190);
          } else {
            base = this.getConsistentRandom(patient.id, 'weight', 130, 160);
          }

          // Adjust for age
          if (patient.age > 60) base -= 10;
          if (patient.age < 30) base -= 5;

          return base;
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

    // Generate consistent, realistic value based on patient data
    vital.value = vital.generateValue(patientContext);
    vital.measured = true;
    vital.timestamp = new Date().toISOString();

    console.log('[VitalsPanel] Measured', vital.name, ':', vital.value, vital.unit);

    return {
      name: vital.name,
      fullName: vital.fullName,
      value: vital.value,
      unit: vital.unit,
      timestamp: vital.timestamp,
      icon: vital.icon
    };
  }

  /**
   * Create seeded random number generator for consistency
   */
  seededRandom(seed) {
    let x = Math.sin(seed++) * 10000;
    return x - Math.floor(x);
  }

  /**
   * Get consistent random value based on patient ID and vital type
   */
  getConsistentRandom(patientId, vitalKey, min, max) {
    const seed = patientId.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0) + vitalKey.length;
    const random = this.seededRandom(seed);
    return min + Math.floor(random * (max - min + 1));
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
        fullName: vital.fullName,
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
