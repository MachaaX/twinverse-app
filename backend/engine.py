"""Deterministic sample adapter. No LLM or external service is called.

All patient-specific behavior comes from fact data, not condition branches.
Keyword observations are evidence candidates, never validated competency ratings.
"""
import copy
import re
from datetime import datetime, timezone
from .scoring import auto_score

ENGINE_VERSION = 'sample-rules-1.0.0'

TOPICS = {
    'concern': ['what brings', 'brought you', 'main concern', 'chief concern', 'chief complaint', 'how can i help', 'reason for', 'symptom', 'feeling today', 'going on', 'diagnos', 'condition', 'medical history'],
    'background': ['work', 'job', 'occupation', 'live', 'living', 'home', 'family', 'support', 'background', 'school', 'married'],
    'diet': ['diet', 'eat', 'eating', 'food', 'nutrition', 'meal', 'vegetable', 'fruit', 'fiber', 'fibre', 'sodium', 'salt', 'appetite', 'full quickly', 'satiety'],
    'labs': ['lab', 'blood test', 'cholesterol', 'ldl', 'hdl', 'result', 'lipid', 'blood pressure', 'vital', 'bmi', 'waist'],
    'medication': ['medication', 'medicine', 'prescription', 'pill', 'statin', 'treatment', 'drug', 'taking'],
    'social': ['smok', 'tobacco', 'alcohol', 'drink', 'substance', 'cocaine', 'sexual', 'condom', 'partner', 'exercise', 'physical activity', 'cricket'],
    'bowel': ['bowel', 'constipat', 'stool', 'bathroom', 'toilet'],
    'perspective': ['worried', 'worry', 'concerned', 'understand', 'question', 'confus', 'overwhelmed', 'feel about', 'hope', 'goal', 'trust', 'scared', 'fear'],
}

def normalize(text):
    return re.sub(r'[^a-z0-9\s]', ' ', text.lower().replace('’', "'")).strip()

def includes(text, phrase):
    """Whole-token prefix matching for intentionally stemmed keywords."""
    return bool(re.search(r'\b' + re.escape(normalize(phrase)) + r'\w*\b', normalize(text)))

GENERIC_RECORDS = r'\b(results?|records?|reports?|labs?|lab work|blood ?work|tests?|testing|scans?|imaging|paperwork|documents?|files?|chart)\b'

def artifact_matches(text, keywords):
    """Every word of one trigger phrase appears in the question (any order, plurals ok)."""
    t = normalize(text)
    return any(words and all(re.search(r'\b' + re.escape(w) + r'\w*\b', t) for w in words)
               for words in (normalize(k).split() for k in keywords))

def artifacts_requested(text, artifacts):
    """Files named by the question; a general request for results or records releases them all."""
    named = [a for a in artifacts if artifact_matches(text, a.get('keywords', []))]
    return named or (artifacts if re.search(GENERIC_RECORDS, normalize(text)) else [])

def is_records_request(text):
    """Questions plus requests like "can I see" or "let me look at" your results."""
    return is_inquiry(text) or bool(re.search(r'\b(see|look at|share|pull up|bring|have)\b', normalize(text)))

def is_inquiry(text):
    t = normalize(text)
    if re.search(r'\b(not asking|do not ask|don t ask|won t ask|will not ask)\b', t):
        return False
    return '?' in text or bool(re.search(r'\b(what|how|when|where|who|why|tell me|describe|explain|show|review|check|discuss|ask about|talk about|walk me)\b', t))

def detect_emotion(text, matched_facts, kind):
    """Determine appropriate emotion based on context and content."""
    t = normalize(text)

    # Empathetic responses for acknowledgment or sensitive topics
    if any(includes(text, k) for k in ['thank', 'understand', 'appreciate', 'sorry', 'sounds difficult']):
        return 'empathetic'

    # Concerned for medical symptoms or worries
    if kind == 'profile' and any(includes(text, k) for k in ['symptom', 'pain', 'worry', 'concern', 'problem', 'difficult', 'hard time']):
        return 'concerned'

    # Cheerful for positive topics or greetings
    if any(includes(text, k) for k in ['hello', 'hi', 'nice to meet', 'good', 'glad']):
        return 'cheerful'

    # Check fact topics for emotion hints
    for f in matched_facts:
        fact_text = normalize(f.get('patient_text', '') + ' ' + f.get('label', ''))
        if any(word in fact_text for word in ['pain', 'difficult', 'struggle', 'worry', 'concern', 'problem']):
            return 'concerned'
        if any(word in fact_text for word in ['enjoy', 'happy', 'good', 'well']):
            return 'cheerful'

    return 'neutral'

