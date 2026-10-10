# Demo script: Sofia Reyes (9, female)

_Backup demo (pediatric). Built on the organizer's Pediatric Hearing Treatment rubric; a parent is present and answers alongside the child._

**Case file:** `data/cases/child-sofia-reyes.json` · **Generated:** 2026-10-10 16:49 by `tools/run_demo_script.py`

> Type each clinician line exactly as written. Replies, chart updates and scores below were produced by running this script through the app's engine and scorer.

## Script

### 1. Introduction
**Clinician types:** Hi Sofia, hi Mom, it's nice to meet you both. I'm a student speech-language pathologist.

**Patient replies:** Sofia: Hi. Mom: Thank you for seeing us.

- Scores: PED-I1, U-OPEN-1, U-SEQ-1

### 2. Introduction
**Clinician types:** Sofia, what would you like me to call you?

**Patient replies:** Sofia: Sofia. Mom: And I'm Elena, her mom.

- Scores: PED-I1, S-OPEN, U-OPEN-2

### 3. Introduction
**Clinician types:** What brings you in today?

**Patient replies:** Mom: Her audiologist said working with a speech-language pathologist could help her follow along better at school. Sofia: My teacher says I'm not listening, but I am.

- Scores: S-OPEN, U-OPEN-3

### 4. Needs assessment
**Clinician types:** When did you find out about Sofia's hearing loss?

**Patient replies:** Mom: We found out when she was 3. She wasn't talking as much as other kids, so her pediatrician sent us for a hearing test.

- Chart adds: Age at diagnosis
- Scores: PED-I1, PED-N1, S-OPEN

### 5. Needs assessment
**Clinician types:** Sofia, tell me about your hearing aids. When do you wear them?

**Patient replies:** Sofia: I wear them at school, but I take them off at recess because they whistle when I run. Mom: She wears them most of the day, just not for sports.

- Chart adds: Hearing device use
- Scores: PED-I1, PED-N2, S-OPEN, U-INFO-1, U-SEQ-1

### 6. Needs assessment
**Clinician types:** Do your ears ever ring or buzz, or do loud sounds bother you?

**Patient replies:** Sofia: Sometimes at night my ears ring, like a buzzing sound. Loud noises don't bother me, though.

- Chart adds: Other auditory complaints
- Scores: PED-N3

### 7. Needs assessment
**Clinician types:** You mentioned your teacher, Sofia. How are things going at school?

**Patient replies:** Mom: She has an IEP, so she sits up front, but there's no microphone system for the teacher yet. Group work is the hardest for her.

- Chart adds: Educational needs
- Scores: PED-N4, S-TONE, U-CUE-1

### 8. Needs assessment
**Clinician types:** Sofia, what's the hardest part about listening for you right now?

**Patient replies:** Sofia: When everyone talks at once I can't follow, and my friends get annoyed when I keep saying 'what?'

- Chart adds: Main communication challenge
- Scores: PED-N5

### 9. Feelings
**Clinician types:** How do you feel about all of this?

**Patient replies:** Sofia: Sometimes I feel dumb when I miss stuff. Mom: I just don't want her to fall behind or feel left out.

- Chart adds: Feelings
- Scores: U-CUE-2

### 10. Empathy
**Clinician types:** That must be hard, and you're not dumb at all - your ears just have to work extra hard.

**Patient replies:** Sofia: Yeah... thanks. Mom: That means a lot to her.

- Scores: PED-X4, S-TONE, U-INFO-5, U-RAPP-1

### 11. Audiogram
**Clinician types:** Mom, could we look at her audiogram together?

**Patient replies:** Mom: I brought her last hearing test. To be honest, I've never understood the graph.

- Chart adds: Audiogram
- Scores: PED-A1, S-TONE

### 12. Audiogram
**Clinician types:** This shows a moderate-to-severe hearing loss in both ears, mostly for soft, high-pitched sounds.

**Patient replies:** Mom: So that's why she hears my voice but misses some words. That finally makes sense.

- Scores: PED-A2

### 13. Audiogram
**Clinician types:** This curved area is the speech banana. With your hearing aids, most speech sounds land inside it, but soft sounds like 's' and 'f' are still hard to catch without them.

**Patient replies:** Sofia: So with my hearing aids I hear most words, but the quiet 's' and 'f' sounds still sneak past? Mom: That explains so much.

