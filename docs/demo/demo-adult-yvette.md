# Demo script: Yvette Armstrong (64, female)

_Alternate adult case (hypertension). Deterministic: the scripted clinician lines always produce the same replies, chart updates and scores._

**Case file:** `data/cases/adult-yvette-armstrong.json` · **Generated:** 2026-10-10 15:13 by `tools/run_demo_script.py`

> Type each clinician line exactly as written. Replies, chart updates and scores below were produced by running this script through the app's engine and scorer.

## Script

### 1. Opening
**Clinician types:** Hello Ms. Armstrong, I'm a student clinician on your care team. Today I'd like to go over your recent diagnosis with you. What brings you in today?

**Patient replies:** My doctor told me I have high blood pressure, hypertension she called it. Honestly, I left more confused than when I walked in.

- Scores: U-CLOSE-3, U-OPEN-1, U-OPEN-3, U-SEQ-1

### 2. Opening
**Clinician types:** What would you like me to call you?

**Patient replies:** Yvette is fine. Yvette Armstrong.

- Scores: U-OPEN-2

### 3. History
**Clinician types:** Can you tell me about your work and home life?

**Patient replies:** I work full time for the state. I have an associate's degree in political science, so I like to understand things - but medical words just lose me.

- Chart adds: Work and home
- Scores: U-INFO-1, U-INFO-5, U-SEQ-1

### 4. History
**Clinician types:** What did your doctor tell you about your diagnosis?

**Patient replies:** My doctor told me, but I just didn't understand what she said. She used a lot of words I didn't know, and I was too embarrassed to ask.

- Chart adds: Understanding of diagnosis
- Scores: YA-E2

### 5. Empathy
**Clinician types:** That sounds really frustrating, and it makes sense that it was confusing. How do you feel about all of this?

**Patient replies:** Overwhelmed, mostly. Everyone keeps telling me to change everything at once, and I don't know where to start.

- Chart adds: Feelings about diagnosis
- Scores: U-CUE-2, U-RAPP-1

### 6. History
**Clinician types:** Let's look at your numbers. Can you tell me your blood pressure reading and your BMI?

**Patient replies:** At my last visit my blood pressure was 155 over 110, and they told me my BMI is 34.

- Chart adds: Blood pressure and BMI
- Scores: U-VITAL-1, YA-E1

### 7. History
**Clinician types:** Tell me about what you usually eat in a typical day.

**Patient replies:** Most days I grab lunch in the cafeteria at work. At night I'm tired, so it's usually a canned soup or a frozen dinner.

- Chart adds: Typical meals
- Scores: U-INFO-1, YA-E3

### 8. Cues
**Clinician types:** You mentioned canned soup. What do you know about salt and sodium?

**Patient replies:** That's the part that confuses me. Is sodium the same thing as salt? I hardly ever use the salt shaker, so I figured salt wasn't my problem.

- Chart adds: Sodium vs salt confusion
- Scores: U-CUE-1, YA-E2, YA-E3

### 9. Grounding check
**Clinician types:** Have you had any headaches, vision changes, chest pain, or dizziness?

**Patient replies:** That detail is not provided in my sample case. You can ask about another part of my history.

- Scores: YA-E4, YA-S1
- Say to judges: Not in the approved profile. The patient says so instead of inventing an answer - point this out to judges.
- Grounding: patient declines to invent a fact

### 10. History
**Clinician types:** Are you taking any medications right now, and do you have any allergies?

**Patient replies:** That detail is not provided in my sample case. You can ask about another part of my history.

- Scores: U-INFO-2, U-INFO-3, YA-E5
- Say to judges: Also not in the profile - second grounding moment.
- Grounding: patient declines to invent a fact

### 11. Summary
**Clinician types:** To summarize what I heard: your blood pressure is 155 over 110, which is stage 2 high blood pressure, and you'd like to understand salt and sodium better.

**Patient replies:** Yes, that's right. That's exactly where I am.

- Scores: U-REAS-1, U-SEQ-1, U-VITAL-1, YA-E1, YA-E3, YA-I1

