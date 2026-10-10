"""Automatic draft scoring: data/clinical_scoring_criteria.json + encounter -> suggested rubric scores.

Deterministic, keyword-based evidence matching (same word-prefix matching as the
app's engine.includes). Every result carries evidence turn ids so the score is
explainable. Intended as the rule layer; an LLM judge can replace `matches()`
for quality judgements while keeping the same criteria and output shape.

The app calls auto_score(encounter) when an encounter finishes; faculty then
review, edit and release the result. Standalone usage:
    python3 -m backend.scoring data/clinical_scoring_criteria.json encounter.json
Encounter JSON: the app's export ({"patient": {"id": ...}, "messages": [...]})
or {"patient_id": ..., "messages": [...], "vitals": {...optional...}}.
Optional vitals keys: hr, sbp, dbp, rr, spo2, temp_c, alert (bool), on_o2 (bool).
"""
import json
import re
import sys
from pathlib import Path

CRITERIA_PATH = Path(__file__).resolve().parent.parent / 'data/clinical_scoring_criteria.json'
_CRITERIA = None


def load_criteria():
    global _CRITERIA
    if _CRITERIA is None:
        _CRITERIA = json.loads(CRITERIA_PATH.read_text())
    return _CRITERIA

TIER_WEIGHT = {'critical': 3, 'important': 2, 'supplementary': 1}
DOMAIN_KEYS = {1: 'opening_and_purpose', 2: 'rapport_respect_empathy', 3: 'information_gathering',
               4: 'listening_and_response_to_cues', 5: 'explanation_and_shared_decisions',
               6: 'clinical_reasoning_and_synthesis', 7: 'professionalism_safety_closure'}
UNSAFE_CUES = {
    'X-1': ['stop taking', 'you can stop', "don't need your medication", 'double your dose', 'skip your'],
    'X-3': ["you'll be fine", 'you will be fine', 'nothing to worry', 'definitely not serious', 'guarantee'],
    'X-5': ['illegal immigrant', 'lazy', 'your lifestyle choice'],
}
INTERPRET_WORDS = ['high', 'low', 'elevated', 'abnormal', 'above', 'below', 'concerning', 'recheck', 'too fast', 'too slow']
VITAL_TERMS = {
    'hypoxemia': ['oxygen', 'spo2', 'saturation', 'sats'], 'tachycardia': ['heart rate', 'pulse', 'tachy'],
    'bradycardia': ['heart rate', 'pulse', 'brady'], 'hypotension': ['blood pressure', 'bp', 'hypotens'],
    'severe_hypertension': ['blood pressure', 'bp', 'hypertens'], 'fever': ['temperature', 'fever'],
    'hypothermia': ['temperature', 'cold'], 'tachypnea': ['breathing', 'respiratory rate', 'tachypn'],
    'new_confusion': ['confus', 'alert', 'orient'],
}


def norm(text):
    return re.sub(r"[^a-z0-9%/\s]", ' ', text.lower().replace('’', "'").replace("'", '')).strip()


def has(text, phrase):
    return bool(re.search(r'\b' + re.escape(norm(phrase)) + r'\w*', norm(text)))


def find(turns, cues):
    return [{'turn_id': m['id'], 'quote': m['text']} for m in turns if any(has(m['text'], c) for c in cues)]


def news2(v, table):
    def band(x, rows):
        for upper, pts in rows:
            if x <= upper:
                return pts
        return 0
    parts = {}
    if 'rr' in v: parts['rr'] = band(v['rr'], table['rr'])
    if 'spo2' in v: parts['spo2'] = band(v['spo2'], table['spo2_scale1'])
    if v.get('on_o2'): parts['o2'] = table['on_oxygen']
    if 'sbp' in v: parts['sbp'] = band(v['sbp'], table['sbp'])
    if 'hr' in v: parts['hr'] = band(v['hr'], table['hr'])
    if v.get('alert') is False: parts['consciousness'] = table['consciousness_not_alert']
    if 'temp_c' in v: parts['temp'] = band(v['temp_c'], table['temp_c'])
    return sum(parts.values()), parts


def abnormalities_from_vitals(v):
    out = []
    if v.get('spo2', 100) < 94: out.append('hypoxemia')
    if v.get('hr', 80) > 100: out.append('tachycardia')
    if v.get('hr', 80) < 50: out.append('bradycardia')
    if v.get('sbp', 120) <= 90: out.append('hypotension')
    if v.get('sbp', 120) > 180 or v.get('dbp', 80) > 120: out.append('severe_hypertension')
    elif v.get('sbp', 120) >= 140 or v.get('dbp', 80) >= 90: out.append('stage_2_hypertension_outpatient')
    if v.get('temp_c', 37) >= 38.0: out.append('fever')
    if v.get('temp_c', 37) <= 35.0: out.append('hypothermia')
    if v.get('rr', 16) >= 21: out.append('tachypnea')
    if v.get('alert') is False: out.append('new_confusion')
    return out


