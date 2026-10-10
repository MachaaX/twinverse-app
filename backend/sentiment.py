"""Conversation-quality and sentiment signals. Deterministic and explainable:
every judgement points at the turn that caused it, so faculty can check it.

Student side: tone per turn (warm / neutral / cold), empathy statements, open vs
closed questions, unexplained medical jargon. Patient side: how open each reply
is and whether the patient opened up or closed down over the conversation.
"""
import re
from datetime import datetime

FEELINGS = r'(overwhelm\w*|scar\w*|worr\w*|frustrat\w*|confus\w*|upset|hard|difficult|tough|stressful|frightening|exhausting|a lot)'
# Patterns, not fixed phrases, so "that sounds confusing" and "it makes sense to feel..." both count.
EMPATHY = [r'\b(that|it|this) (sounds|seems|must be|must feel)\b', r'\bsounds like\b', r'\bmakes sense\b', r'\bmust (be|feel)\b',
           r'\bi can (imagine|see|understand|tell)\b', r'\bi understand\b', r'\b(i\'m|i am) (so |really )?sorry\b', r'\bi hear you\b',
           r'\bthat\'s fair\b', r'\btake your time\b', r'\b(feel|feeling|felt) ' + FEELINGS, r'\bi know (it|this|that)\b',
           r'\bthank you for (sharing|telling|being)\b', r'\bno wonder\b']
WARM = EMPATHY + [r'\bthank(s| you)\b', r'\bplease\b', r'\bglad\b', r'\bno rush\b', r'\bi appreciate\b', r'\bgood question\b',
                  r'\bis it okay if\b', r'\bwould you be comfortable\b', r"\byou don\'t have to\b", r"\b(it\'s|that\'s) okay\b",
                  r"\bwhenever you\'re ready\b", r'\byou mentioned\b', r'\btogether\b', r'\bgreat\b']
COLD = ['you should have', "why didn't you", 'why would you', 'noncompliant', 'non-compliant', 'lazy', 'obviously',
        'calm down', "that's not true", "you're wrong", 'no excuse', 'just answer', 'whatever', 'stop being', 'not my problem']
DIRECTIVE = ['you need to', 'you have to', 'you must', 'you should']
JARGON = ['etiology', 'prognosis', 'comorbid', 'comorbidity', 'hyperlipidemia', 'dyslipidemia', 'glycemic', 'hba1c', 'sensorineural',
          'nyha', 'idiopathic', 'contraindicated', 'titrate', 'pathophysiology', 'myocardial', 'renal', 'hepatic', 'neuropathy',
          'nephropathy', 'retinopathy', 'hypoglycemia', 'hyperglycemia', 'ejection fraction', 'differential', 'bilateral',
          'tinnitus', 'hyperacusis', 'audiometry', 'htn', 'chf', 'copd', 'dm2', 'prn', 'bid', 'tid', 'npo']
EXPLAINERS = ['which means', 'that means', 'in other words', 'basically', 'in plain terms', 'meaning', 'which is', 'also called',
              'is when', 'in simple terms', 'put simply']
OPEN_START = r'^(what|how|why|tell me|describe|walk me|can you tell|could you tell|could you describe|can you describe|help me understand|what\'s)'
CLOSED_START = r'^(do|does|did|are|is|was|were|have|has|had|can|could|will|would|any|ever)\b'
GUARDED = ["i'd rather not", "i don't want to", "that's all i'm gonna say", "that's all i'm going to say", 'no promises',
           "i don't know", 'not really', "doesn't matter", "i'm fine", 'whatever', 'why do you need', "none of your", "i don't get"]
POSITIVE = ['i appreciate', 'i get it', 'thank you', 'thanks', 'maybe we can', 'i guess', 'okay', 'i want to know', 'that helps',
            'i can try', "i'll think about it", 'makes sense']


def _norm(text):
    return re.sub(r'\s+', ' ', text.lower().replace('’', "'")).strip()


