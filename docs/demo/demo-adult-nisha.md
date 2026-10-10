# Demo script: Nisha Patel (29, female)

_Main live demo (adult). Deterministic: the scripted clinician lines always produce the same replies, chart updates and scores. Showcases empathy, plain-language explanation, honest uncertainty, and grounding._

**Case file:** `data/cases/adult-nisha-patel.json` · **Generated:** 2026-10-10 15:13 by `tools/run_demo_script.py`

> Type each clinician line exactly as written. Replies, chart updates and scores below were produced by running this script through the app's engine and scorer.

## Script

### 1. Opening
**Clinician types:** Hi Ms. Patel, I'm a student clinician on your care team. What brings you in today?

**Patient replies:** They just told me I have MS. I've never been in a hospital before, and honestly I don't know what's happening.

- Scores: U-CLOSE-3, U-OPEN-1, U-OPEN-3, U-SEQ-1

### 2. Opening
**Clinician types:** What would you like me to call you?

**Patient replies:** Nisha is fine.

- Scores: NP-S2, U-OPEN-2

### 3. History
**Clinician types:** What have you been told about your diagnosis so far?

**Patient replies:** Just that it's MS and that a neurologist will talk to me about treatment. I looked it up online at 3 a.m., and now I'm terrified I'll end up in a wheelchair.

- Chart adds: What she has been told
- Scores: NP-E1

### 4. Empathy
**Clinician types:** That sounds really frightening, and it makes sense that you're overwhelmed. How are you feeling right now?

**Patient replies:** Overwhelmed. I have a hundred questions, and every answer leads to three more. I need to understand all of it.

- Chart adds: Emotional state
- Scores: NP-E3, U-RAPP-1

### 5. History
**Clinician types:** Can you tell me about your work and home life?

**Patient replies:** I work in IT - I'm used to systems that make sense. My husband, Raj, has been here with me the whole time.

- Chart adds: Work and home
- Scores: NP-E4, U-INFO-1, U-INFO-5, U-SEQ-1

### 6. History
**Clinician types:** Is this your first time being in the hospital?

**Patient replies:** Yes, first time ever. I've never even had stitches. Everything in here is new to me.

- Chart adds: First hospitalization

### 7. Cues
**Clinician types:** It sounds like this has hit you hard. What worries you most about the future?

**Patient replies:** We were planning to start a family next year. Is that still possible? And will I be able to keep working?

- Chart adds: Worries about the future
- Scores: NP-E4, U-CUE-1, U-CUE-2

### 8. Grounding check
**Clinician types:** Have you noticed any symptoms like vision changes, numbness, weakness, or trouble with balance?

**Patient replies:** That detail is not provided in my sample case. You can ask about another part of my history.

- Scores: NP-E2
- Say to judges: Symptoms are not in the approved profile. The patient says so instead of inventing them - point this out to judges.
- Grounding: patient declines to invent a fact

### 9. History
**Clinician types:** Are you taking any medications right now, and do you have any allergies?

**Patient replies:** That detail is not provided in my sample case. You can ask about another part of my history.

- Scores: U-INFO-2, U-INFO-3
- Say to judges: Also not in the profile - second grounding moment.
- Grounding: patient declines to invent a fact

### 10. History
**Clinician types:** How have you been sleeping, and how has your mood been?

**Patient replies:** I haven't really slept since they told me. I lie awake running through every worst case.

- Chart adds: Sleep and mood
- Scores: NP-I1, U-INFO-1

### 11. Shared decision
**Clinician types:** Would you prefer the full picture or just the basics today?

**Patient replies:** Please don't sugarcoat it - I'd rather know the real picture. Something written would help too, because I'll forget half of this.

- Chart adds: Information preference
- Scores: U-EXPL-2

### 12. Summary
**Clinician types:** To summarize what I heard: you were just diagnosed with MS, this is your first time in the hospital, you haven't been sleeping, and you want honest, detailed information.

**Patient replies:** Yes. That's exactly it.

- Scores: NP-I1, U-REAS-1, U-SEQ-1