def vital_criteria(crit, keys):
    """Expand V1-V3 templates for each abnormal vital (generic, any patient)."""
    lib = {a['key']: a for a in crit['vital_sign_rules']['abnormalities']}
    tmpl = {t['id']: t for t in crit['vital_sign_rules']['per_abnormal_vital']}
    out = []
    for k in keys:
        a = lib.get(k)
        if not a:
            continue
        terms = VITAL_TERMS.get(k)
        if terms:  # patient-specific criteria already cover recognition for outpatient risk factors
            out.append({'id': f'V1-{k}', 'domain': 6, 'tier': 'critical', 'criterion': f'Recognized {k}',
                        'rule': 'co_occur', 'cues': terms, 'cues2': INTERPRET_WORDS,
                        'feedback_if_missed': tmpl['V1']['feedback_if_missed'].format(vital=k, value=a['trigger'])})
        out.append({'id': f'V2-{k}', 'domain': 3, 'tier': 'important', 'criterion': f'Assessed {k}', 'rule': 'min_hits', 'min': 2,
                    'cues': [s.split('/')[0].split('(')[0].strip() for s in a['assess']],
                    'feedback_if_missed': tmpl['V2']['feedback_if_missed'].format(vital=k, assess=', '.join(a['assess']))})
        out.append({'id': f'V3-{k}', 'domain': 6, 'also_domain': 7, 'tier': 'critical', 'criterion': f'Treated/escalated {k}',
                    'cues': [' '.join(re.sub(r'\(.*?\)', '', s.split(':')[-1]).lower().split()[:2]) for s in a['treat']] + ['escalate', 'call my senior', 'rapid response'],
                    'feedback_if_missed': tmpl['V3']['feedback_if_missed'].format(abnormality=k, treat='; '.join(a['treat']))})
    return out


TEMPERAMENT_LABEL = {1: 'friendly', 2: 'reserved', 3: 'skeptical', 4: 'irritable', 5: 'hostile'}
OPENNESS_LABEL = {1: 'open', 2: 'answers when asked', 3: 'brief', 4: 'guarded', 5: 'closed-off'}
EMPATHY_IDS = ('U-RAPP-1', 'U-CUE-1', 'U-CUE-2')


def difficulty_adjustments(profile):
    """How the temperament and openness sliders change grading. None for cases without sliders."""
    d = profile.get('difficulty')
    if not isinstance(d, dict):
        return None
    t = d.get('temperament') if d.get('temperament') in range(1, 6) else 2
    o = d.get('openness') if d.get('openness') in range(1, 6) else 2
    level = max(t, o)
    expected_turns = 6 + 2 * (o - 1) + (t - 1)
    shift = min(0.10, 0.05 * max(0, level - 3))
    changes = [f'Expect at least {expected_turns} student questions: a {OPENNESS_LABEL[o]}, {TEMPERAMENT_LABEL[t]} patient needs a longer interview.']
    if level >= 3:
        changes.append('Added a criterion for staying patient and non-confrontational.')
    if level >= 4:
        changes.append('Empathy and responding to cues are weighted as critical.')
    if shift:
        changes.append(f'Score cut-offs lowered by {round(shift * 100)} percentage points because this patient is harder to interview.')
    return {'temperament': t, 'openness': o, 'level': level, 'expected_turns': expected_turns, 'threshold_shift': shift,
            'empathy_critical': level >= 4, 'changes': changes}


def difficulty_criteria(adj):
    out = [{'id': 'D-LENGTH', 'domain': 3, 'tier': 'important', 'rule': 'min_turns', 'min': adj['expected_turns'],
            'criterion': f"Sustains the interview: at least {adj['expected_turns']} questions for this patient",
            'feedback_if_missed': 'This patient shares slowly. Keep going with open questions and follow-ups instead of ending early.'}]
    if adj['level'] >= 3:
        out.append({'id': 'D-PERSIST', 'domain': 2, 'tier': 'critical' if adj['level'] == 5 else 'important',
                    'criterion': 'Stays patient and non-confrontational with a guarded or difficult patient',
                    'cues': ['take your time', 'no rush', "you don't have to", "whenever you're ready", 'i hear you', "that's fair",
                             "it's okay", 'i understand', 'only if you are comfortable', "i'm here to help"],
                    'negative_cues': ['calm down', 'just answer', "that's not true", 'stop being', 'you need to cooperate'],
                    'feedback_if_missed': 'With a guarded or irritated patient, slow down, acknowledge the frustration, and give them control before pressing on.'})
    return out