def _hits(text, phrases):
    t = _norm(text)
    return [p for p in phrases if re.search(r'(?<![a-z])' + re.escape(p) + r'(?![a-z])', t)]


def _matches(text, patterns):
    t = _norm(text)
    return [m.group(0) for m in (re.search(p, t) for p in patterns) if m]


def _questions(text):
    """Split a turn into question sentences and classify each as open or closed."""
    out = []
    for sentence in re.split(r'(?<=[.?!])\s+', _norm(text)):
        if not sentence.endswith('?'):
            continue
        s = re.sub(r'^(so|and|but|okay|ok|well|also|now)[, ]+', '', sentence)
        out.append('open' if re.match(OPEN_START, s) else 'closed' if re.match(CLOSED_START, s) else 'open')
    return out


def _time(value):
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def analyze(messages, profile=None):
    profile = profile or {}
    turns, patient_turns = [], []
    for m in messages:
        if m['role'] == 'student':
            warm, cold, directive = _matches(m['text'], WARM), _hits(m['text'], COLD), _hits(m['text'], DIRECTIVE)
            score = len(warm) - 2 * len(cold) - len(directive)
            jargon = [] if _hits(m['text'], EXPLAINERS) else _hits(m['text'], JARGON)
            turns.append({'turn_id': m['id'], 'tone': 'cold' if score <= -2 or cold else 'warm' if score >= 1 else 'neutral',
                          'warm': list(dict.fromkeys(warm)), 'cold': cold + directive, 'empathy': bool(_matches(m['text'], EMPATHY)),
                          'questions': _questions(m['text']), 'jargon': jargon})
        elif m['role'] == 'patient' and m.get('reply_to'):
            guarded, positive = _hits(m['text'], GUARDED), _hits(m['text'], POSITIVE)
            words = len(m['text'].split())
            score = (1 if words > 15 else 0) + len(positive) - 2 * len(guarded) + len(m.get('fact_ids') or [])
            patient_turns.append({'turn_id': m['id'], 'openness': score, 'guarded': guarded})
    questions = [q for t in turns for q in t['questions']]
    open_q = questions.count('open')
    sensitive = {f['id'] for f in profile.get('facts', []) if f.get('sensitivity') == 'sensitive' and f.get('release') == 'question'}
    disclosed = {fid for m in messages if m['role'] == 'patient' for fid in m.get('fact_ids') or []}
    trajectory, start, end = 'n/a', None, None
    if len(patient_turns) >= 3:
        half = len(patient_turns) // 2
        start = sum(t['openness'] for t in patient_turns[:half]) / half
        end = sum(t['openness'] for t in patient_turns[half:]) / (len(patient_turns) - half)
        trajectory = 'opened up' if end - start > 0.5 else 'closed down' if start - end > 0.5 else 'steady'
    times = [_time(m.get('timestamp')) for m in messages if m.get('timestamp')]
    first_student = next((_time(m.get('timestamp')) for m in messages if m['role'] == 'student' and m.get('timestamp')), None)
    duration = int((max(t for t in times if t) - first_student).total_seconds()) if first_student and any(times) else None
    student = {'turns': len(turns), 'warm': sum(t['tone'] == 'warm' for t in turns), 'neutral': sum(t['tone'] == 'neutral' for t in turns),
               'cold': sum(t['tone'] == 'cold' for t in turns), 'empathy_statements': sum(t['empathy'] for t in turns),
               'questions': len(questions), 'open_questions': open_q, 'closed_questions': len(questions) - open_q,
               'open_ratio': round(open_q / len(questions), 2) if questions else None,
               'unexplained_jargon': [{'turn_id': t['turn_id'], 'term': j} for t in turns for j in t['jargon']]}
    patient = {'replies': len(patient_turns), 'trajectory': trajectory, 'start': start, 'end': end,
               'guarded_replies': [t['turn_id'] for t in patient_turns if t['guarded']],
               'sensitive_total': len(sensitive), 'sensitive_disclosed': len(sensitive & disclosed), 'turns': patient_turns}
    return {'student': student, 'patient': patient, 'turns': turns, 'duration_seconds': duration, 'summary': summarize(student, patient)}


