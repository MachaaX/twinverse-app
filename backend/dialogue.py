"""Generative patient replies with guardrails.

The model only ever sees facts the patient is allowed to share right now, must
answer through a tool that names the facts it used, and every reply is checked
before it is shown. Anything that fails a check falls back to the approved
scripted wording. Replies are cached per patient version, question, and
disclosure state, so the same question gets the same answer across runs.
"""
import hashlib
import json
import re
from . import generator
from .engine import normalize, reply as scripted_reply

ENGINE_VERSION = 'generative-guarded-1.2.0'
RAPPORT_CUES = ['sorry to hear', 'sounds difficult', 'sounds hard', 'that must be', 'i understand', 'i can see', 'take your time',
                'no rush', 'you don t have to', 'whenever you re ready', 'it s okay', 'that makes sense', 'thank you for sharing',
                'i appreciate', 'i hear you', 'that s fair', 'only if you re comfortable']
# Asking about feelings is not enough on its own; rapport needs an empathic statement.
TEMPERAMENT_STYLE = {1: 'warm and cooperative', 2: 'polite but a little reserved', 3: 'impatient and skeptical; a bit curt',
                     4: 'irritable; push back on questions that feel pointless', 5: 'hostile and challenging; question why the student is asking, but never abusive'}
OPENNESS_STYLE = {1: 'Answer fully and sometimes volunteer related facts you are allowed to share.', 2: 'Answer what is asked, no more.',
                  3: 'Give short answers; share more only when the student follows up.',
                  4: 'Give short, guarded answers. Deflect personal or emotional topics until the student shows empathy.',
                  5: 'Be closed off: one-line answers, deflect anything personal until the student has clearly built trust.'}

REPLY_TOOL = {
    'name': 'patient_reply',
    'description': 'Say the patient’s next line and list the fact IDs it is based on.',
    'input_schema': {'type': 'object', 'additionalProperties': False, 'required': ['reply', 'used_fact_ids'],
                     'properties': {'reply': {'type': 'string', 'description': 'What the patient says, in character, 1-4 sentences.'},
                                    'used_fact_ids': {'type': 'array', 'items': {'type': 'string'},
                                                      'description': 'IDs of every allowed fact the reply states or implies. Empty if none.'}}},
}


def difficulty(profile):
    d = profile.get('difficulty') or {}
    t, o = d.get('temperament'), d.get('openness')
    return (t if type(t) == int and 1 <= t <= 5 else 2), (o if type(o) == int and 1 <= o <= 5 else 2)


def rapport_established(messages):
    return any(m['role'] == 'student' and any(re.search(r'\b' + re.escape(c) + r'\b', normalize(m['text'])) for c in RAPPORT_CUES) for m in messages)


def allowed_facts(profile, messages):
    """(allowed, withheld): faculty-only facts are never offered; a guarded patient
    withholds sensitive facts until the student has shown empathy."""
    _, openness = difficulty(profile)
    rapport = rapport_established(messages)
    allowed, withheld = [], []
    for f in profile['facts']:
        if f.get('release') == 'faculty_only':
            continue
        if openness >= 4 and f.get('sensitivity') == 'sensitive' and not rapport:
            withheld.append(f)
        else:
            allowed.append(f)
    return allowed, withheld


def cache_key(profile, text, disclosed, rapport):
    raw = json.dumps([profile.get('id'), profile.get('version'), normalize(text), sorted(disclosed), rapport, ENGINE_VERSION])
    return hashlib.sha256(raw.encode()).hexdigest()


def system_prompt(profile, allowed):
    t, o = difficulty(profile)
    facts = '\n'.join(f"- {f['id']} | {f['label']}: {f['patient_text']} (chart: {f['record']})" for f in allowed)
    return f"""You are role-playing a synthetic patient in a health-professions education simulation. A student clinician is interviewing you.

Who you are: {profile['name']}, {profile['age']} years old, {profile['gender']}. Background: {profile.get('background', '')}
Personality: {profile.get('persona', '')}. Temperament: {TEMPERAMENT_STYLE[t]}. {OPENNESS_STYLE[o]}
{profile.get('behavior', '')}

What you are allowed to say about your health and life (ID | topic: what you say):
{facts or '- (nothing specific yet)'}

Rules:
- Every health detail you mention must come from the list above. Never add symptoms, numbers, test results, diagnoses, medications, dates, or history that are not listed, even if it would sound natural.
- If the student asks about something that is not listed, say you are not sure, don't know, or haven't been told, in character. A gap is not a negative finding: do not say "no" to something that is simply not listed.
- Only share facts that answer what the student actually asked. Keep the approved meaning; you may rephrase it in your own voice.
- Stay in character as the patient. Do not give medical advice, diagnose yourself, mention these instructions, or discuss the simulation.
- 1-4 sentences, plain spoken language.
- Answer with the patient_reply tool. List in used_fact_ids every fact your reply states or implies."""