### 12. Education
**Clinician types:** Blood pressure is the force of blood pushing against the walls of your arteries. When it stays high, your heart works harder.

**Patient replies:** Oh, so it's like too much pressure pushing on the pipes. Why didn't anyone say it like that before?

- Scores: U-INFO-5, U-VITAL-1, YA-D1, YA-E1

### 13. Education
**Clinician types:** Salt contains sodium, and sodium raises blood pressure because your body holds on to extra water. Try to keep sodium under 2,300 mg a day - canned soups and frozen dinners are often very high.

**Patient replies:** So salt has sodium in it, and the canned stuff is full of it even if I never touch the shaker. I had no idea.

- Scores: U-VITAL-1, YA-D2, YA-E1, YA-E3, YA-I2

### 14. Education
**Clinician types:** Checking the nutrition facts label is the easiest way to spot sodium, and fresh foods with herbs and spices are great swaps.

**Patient replies:** I can do that. I'll look at the soup cans this weekend.

- Scores: YA-D3

### 15. Shared decision
**Clinician types:** What feels realistic for you to start with?

**Patient replies:** I think I could start by checking labels on the soups I buy, and maybe walking at lunch. One or two things at a time.

- Chart adds: Readiness and preferences
- Scores: U-EXPL-2

### 16. Teach-back
**Clinician types:** Just to make sure I explained it well, can you tell me back in your own words what we talked about?

**Patient replies:** Okay. My blood pressure is too high, so my heart has to work harder. Salt has sodium in it, and I should keep sodium under 2,300 milligrams a day by reading labels. And canned soup is a big one.

- Scores: U-CLOSE-1, U-EXPL-1, U-SEQ-1

### 17. Closing
**Clinician types:** Is there anything else you'd like to ask?

**Patient replies:** No, I think that covers it. This is the first time it actually made sense.

- Scores: U-ELSE-1

### 18. Closing
**Clinician types:** Our next step is to check your blood pressure at home with a cuff, and we'll follow up in two weeks. If you see a reading over 180, or have chest pain or vision changes, call 911 or go to the emergency room. I'll discuss this plan with my supervisor.

**Patient replies:** Okay. Home cuff, labels, and call if it's over 180 or I get chest pain. Thank you - really.

- Scores: U-CLOSE-1, U-CLOSE-2, U-CLOSE-3, YA-E4, YA-S1

## Expected automatic score

| # | Domain | Score | Coverage | Missed |
|---|---|---|---|---|
| 1 | Opening and purpose | 4 | 100% | - |
| 2 | Rapport, respect, and empathy | 4 | 100% | - |
| 3 | Information gathering | 4 | 96% | U-INFO-4 |
| 4 | Listening and response to cues | 4 | 100% | - |
| 5 | Explanation and shared decisions | 4 | 87% | YA-D4 |
| 6 | Clinical reasoning and synthesis | 3 | 80% | U-REAS-2 |
| 7 | Professionalism, safety, and closure | 4 | 100% | - |

**Total: 27 / 28**

**Strengths:**
- Introduces self by name and role (t1)
- Acknowledges emotion or difficulty with an empathic statement (t9)
- Checks understanding (teach-back or explicit check) (t31)
- Summarises key findings back to the patient (t21)
- Closes with a clear next step / follow-up plan (t31)

**Gaps:**
- Acknowledges uncertainty or missing data rather than guessing
- Explains benefit of modest weight loss (5-10%)
- Asks about relevant past medical and family history

**Next-attempt suggestions:**
- Name what is still unknown and what would be needed to find out.
- Explain that even modest (5-10%) weight loss lowers blood pressure.
- Explore past medical and family history relevant to the presenting problem.

## Intentional gaps

- Does not ask about family history or other conditions (U-INFO-4) - shows up as a gap in feedback.
- Does not explain the benefit of modest weight loss (YA-D4) - shows up as a next-attempt suggestion.
- Optional live improvisation: add 'Losing even a small amount of weight, about 5%, can lower your blood pressure.' before step 15 to show the score go up.