def summarize(student, patient):
    lines = []
    if student['turns']:
        lines.append(f"Tone: {student['warm']} warm, {student['neutral']} neutral, {student['cold']} cold of {student['turns']} messages; "
                     f"{student['empathy_statements']} empathy statement{'s' if student['empathy_statements'] != 1 else ''}.")
    if student['questions']:
        lines.append(f"Questions: {student['open_questions']} open, {student['closed_questions']} closed.")
    if student['unexplained_jargon']:
        lines.append('Unexplained jargon: ' + ', '.join(sorted({j['term'] for j in student['unexplained_jargon']})) + '.')
    if patient['trajectory'] != 'n/a':
        lines.append(f"Patient {patient['trajectory']} over the conversation"
                     + (f"; shared {patient['sensitive_disclosed']} of {patient['sensitive_total']} sensitive topics." if patient['sensitive_total'] else '.'))
    return lines


def criteria(analysis):
    """Rubric criteria driven by the analysis: (criterion, met or None, evidence)."""
    s, p, turns = analysis['student'], analysis['patient'], analysis['turns']
    out = []
    if s['turns']:
        warm_ids = [t['turn_id'] for t in turns if t['tone'] == 'warm']
        cold_ids = [t['turn_id'] for t in turns if t['tone'] == 'cold']
        met = not cold_ids and len(warm_ids) >= max(1, round(0.2 * s['turns']))
        out.append(({'id': 'S-TONE', 'domain': 2, 'tier': 'important', 'criterion': 'Keeps a warm, respectful tone throughout',
                     'feedback_if_missed': (f"Some messages read as cold or directive ({', '.join(cold_ids)}). " if cold_ids else '')
                     + 'Use more validating language: acknowledge, thank, and reflect what the patient says.'},
                    met, [{'turn_id': t, 'quote': 'cold tone'} for t in cold_ids] if cold_ids else [{'turn_id': t, 'quote': 'warm tone'} for t in warm_ids[:4]]))
    if s['questions'] >= 3:
        ids = [t['turn_id'] for t in turns if 'open' in t['questions']]
        out.append(({'id': 'S-OPEN', 'domain': 3, 'tier': 'supplementary', 'criterion': 'Balances open and closed questions',
                     'feedback_if_missed': 'Start topics with open questions ("Tell me about…", "How has…") before narrowing down.'},
                    s['open_ratio'] >= 0.3, [{'turn_id': t, 'quote': 'open question'} for t in ids[:4]]))
    if s['turns']:
        jargon = s['unexplained_jargon']
        out.append(({'id': 'S-JARGON', 'domain': 5, 'tier': 'important', 'criterion': 'Explains medical terms instead of using unexplained jargon',
                     'feedback_if_missed': 'Explain terms like ' + ', '.join(sorted({j['term'] for j in jargon})[:3]) + ' in plain language, or skip them.' if jargon else ''},
                    not jargon, [{'turn_id': j['turn_id'], 'quote': f"jargon: {j['term']}"} for j in jargon[:4]] or [{'turn_id': '-', 'quote': 'no unexplained jargon'}]))
    if p['replies'] >= 3:
        met = p['trajectory'] != 'closed down' and (p['sensitive_total'] == 0 or p['sensitive_disclosed'] > 0)
        out.append(({'id': 'S-TRUST', 'domain': 4, 'tier': 'supplementary', 'criterion': 'Patient opens up as the conversation goes on',
                     'feedback_if_missed': 'The patient stayed guarded. Build trust with empathy and patience before sensitive questions.'},
                    met, [{'turn_id': p['turns'][-1]['turn_id'], 'quote': f"patient {p['trajectory']}"}]))
    return out