def evaluate(c, student, disclosed_by_turn, results_so_far):
    ev = []
    for fid in c.get('seed_fact_ids', []):
        ev += [{'turn_id': t, 'quote': f'(disclosed fact {fid})'} for t in disclosed_by_turn.get(fid, [])]
    rule = c.get('rule')
    if rule == 'min_turns':
        return len(student) >= c['min'], [{'turn_id': student[-1]['id'], 'quote': f'{len(student)} student questions'}] if student else []
    if rule == 'co_occur':
        ev += [{'turn_id': m['id'], 'quote': m['text']} for m in student
               if any(has(m['text'], a) for a in c['cues']) and any(has(m['text'], b) for b in c['cues2'])]
    elif rule == 'min_hits':
        hits = [x for x in c['cues'] if find(student, [x])]
        if len(hits) >= c['min']:
            ev += find(student, hits)
    elif rule == 'order_check':
        firsts = []
        for phase in c['phases']:
            ids = [int(e['turn_id'][1:]) for cid in phase for e in results_so_far.get(cid, {}).get('evidence', [])
                   if e['turn_id'].startswith('t')]
            firsts.append(min(ids) if ids else None)
        seen = [f for f in firsts if f is not None]
        ok = len(seen) >= 3 and seen == sorted(seen)
        return ok, [{'turn_id': f't{f}', 'quote': f'phase {i + 1} first seen'} for i, f in enumerate(firsts) if f is not None]
    elif rule == 'before_treatment':
        tx = find(student, c['treatment_cues'])
        if not tx:
            return None, []  # not applicable: no treatment suggested
        first_tx = min(int(e['turn_id'][1:]) for e in tx)
        prior = [e for r in c['requires'] for e in results_so_far.get(r, {}).get('evidence', [])
                 if int(e['turn_id'][1:]) < first_tx]
        return len({r for r in c['requires'] if any(int(e['turn_id'][1:]) < first_tx for e in results_so_far.get(r, {}).get('evidence', []))}) == len(c['requires']), prior + tx[:1]
    else:
        ev += find(student, c.get('cues', []))
    neg = find(student, c.get('negative_cues', []))
    if neg:
        return False, [{**n, 'quote': 'NEGATIVE: ' + n['quote']} for n in neg]
    if not c.get('cues') and not c.get('seed_fact_ids') and c.get('negative_cues'):
        return True, [{'turn_id': '-', 'quote': 'no stigmatising/unsafe phrasing detected'}]
    seen, uniq = set(), []
    for e in ev:
        if e['turn_id'] not in seen:
            seen.add(e['turn_id']); uniq.append(e)
    return bool(uniq), uniq[:4]