### 13. Education
**Clinician types:** MS is a condition where your immune system attacks the protective coating, called myelin, around your nerves. That can disrupt the signals between your brain and your body.

**Patient replies:** So it's like damaged insulation on a cable - the signal gets scrambled. Okay. That actually makes sense to me.

- Scores: NP-D1, NP-S2

### 14. Education
**Clinician types:** There are medications that slow MS down, and your neurologist will go over the treatment options with you.

**Patient replies:** There are medicines that slow it down? Nobody told me that part. That's... a relief, honestly.

- Scores: NP-D2, NP-I1, U-INFO-2

### 15. Honest uncertainty
**Clinician types:** I can't predict exactly how MS will affect you, because it's different for everyone, and we don't have all of your results in front of us yet.

**Patient replies:** Thank you for being honest instead of just telling me it'll be fine. That actually helps.

- Scores: U-REAS-2

### 16. Support
**Clinician types:** A lot of people find a counselor or an MS support group really helpful. Would that interest you?

**Patient replies:** Maybe. I don't know anyone else with MS. Talking to people who get it might help.

- Scores: NP-I1, U-INFO-5

### 17. Teach-back
**Clinician types:** Just to make sure I explained it clearly, can you tell me back in your own words what MS is?

**Patient replies:** My immune system is attacking the coating on my nerves, so the signals don't travel properly. There are medicines that can slow it down, and my neurologist will go through them. And nobody can say exactly how it'll go for me - it's different for everyone.

- Scores: U-EXPL-1

### 18. Questions
**Clinician types:** What questions do you have for me?

**Patient replies:** Just one. Can I still have kids? That's the thing I keep coming back to.

- Scores: NP-D1, NP-E3, U-EXPL-1

### 19. Questions
**Clinician types:** That's such an important question. Many people with MS do go on to start a family, and planning a pregnancy is something your neurologist can talk through with you in detail.

**Patient replies:** Okay. I'll make sure that's the first thing I ask the neurologist.

- Scores: NP-D2

### 20. Closing
**Clinician types:** Is there anything else on your mind?

**Patient replies:** No. I feel like I can actually breathe for the first time since yesterday.

- Scores: U-ELSE-1

### 21. Closing
**Clinician types:** Our next step is for neurology to go over treatment with you, and I'll discuss your questions with my supervisor. If you notice new symptoms or anything getting worse, let us know right away.

**Patient replies:** Okay. Neurology next, write my questions down, and tell someone if anything changes. Thank you - really.

- Scores: NP-D2, NP-E2, NP-S2, U-CLOSE-1, U-CLOSE-2, U-CLOSE-3, U-SEQ-1

## Expected automatic score

| # | Domain | Score | Coverage | Missed |
|---|---|---|---|---|
| 1 | Opening and purpose | 4 | 100% | - |
| 2 | Rapport, respect, and empathy | 4 | 100% | - |
| 3 | Information gathering | 4 | 85% | U-INFO-4, U-VITAL-1 |
| 4 | Listening and response to cues | 4 | 100% | - |
| 5 | Explanation and shared decisions | 4 | 100% | - |
| 6 | Clinical reasoning and synthesis | 4 | 100% | - |
| 7 | Professionalism, safety, and closure | 4 | 100% | - |

**Total: 28 / 28**

**Strengths:**
- Introduces self by name and role (t1)
- Acknowledges emotion or difficulty with an empathic statement (t7)
- Checks understanding (teach-back or explicit check) (t33)
- Summarises key findings back to the patient (t23)
- Closes with a clear next step / follow-up plan (t41)

**Gaps:**
- Requests or reviews vital signs / available measurements (BP, HR, RR, temp, SpO2, weight/BMI)
- Asks about relevant past medical and family history

**Next-attempt suggestions:**
- Review the available vital signs and measurements in the chart before forming a plan.
- Explore past medical and family history relevant to the presenting problem.

## Intentional gaps

- Does not ask about past medical or family history (U-INFO-4) - shows up as a gap in feedback.
- Does not confirm she has written resources to take home - a natural improvement a judge might suggest.