- Scores: PED-A2, PED-A3, PED-N2, S-TONE

### 14. Expectations
**Clinician types:** What are you hoping we can work on together?

**Patient replies:** Mom: Honestly, I'm hoping therapy will fix her hearing. And I'm not sure how what you do is different from her audiologist.

- Chart adds: Family expectations and questions
- Scores: U-CUE-2, U-INFO-5

### 15. Expectations
**Clinician types:** Your audiologist tests your hearing and adjusts your hearing aids. As a speech-language pathologist, I help you get the most out of what you hear.

**Patient replies:** Mom: Okay, so the audiologist handles the testing and the hearing aids, and you help her use what she hears.

- Scores: PED-N2, PED-X1

### 16. Expectations
**Clinician types:** Aural rehab is listening practice - games and strategies to help you follow conversations in noisy places. To be realistic, it won't fix your hearing, but it can make school and friends a lot easier.

**Patient replies:** Sofia: So like listening games? That sounds kind of fun.

- Scores: PED-N4, PED-X2, PED-X3

### 17. Teach-back
**Clinician types:** Mom, can you tell me back in your own words what we talked about?

**Patient replies:** Mom: Her hearing loss is moderate to severe, mostly for high, soft sounds. The hearing aids help, but she still misses sounds like 's' and 'f'. Your job is to help her listen better, not to fix her hearing.

- Scores: U-EXPL-1, U-SEQ-1

### 18. Questions
**Clinician types:** What questions do you have for me?

**Patient replies:** Mom: Could a microphone for the teacher help? Sofia: Can I still play soccer?

- Scores: PED-X5, U-EXPL-1

### 19. Closing
**Clinician types:** Great questions. Our next step is to meet weekly, and I'll talk with your audiologist and school about a microphone for your teacher. See you next session, Sofia!

**Patient replies:** Mom: That sounds like a good plan. See you next week. Sofia: Bye!

- Scores: PED-N4, PED-X1, U-CLOSE-1, U-SEQ-1

## Expected automatic score

| # | Domain | Score | Coverage | Missed |
|---|---|---|---|---|
| 1 | Opening and purpose | 4 | 100% | - |
| 2 | Rapport, respect, and empathy | 4 | 100% | - |
| 3 | Information gathering | 4 | 100% | U-INFO-4 |
| 4 | Listening and response to cues | 3 | 67% | U-ELSE-1, S-TRUST |
| 5 | Explanation and shared decisions | 4 | 87% | U-EXPL-2 |
| 6 | Clinical reasoning and synthesis | 2 | 42% | U-REAS-1, U-REAS-2, SYN-1 |
| 7 | Professionalism, safety, and closure | 2 | 50% | U-CLOSE-2, U-CLOSE-3 |

**Total: 23 / 28**

**Case point rubric:**

| Section | Points | Met |
|---|---|---|
| Introduce yourself to the client | 10 / 10 | U-OPEN-1, PED-I1, U-RAPP-2 |
| Needs assessment | 30 / 30 | PED-N1, PED-N2, PED-N3, PED-N4, PED-N5 |
| Review the audiogram | 30 / 30 | PED-A1, PED-A2, PED-A3 |
| Realistic expectations for aural rehab | 30 / 30 | PED-X1, PED-X2, PED-X3, PED-X4, PED-X5 |

**Case points: 100 / 100**

**Strengths:**
- Introduces self by name and role (t1)
- Acknowledges emotion or difficulty with an empathic statement (t19)
- Checks understanding (teach-back or explicit check) (t33)
- Closes with a clear next step / follow-up plan (t37)
- Asks age at diagnosis of hearing loss (t7)

**Gaps:**
- Summarises key findings back to the patient
- Involves the patient in decisions / explores readiness and preferences
- Acknowledges uncertainty or missing data rather than guessing
- Safety-nets: tells patient which symptoms need urgent care
- Asks 'anything else?' before closing

**Next-attempt suggestions:**
- Summarise the key findings before moving to explanation or plan.
- Offer options and ask what feels realistic, rather than prescribing a single plan.
- Name what is still unknown and what would be needed to find out.

## Intentional gaps

- Does not summarize findings back to the family (U-REAS-1) - shows up as a gap.
- Does not safety-net (when to contact the audiologist sooner, e.g. sudden hearing change) - shows up as a gap.