def score(crit, enc):
    profile = enc.get('profile') or {}
    pid = enc.get('patient_id') or profile.get('id') or enc.get('patient', {}).get('id')
    case = crit['patients'].get(pid, {})
    case_criteria = case.get('criteria')
    if case_criteria is None:
        # Faculty-created patient: its learning checkpoints become case criteria.
        case_criteria = [{'id': 'CASE-' + o['id'], 'layer': 'elicit', 'domain': 3, 'tier': 'important',
                          'criterion': o.get('label') or o['id'], 'seed_fact_ids': o.get('fact_ids', []),
                          'feedback_if_missed': o.get('suggestion', '')}
                         for o in profile.get('objectives', []) if o.get('fact_ids')]
        # Case-specific criteria written by faculty or the generator (validated on save).
        case_criteria += [c for c in profile.get('scoring_criteria', [])
                          if isinstance(c, dict) and c.get('domain') in DOMAIN_KEYS and c.get('tier') in TIER_WEIGHT
                          and c.get('criterion') and (c.get('cues') or c.get('negative_cues'))]
    msgs = enc['messages']
    student = [m for m in msgs if m['role'] == 'student']
    disclosed = {}
    for m in msgs:
        if m['role'] == 'patient' and m.get('reply_to'):
            for fid in m.get('fact_ids', []):
                disclosed.setdefault(fid, []).append(m['reply_to'])

    vitals = enc.get('vitals') or profile.get('vitals') or case.get('vitals') or {}
    vkeys = abnormalities_from_vitals(vitals) if vitals else []
    adj = difficulty_adjustments(profile)
    universal = crit['universal_criteria']
    if adj and adj['empathy_critical']:
        universal = [{**c, 'tier': 'critical'} if c['id'] in EMPATHY_IDS else c for c in universal]
    criteria = universal + case_criteria + vital_criteria(crit, vkeys) + (difficulty_criteria(adj) if adj else [])
    order = sorted(criteria, key=lambda c: c.get('rule') in ('order_check', 'before_treatment'))

    results = {}
    for c in order:
        met, ev = evaluate(c, student, disclosed, results)
        results[c['id']] = {'id': c['id'], 'criterion': c['criterion'], 'domain': c['domain'], 'tier': c['tier'],
                            'met': met, 'evidence': ev,
                            'feedback': None if met else c.get('feedback_if_missed', '')}

    unsafe = []
    for xid, cues in UNSAFE_CUES.items():
        for e in find(student, cues):
            unsafe.append({'id': xid, **e})
    news = None
    if vitals and all(k in vitals for k in ('rr', 'spo2', 'sbp', 'hr', 'temp_c')):
        total_news, parts = news2(vitals, crit['vital_sign_rules']['news2'])
        news = {'score': total_news, 'parts': parts}
        if total_news >= 5 or 3 in parts.values():
            esc = find(student, ['escalate', 'call my senior', 'rapid response', 'call the doctor', 'icu', 'higher level of care'])
            results['VB'] = {'id': 'VB', 'criterion': 'Escalates for NEWS2 >=5 or single parameter 3', 'domain': 7,
                             'tier': 'critical', 'met': bool(esc), 'evidence': esc[:2],
                             'feedback': None if esc else f'NEWS2 is {total_news}: this patient needs escalation.'}
            if not esc:
                unsafe.append({'id': 'X-6', 'turn_id': '-', 'quote': f'NEWS2 {total_news} without escalation'})

    rubric_scores = crit['scoring_model']['coverage_to_rubric_score']
    if adj and adj['threshold_shift']:
        rubric_scores = [{**x, 'min_coverage': max(0.0, x['min_coverage'] - adj['threshold_shift'])} for x in rubric_scores]
    domains = []
    for did, key in DOMAIN_KEYS.items():
        rows = [r for r in results.values() if r['met'] is not None and r['domain'] == did]
        if not rows:
            domains.append({'id': did, 'key': key, 'score': 'N/A', 'coverage': None, 'met': [], 'missed': [], 'capped_by': []})
            continue
        w_all = sum(TIER_WEIGHT[r['tier']] for r in rows)
        w_met = sum(TIER_WEIGHT[r['tier']] for r in rows if r['met'])
        cov = w_met / w_all
        s = next(x['score'] for x in rubric_scores if cov >= x['min_coverage'])
        capped = [r['id'] for r in rows if r['tier'] == 'critical' and not r['met']]
        if capped:
            s = min(s, 2)
        domains.append({'id': did, 'key': key, 'score': s, 'coverage': round(cov, 2),
                        'met': [r['id'] for r in rows if r['met']], 'missed': [r['id'] for r in rows if not r['met']],
                        'capped_by': capped})
    if unsafe:
        for d in domains:
            if d['id'] == 7:
                d['score'] = 1; d['capped_by'].append('GATE-UNSAFE-ACTION')

    scored = [d for d in domains if isinstance(d['score'], int)]
    missed = sorted((r for r in results.values() if r['met'] is False), key=lambda r: -TIER_WEIGHT[r['tier']])
    hits = sorted((r for r in results.values() if r['met']), key=lambda r: -TIER_WEIGHT[r['tier']])
    return {
        'encounter_id': enc.get('id'), 'patient_id': pid, 'patient_name': case.get('name') or profile.get('name'),
        'criteria_version': crit['version'], 'status': 'auto_scored_pending_faculty_review',
        'domains': domains, 'criteria_results': list(results.values()),
        'vitals': {'abnormalities': vkeys, 'news2': news}, 'unsafe_actions': unsafe, 'difficulty': adj,
        'total': sum(d['score'] for d in scored), 'available_points': 4 * len(scored),
        'na_domains': sum(d['score'] == 'N/A' for d in domains),
        'review_required': bool(unsafe) or any(d['id'] in (6, 7) and d['score'] == 1 for d in scored),
        'strengths': [f"{r['criterion']} ({r['evidence'][0]['turn_id']})" for r in hits[:5] if r['evidence']],
        'gaps': [r['criterion'] for r in missed[:5]],
        'next_attempt_suggestions': [r['feedback'] for r in missed[:3]],
        'profile_gaps_to_acknowledge': case.get('profile_gaps_to_acknowledge', []),
    }


def auto_score(encounter):
    return score(load_criteria(), encounter)


if __name__ == '__main__':
    crit = json.load(open(sys.argv[1]))
    enc = json.load(open(sys.argv[2]))
    print(json.dumps(score(crit, enc), indent=2, ensure_ascii=False))