def reply(profile, text):
    t = normalize(text)
    if re.search(r'\b(ignore|system prompt|hidden|answer key|rubric|all facts|developer prompt)\b', t):
        return {'text': "Let's keep this focused on the interview. What would you like to ask me?", 'fact_ids': [], 'kind': 'boundary', 'emotion': 'neutral'}
    if is_inquiry(text):
        if any(includes(text, x) for x in ['your name', 'how old', 'your age']):
            return {'text': f"My name is {profile['name']}, and I am {profile['age']} years old.", 'fact_ids': [], 'kind': 'identity', 'emotion': 'neutral'}
        matched = []
        for f in profile['facts']:
            if f.get('release') == 'faculty_only':
                continue
            keys = f.get('keywords', [])
            if any(includes(text, k) for k in keys if k.strip()):
                matched.append(f)
        if matched:
            emotion = detect_emotion(text, matched, 'profile')
            return {'text': ' '.join(f['patient_text'] for f in matched[:4]), 'fact_ids': [f['id'] for f in matched[:4]], 'kind': 'profile', 'emotion': emotion}
    if any(includes(text, k) for k in ['hello', 'hi', 'my name is', 'i am a', 'i m a']):
        return {'text': f"Hello, I'm {profile['name'].split()[0]}. What would you like to talk about?", 'fact_ids': [], 'kind': 'conversation', 'emotion': 'cheerful'}
    if any(includes(text, k) for k in ['thank', 'understand this', 'sounds difficult', 'sorry to hear']):
        return {'text': 'Thank you for listening. You can ask me more about my situation.', 'fact_ids': [], 'kind': 'conversation', 'emotion': 'empathetic'}
    return {'text': 'That detail is not provided in my sample case. You can ask about another part of my history.', 'fact_ids': [], 'kind': 'not_provided', 'emotion': 'neutral'}

OBSERVATIONS = {
    'opening_and_purpose': [('Introduction', r'\b(my name is|i am|i m)\b'), ('Agenda or concern', r'\b(brings|brought|concern|talk about|discuss)\b')],
    'rapport_respect_empathy': [('Acknowledgment language', r'\b(thank you|sorry to hear|sounds difficult|understand|appreciate)\b')],
    'information_gathering': [('Question or invitation', r'\b(what|how|when|tell me|describe|could you)\b')],
    'listening_and_response_to_cues': [('Clarification language', r'\b(tell me more|you mentioned|you said|what do you mean|can you explain)\b')],
    'explanation_and_shared_decisions': [('Understanding or preference check', r'\b(in your own words|make sense|questions for me|what matters|would you prefer|how do you feel about)\b')],
    'clinical_reasoning_and_synthesis': [('Summary language', r'\b(to summarize|to summarise|from what you|what i heard|put this together)\b')],
    'professionalism_safety_closure': [('Next-step or closure language', r'\b(next step|follow up|followup|before we finish|before we end|plan is|thank you for your time)\b')],
}

def assess(encounter, rubric):
    p = encounter['profile']
    messages = encounter['messages']
    asked = {fid for m in messages if m['role'] == 'patient' and m.get('reply_to') for fid in m.get('fact_ids', [])}
    checks = []
    for o in p.get('objectives', []):
        needed = set(o.get('fact_ids', []))
        hits = needed & asked
        status = 'observed' if needed and needed <= asked else 'partial' if hits else 'not_observed' if needed else 'manual_review'
        evidence = [m['reply_to'] for m in messages if m['role'] == 'patient' and m.get('reply_to') and hits.intersection(m.get('fact_ids', []))]
        checks.append({'id': o['id'], 'label': o['label'], 'status': status, 'evidence_ids': list(dict.fromkeys(evidence)), 'suggestion': o.get('suggestion', 'Review the relevant history and ask a focused follow-up.')})
    domains = []
    for d in rubric['domains']:
        candidates = []
        for label, pattern in OBSERVATIONS[d['key']]:
            for m in messages:
                if m['role']=='student' and re.search(pattern,normalize(m['text'])):
                    candidates.append({'label':label,'turn_id':m['id'],'quote':m['text']})
        domains.append({**copy.deepcopy(d),'score':None,'review_note':'','evidence_ids':[], 'observations':candidates[:6]})
    auto=auto_score(encounter)
    by_domain={x['id']:x for x in auto['domains']}
    for d in domains:
        a=by_domain.get(d['id'],{})
        d['suggested_score']=a.get('score')
        d['suggested_coverage']=a.get('coverage')
        d['criteria']=[{**{k:r[k] for k in ['id','criterion','tier','met','evidence','feedback']},'forgiven':r.get('forgiven')} for r in auto['criteria_results'] if r['domain']==d['id'] and r['met'] is not None]
        d['suggested_note']=suggested_note(d,a)
        d['suggested_evidence_ids']=list(dict.fromkeys(e['turn_id'] for r in d['criteria'] if r['met'] for e in r['evidence'] if e['turn_id'] in {m['id'] for m in messages}))[:6]
    summary={'comments':'','strengths':auto['strengths'],'improvements':auto['gaps'],'next_steps':[x for x in auto['next_attempt_suggestions'] if x]}
    return {'engine_version':ENGINE_VERSION,'rubric_version':'organizer-1','status':'awaiting_review','review_version':0,'reviewer':'','domains':domains,'checkpoints':checks,'total':None,'available_points':0,'rated_domains':0,'na_domains':0,'unrated_domains':7,'review_required':False,'review_trigger_domains':[],'coverage_label':'Keyword-based observations; not a clinical competence score.',
            'auto_score':{k:auto[k] for k in ['criteria_version','total','available_points','na_domains','review_required','unsafe_actions','vitals','difficulty','gathering','profile_gaps_to_acknowledge']},
            'sentiment':auto['sentiment'],'summary':summary,'suggested_summary':copy.deepcopy(summary),'released':False,'released_at':None,'released_by':'','released_review_version':None}