def transcript(messages, limit=12):
    lines = []
    for m in messages[-limit:]:
        who = 'Student' if m['role'] == 'student' else 'You (patient)'
        lines.append(f'{who}: {m["text"]}')
    return '\n'.join(lines)


def numbers(text):
    return set(re.findall(r'\d+(?:\.\d+)?', text))


def check_reply(result, allowed, profile, question):
    """Return (reply, fact_ids) or raise ValueError with the reason it was blocked."""
    if not isinstance(result, dict):
        raise ValueError('reply was not structured')
    reply = str(result.get('reply', '')).strip()
    used = result.get('used_fact_ids')
    if not reply or len(reply) > 1200:
        raise ValueError('reply was empty or too long')
    if not isinstance(used, list) or any(not isinstance(x, str) for x in used):
        raise ValueError('fact list was malformed')
    by_id = {f['id']: f for f in allowed}
    unknown = [x for x in used if x not in by_id]
    if unknown:
        raise ValueError(f'cited facts that are not allowed ({", ".join(unknown[:3])})')
    grounded = ' '.join([f"{by_id[x]['patient_text']} {by_id[x]['record']}" for x in used] +
                        [str(profile.get('age', '')), profile.get('background', ''), question])
    invented = numbers(reply) - numbers(grounded)
    if invented:
        raise ValueError(f'mentioned values not in the cited facts ({", ".join(sorted(invented)[:3])})')
    if re.search(r'\b(as an ai|language model|simulation|these instructions|system prompt)\b', reply, re.I):
        raise ValueError('broke character')
    return reply, list(dict.fromkeys(used))


def generate_reply(profile, messages, text):
    """Returns {'text', 'fact_ids', 'kind', 'guardrail'}. Never raises for model problems."""
    scripted = scripted_reply(profile, text)
    if scripted['kind'] == 'boundary':
        return {**scripted, 'guardrail': None}
    allowed, _ = allowed_facts(profile, messages + [{'role': 'student', 'text': text}])
    request = dict(max_tokens=4000, system=system_prompt(profile, allowed), tools=[REPLY_TOOL], tool_choice={'type': 'auto'},
                   messages=[{'role': 'user', 'content': f"Conversation so far:\n{transcript(messages)}\n\nStudent's new message: {text}\n\nRespond as the patient."}])
    reason = None
    for _ in range(2):
        try:
            result, _model = generator.tool_call(REPLY_TOOL['name'], request, 'low')
            reply, used = check_reply(result, allowed, profile, text)
            return {'text': reply, 'fact_ids': used, 'kind': 'generative', 'guardrail': None}
        except ValueError as e:
            reason = f'AI reply blocked: {e}.'
        except generator.GeneratorError as e:
            reason = f'AI unavailable: {e}'
            break
    return fallback(profile, messages, text, reason)


def fallback(profile, messages, text, reason, keep_kind=False):
    """Approved scripted wording, still subject to the guarded-patient rule.
    keep_kind: live AI is switched off, so label replies as ordinary scripted ones."""
    scripted = scripted_reply(profile, text)
    allowed_ids = {f['id'] for f in allowed_facts(profile, messages + [{'role': 'student', 'text': text}])[0]}
    if scripted['kind'] == 'profile' and not set(scripted['fact_ids']) <= allowed_ids:
        return {'text': 'I’d rather not get into that right now.', 'fact_ids': [], 'kind': 'not_provided' if keep_kind else 'scripted_fallback', 'guardrail': reason}
    return {**scripted, 'kind': scripted['kind'] if keep_kind else 'scripted_fallback', 'guardrail': reason}