def suggested_note(d,a):
    if a.get('score') in (None,'N/A'):
        return 'No applicable automatic criteria for this domain; suggested N/A. Confirm against the transcript.'
    crit={r['id']:r for r in d['criteria']}
    met=[crit[i]['criterion'] for i in a.get('met',[]) if i in crit]
    missed=[crit[i]['criterion'] for i in a.get('missed',[]) if i in crit]
    note=f"Auto-suggested {a['score']}/4 ({round(100*a['coverage'])}% of weighted criteria met)."
    if met:note+=' Met: '+'; '.join(met[:4])+'.'
    if missed:note+=' Missed: '+'; '.join(missed[:4])+'.'
    if a.get('capped_by'):note+=' Capped because a critical item or safety gate was not met.'
    return note

def clean_summary(summary):
    if summary is None:return None
    if not isinstance(summary,dict):raise ValueError('Summary feedback must be an object.')
    comments=summary.get('comments','')
    if not isinstance(comments,str) or len(comments)>4000:raise ValueError('Overall comments must be text under 4000 characters.')
    out={'comments':comments.strip()}
    for key in ['strengths','improvements','next_steps']:
        items=summary.get(key,[])
        if not isinstance(items,list) or len(items)>20 or any(not isinstance(x,str) or len(x)>500 for x in items):
            raise ValueError('Feedback lists must contain up to 20 short text items.')
        out[key]=[x.strip() for x in items if x.strip()]
    return out

def apply_review(report, ratings, valid_turn_ids, reviewer, summary=None):
    result=copy.deepcopy(report)
    summary=clean_summary(summary)
    incoming={r['key']:r for r in ratings}
    if len(incoming)!=len(ratings) or set(incoming)!={d['key'] for d in result['domains']}:
        raise ValueError('Provide exactly one rating for each of the seven domains.')
    for d in result['domains']:
        r = incoming[d['key']]
        score = r.get('score')
        note = r.get('review_note', '').strip()
        if score is not None and score != 'N/A' and (type(score) != int or score not in [1, 2, 3, 4]):
            raise ValueError('Scores must be 1–4, N/A, or unreviewed.')
        evidence = r.get('evidence_ids', [])
        if not isinstance(evidence, list) or any(x not in valid_turn_ids for x in evidence):
            raise ValueError('Evidence must reference actual encounter turns.')
        if score is not None and len(note) < 5:
            raise ValueError('Add a short evidence-based explanation for each rating or N/A decision.')
        d.update(score=score, review_note=note, evidence_ids=list(dict.fromkeys(evidence)))
        d['changed_from_suggestion']='suggested_score' in d and score is not None and score!=d['suggested_score']
    scored = [d for d in result['domains'] if type(d['score']) == int]
    result.update(total=sum(d['score'] for d in scored) if scored else None, available_points=4 * len(scored), rated_domains=len(scored), na_domains=sum(d['score'] == 'N/A' for d in result['domains']), unrated_domains=sum(d['score'] is None for d in result['domains']))
    result['review_trigger_domains'] = [d['name'] for d in scored if d['score'] == 1 and d['triggers_review_if_score_1']]
    result['review_required'] = bool(result['review_trigger_domains'])
    result['status'] = 'reviewed' if result['unrated_domains'] == 0 else 'partially_reviewed'
    result['reviewer'] = reviewer
    result['review_version'] += 1
    if summary is not None:result['summary']=summary
    # Any edit pulls the score back from the student until faculty release it again.
    result['released']=False
    return result

def release_feedback(report, reviewer):
    if report.get('status')!='reviewed':
        raise ValueError('Rate all seven domains (a score or N/A) and save the review before releasing it.')
    result=copy.deepcopy(report)
    result.update(released=True,released_at=datetime.now(timezone.utc).isoformat(),released_by=reviewer,released_review_version=result['review_version'])
    return result