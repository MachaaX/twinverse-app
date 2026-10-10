"""Plain-language patient generator: one text block (+ optional files) -> draft case.

Input: free text, optional files (PDF, image, text), and two sliders
(temperament 1 friendly .. 5 hostile, openness 1 open .. 5 closed off).
Output, always a DRAFT for faculty review: patient profile, case rubric criteria
with named sources, clinical reports (labs, imaging, prior notes), and a portrait.

Live generation needs the optional `openai` package and a Bedrock API key in
AWS_BEARER_TOKEN_BEDROCK. The static example in data/generated_examples/ never
calls the network.
"""
import base64
import copy
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from . import bedrock_gpt

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / 'data/generated_examples'
REGION = os.environ.get('TWINVERSE_BEDROCK_REGION', 'us-west-2')
MODEL = os.environ.get('TWINVERSE_BEDROCK_MODEL', 'us.openai.gpt-6-sol')
# Try the US and global profiles of GPT-6 Sol through Bedrock Runtime.
# Explicit Claude overrides retain the Messages adapter and compatible 4.6
# fallbacks. All transports enforce temperature zero with reasoning off.
_FALLBACKS = [m.strip() for m in os.environ.get('TWINVERSE_BEDROCK_FALLBACK_MODELS',
              'global.openai.gpt-6-sol' if bedrock_gpt.is_gpt(MODEL) else
              'global.anthropic.claude-sonnet-4-6,us.anthropic.claude-opus-4-6-v1,global.anthropic.claude-opus-4-6-v1').split(',') if m.strip()]
_RUNTIME_EXTRA = [] if bedrock_gpt.is_gpt(MODEL) else [
    'us.anthropic.claude-sonnet-4-6', 'global.anthropic.claude-sonnet-4-6',
    'us.anthropic.claude-opus-4-6-v1', 'global.anthropic.claude-opus-4-6-v1']
_REGIONAL_PREFIXES = ('us.', 'global.', 'eu.', 'apac.')
CANDIDATES = list(dict.fromkeys(
    [('runtime' if m.startswith(_REGIONAL_PREFIXES) else 'mantle', m) for m in [MODEL] + _FALLBACKS]
    + [('runtime', m) for m in [MODEL] + _FALLBACKS if not m.startswith(_REGIONAL_PREFIXES)]
    + [('runtime', m) for m in _RUNTIME_EXTRA]))
_unavailable = set()
_active = None
_clients = {}
IMAGE_MODEL = os.environ.get('TWINVERSE_IMAGE_MODEL', 'stability.stable-image-core-v1:1')
TOPICS = ['concern', 'background', 'diet', 'labs', 'medication', 'social', 'bowel', 'perspective', 'vitals', 'history', 'symptoms', 'function']
VITAL_KEYS = {'hr': 'Heart rate', 'sbp': 'Systolic BP', 'dbp': 'Diastolic BP', 'rr': 'Respiratory rate', 'temp_c': 'Temperature (°C)', 'spo2': 'SpO2'}
FILE_TYPES = {'.pdf': 'application/pdf', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.txt': 'text/plain', '.md': 'text/plain'}
MAX_FILES, MAX_FILE_BYTES = 4, 5 * 1024 * 1024
PHI_PATTERNS = [(r'\b\d{3}-\d{2}-\d{4}\b', 'a Social Security number'), (r'\b[\w.+-]+@[\w-]+\.[\w.]+\b', 'an email address'),
                (r'\b\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b', 'a phone number'), (r'\bMRN\b|\bmedical record number\b', 'a medical record number')]
TEMPERAMENT = {1: 'Warm and cooperative', 2: 'Polite but reserved', 3: 'Impatient or skeptical', 4: 'Irritable, pushes back', 5: 'Hostile, challenges the student'}
OPENNESS = {1: 'Open, volunteers information', 2: 'Answers what is asked', 3: 'Brief answers, needs follow-up', 4: 'Guarded, shares sensitive topics only after rapport', 5: 'Closed off, deflects until trust is built'}
# Rubric criteria may only cite these. Prevents invented references.
REFERENCES = ['Faculty brief', 'Organizer Patient Encounter Performance Rubric', 'SEGUE Framework (Makoul 2001)',
              'Kalamazoo Essential Elements (Acad Med 2001)', 'Calgary-Cambridge Guide', 'Master Interview Rating Scale (MIRS)',
              'AAMC Core EPA 1', 'Teach-back method (AHRQ Health Literacy Toolkit)', 'Motivational interviewing (Miller & Rollnick)',
              'Trauma-informed care (SAMHSA)', 'AHA/ACC 2025 High Blood Pressure Guideline', '2018 ACC/AHA Cholesterol Guideline',
              'ADA Standards of Care in Diabetes', 'NEWS2 (Royal College of Physicians 2017)', 'BTS 2017 Oxygen Guideline',
              'Surviving Sepsis Campaign 2021', 'AAP Clinical Practice Guidelines', 'GINA Asthma Strategy', 'USPSTF Recommendations',
              'CDC Clinical Guidance', 'NIAAA Drinking Guidelines', 'ASHA Practice Portal', 'General clinical communication practice']


class GeneratorError(Exception):
    """A message that is safe and useful to show faculty in the UI."""


class ModelUnavailable(GeneratorError):
    """This key cannot use this model in this region; another candidate may work."""


def active_model():
    return _active or next((c for c in CANDIDATES if c not in _unavailable), CANDIDATES[0])


def label(candidate):
    return f'{candidate[1]} via bedrock-{candidate[0]}'



def _slider(value):
    return value if type(value) == int and 1 <= value <= 5 else None


def check_request(req):
    """Requirements that must be met before anything is generated."""
    errors, warnings = [], []
    if not isinstance(req, dict):
        return {'errors': ['Send the request as an object.'], 'warnings': []}
    text = str(req.get('text', '')).strip()
    if len(text) < 80:
        errors.append('Describe the patient in at least a few sentences (80+ characters): age, sex, situation, key findings, and what the student should learn.')
    if len(text) > 12000:
        errors.append('Keep the description under 12,000 characters.')
    for key, label in [('temperament', 'Temperament'), ('openness', 'Openness')]:
        if _slider(req.get(key)) is None:
            errors.append(f'{label} must be a whole number from 1 to 5.')
    files = req.get('files') or []
    if not isinstance(files, list) or len(files) > MAX_FILES:
        errors.append(f'Attach at most {MAX_FILES} files.')
        files = []
    texts = [text]
    for f in files:
        name = Path(str((f or {}).get('name', ''))).name
        ext = Path(name).suffix.lower()
        if ext not in FILE_TYPES:
            errors.append(f'{name or "A file"}: upload PDF, PNG, JPG, TXT, or MD.')
            continue
        try:
            raw = base64.b64decode((f or {}).get('content', ''), validate=True)
        except (ValueError, TypeError):
            errors.append(f'{name}: the file could not be read.')
            continue
        if not raw or len(raw) > MAX_FILE_BYTES:
            errors.append(f'{name}: files must be between 1 byte and 5 MB.')
        elif FILE_TYPES[ext] == 'text/plain':
            texts.append(raw.decode('utf-8', 'replace'))
    joined = '\n'.join(texts)
    for pattern, label in PHI_PATTERNS:
        if re.search(pattern, joined, re.I):
            errors.append(f'The description or a text file appears to contain {label}. Use synthetic data only.')
    if any(Path(str((f or {}).get('name', ''))).suffix.lower() in ('.pdf', '.png', '.jpg', '.jpeg') for f in files):
        warnings.append('PDFs and images are read by the AI but not scanned here for real identifiers. Make sure they are synthetic.')
    return {'errors': errors, 'warnings': warnings}


CASE_TOOL = {
    'name': 'save_patient_case',
    'description': 'Save the complete synthetic virtual-patient case built from the faculty description.',
    'input_schema': {
        'type': 'object', 'additionalProperties': False,
        'required': ['missing_required', 'age', 'sex', 'concern', 'assessment_terms', 'key_findings', 'learning_objectives', 'name', 'summary', 'background', 'persona',
                     'behavior', 'vitals', 'facts', 'objectives', 'scoring_criteria', 'reports', 'image_prompt'],
        'properties': {
            'missing_required': {'type': 'array', 'items': {'type': 'string', 'enum': ['age', 'sex', 'main concern', 'learning objectives']},
                                 'description': 'Required items the description does not state. Do not guess them.'},
            'age': {'type': ['integer', 'null']},
            'sex': {'type': 'string'},
            'concern': {'type': 'string', 'description': 'Main concern or diagnosis as stated.'},
            'assessment_terms': {'type': 'array', 'items': {'type': 'string'},
                                 'description': '2-6 accepted names for the working diagnosis or assessment a student should reach, including lay synonyms (e.g. "type 2 diabetes", "diabetes", "high blood sugar").'},
            'key_findings': {'type': 'array', 'items': {'type': 'string'},
                             'description': '3-8 short lowercase phrases a student would mention when tying the picture together (e.g. "a1c", "sweet tea", "family history").'},
            'learning_objectives': {'type': 'array', 'items': {'type': 'string'}, 'description': 'From the description; if none are stated, list missing_required "learning objectives".'},
            'name': {'type': 'string', 'description': 'Fictional full name. Never a real or famous person.'},
            'summary': {'type': 'string', 'description': 'One-line card summary. Do not reveal hidden answers.'},
            'background': {'type': 'string'},
            'persona': {'type': 'string', 'description': 'Personality in 3-8 words.'},
            'behavior': {'type': 'string', 'description': '2-4 sentences: how the temperament and openness levels show in conversation.'},
            'vitals': {'type': 'object', 'additionalProperties': False, 'description': 'Only values stated in the description or files.',
                       'properties': {k: {'type': 'number'} for k in VITAL_KEYS}},
            'facts': {'type': 'array', 'minItems': 4, 'maxItems': 24, 'items': {
                'type': 'object', 'additionalProperties': False,
                'required': ['label', 'topic', 'record', 'patient_text', 'keywords', 'release', 'sensitivity', 'origin'],
                'properties': {
                    'label': {'type': 'string'},
                    'topic': {'type': 'string', 'enum': TOPICS},
                    'record': {'type': 'string', 'description': 'Chart wording, clinical and concise.'},
                    'patient_text': {'type': 'string', 'description': 'What the patient says when asked: first person, in persona, only this fact.'},
                    'keywords': {'type': 'array', 'items': {'type': 'string'}, 'description': '4-12 lowercase phrases a student might use to ask about this.'},
                    'release': {'type': 'string', 'enum': ['initial', 'question', 'faculty_only']},
                    'sensitivity': {'type': 'string', 'enum': ['routine', 'sensitive'], 'description': 'sensitive = emotional, stigmatized, or private topics a guarded patient would hold back.'},
                    'origin': {'type': 'string', 'enum': ['faculty_brief', 'ai_added']}}}},
            'objectives': {'type': 'array', 'minItems': 1, 'maxItems': 12, 'items': {
                'type': 'object', 'additionalProperties': False, 'required': ['label', 'fact_indexes', 'suggestion'],
                'properties': {'label': {'type': 'string'},
                               'fact_indexes': {'type': 'array', 'items': {'type': 'integer'}, 'description': '0-based indexes into facts; never faculty_only facts.'},
                               'suggestion': {'type': 'string'}}}},
            'scoring_criteria': {'type': 'array', 'minItems': 4, 'maxItems': 14, 'items': {
                'type': 'object', 'additionalProperties': False, 'required': ['criterion', 'domain', 'tier', 'cues', 'feedback_if_missed', 'source'],
                'properties': {'criterion': {'type': 'string'},
                               'domain': {'type': 'integer', 'minimum': 1, 'maximum': 7},
                               'tier': {'type': 'string', 'enum': ['critical', 'important', 'supplementary']},
                               'cues': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Short phrases a student says when meeting this criterion.'},
                               'feedback_if_missed': {'type': 'string'},
                               'source': {'type': 'string', 'enum': REFERENCES}}}},
            'reports': {'type': 'array', 'maxItems': 4, 'items': {
                'type': 'object', 'additionalProperties': False, 'required': ['kind', 'title', 'body', 'keywords', 'origin'],
                'properties': {'kind': {'type': 'string', 'enum': ['lab', 'imaging', 'prior_note', 'other']},
                               'title': {'type': 'string'},
                               'body': {'type': 'string', 'description': 'Plain-text report consistent with the facts. Mark it SYNTHETIC.'},
                               'keywords': {'type': 'array', 'items': {'type': 'string'}},
                               'origin': {'type': 'string', 'enum': ['faculty_brief', 'ai_added']}}}},
            'image_prompt': {'type': 'string', 'description': 'Neutral visual description for a synthetic portrait (age, apparent sex, clothing, setting). No names.'},
        },
    },
}

SYSTEM = """You build synthetic virtual-patient cases for a health-professions education simulator. Faculty describe a patient in plain language, sometimes with attached files; you turn that into a structured case.

Clinical grounding comes first. Every value faculty gave (age, vitals, labs, imaging, diagnoses, medications) appears exactly as given. You may add a few plausible supporting details that make the interview realistic, but mark each one origin "ai_added", and never add diagnoses, abnormal results, or medications the material does not imply. If age, sex, the main concern, or learning objectives are not stated, list them in missing_required instead of guessing. Unknown details stay unknown.

Facts are disclosable units. Release "initial" for what the chart shows at the start (presenting summary, stated vital signs), "question" for history the student must ask about, and "faculty_only" for teaching notes the patient never says. Give "question" facts 4-12 lowercase trigger phrases. Patient wording is first person, in the persona's voice, and states only that fact. Mark emotional, stigmatized, or private facts "sensitive".

The temperament and openness levels shape the persona and behavior, and the rubric: for a hostile or closed-off patient, include criteria for de-escalation, patience, and building trust before sensitive questions.

Scoring criteria describe observable student behavior for this case, mapped to rubric domains (1 opening and purpose, 2 rapport and empathy, 3 information gathering, 4 listening and cues, 5 explanation and shared decisions, 6 clinical reasoning, 7 professionalism, safety and closure). Cite the source each criterion is built on, choosing only from the allowed list.

Reports: include a short report for each kind of result the material mentions (labs, imaging such as an X-ray, prior notes), consistent with the facts. Do not create reports for tests that were not mentioned.

Names and details are fictional. Call save_patient_case exactly once with the complete case."""


def request_content(req):
    """User message: the description, slider levels, then any attached files."""
    t, o = req['temperament'], req['openness']
    intro = (f"Temperament level {t}/5: {TEMPERAMENT[t]}.\nOpenness level {o}/5: {OPENNESS[o]}.\n\n"
             f"Faculty description:\n{str(req['text']).strip()}")
    blocks = [{'type': 'text', 'text': intro}]
    for f in req.get('files') or []:
        name = Path(f['name']).name
        mime = FILE_TYPES[Path(name).suffix.lower()]
        if mime == 'text/plain':
            blocks.append({'type': 'text', 'text': f'Attached file {name}:\n' + base64.b64decode(f['content']).decode('utf-8', 'replace')})
        elif mime == 'application/pdf':
            blocks.append({'type': 'document', 'source': {'type': 'base64', 'media_type': mime, 'data': f['content']}, 'title': name})
        else:
            blocks.append({'type': 'image', 'source': {'type': 'base64', 'media_type': mime, 'data': f['content']}})
            blocks.append({'type': 'text', 'text': f'(The image above is attached file {name}.)'})
    return blocks


def bedrock_key():
    return os.environ.get('AWS_BEARER_TOKEN_BEDROCK', '').strip()


def live_status():
    base = {'model': label(active_model()), 'image_model': IMAGE_MODEL, 'region': REGION,
            'temperature': 0, 'thinking': 'disabled', 'reasoning_effort': 'none'}
    package = 'openai' if bedrock_gpt.is_gpt(active_model()[1]) else 'anthropic'
    try:
        __import__(package)
    except ImportError:
        return {**base, 'live_available': False, 'reason': f'Live AI needs the {package} package: run  python3 -m pip install {package}  and restart the app.'}
    if not bedrock_key():
        return {**base, 'live_available': False, 'reason': 'No Bedrock API key. Start the app with AWS_BEARER_TOKEN_BEDROCK set (see README).'}
    return {**base, 'live_available': True, 'reason': 'Bedrock key found. Use “Test connection” to confirm it still works.'}


def client(transport='runtime', model=None):
    status = live_status()
    if not status['live_available']:
        raise GeneratorError(status['reason'])
    provider = 'openai' if bedrock_gpt.is_gpt(model or active_model()[1]) else 'anthropic'
    key = (provider, transport)
    if key not in _clients:
        if provider == 'openai':
            import openai
            host = f'bedrock-runtime.{REGION}.amazonaws.com' if transport == 'runtime' else f'bedrock-mantle.{REGION}.api.aws'
            _clients[key] = openai.OpenAI(base_url=f'https://{host}/openai/v1', api_key=bedrock_key(),
                                        timeout=240.0, max_retries=1)
            return _clients[key]
        import anthropic
        # Bedrock API keys are bearer tokens. mantle: the standard client pointed at the
        # Bedrock Messages endpoint; runtime: the SDK's Bedrock (InvokeModel) client.
        if transport == 'mantle':
            _clients[key] = anthropic.Anthropic(base_url=f'https://bedrock-mantle.{REGION}.api.aws/anthropic', api_key=bedrock_key(), timeout=240.0, max_retries=1)
        else:
            _clients[key] = anthropic.AnthropicBedrock(api_key=bedrock_key(), aws_region=REGION, timeout=240.0, max_retries=1)
    return _clients[key]


def call(api, model, **kwargs):
    if bedrock_gpt.is_gpt(model):
        return bedrock_gpt.call(api, model, **kwargs)
    import anthropic
    # SDK 1.13 removed the temperature keyword. extra_body sends it in the
    # actual Bedrock JSON body for both SDK transports, including all retries
    # and connection probes. Do not silently retry with default sampling.
    kwargs['extra_body'] = {**(kwargs.get('extra_body') or {}),
                            'temperature': 0, 'thinking': {'type': 'disabled'}}
    try:
        return api.messages.create(model=model, **kwargs)
    except anthropic.AuthenticationError as e:
        raise ModelUnavailable(f'401 key rejected ({_detail(e)})')
    except (anthropic.PermissionDeniedError, anthropic.NotFoundError) as e:
        raise ModelUnavailable(f'{e.status_code} {_detail(e)}')
    except anthropic.RateLimitError:
        raise GeneratorError('Bedrock is rate limiting requests. Wait a minute and try again.')
    except anthropic.APIStatusError as e:
        if e.status_code == 400:
            raise ModelUnavailable(f'400 {_detail(e)}')
        raise GeneratorError(f'Bedrock returned an error ({e.status_code}): {_detail(e)}')
    except anthropic.APIConnectionError:
        raise GeneratorError('Could not reach Bedrock. Check the internet connection, or use the static example.')


def _detail(e):
    detail = str(getattr(e, 'message', '') or e)
    if bedrock_key():
        detail = detail.replace(bedrock_key(), '[REDACTED]')
    return re.sub(r'\s+', ' ', detail)[:160]


def _no_model_error(errors):
    if errors and all(' 401 ' in f' {err} ' for _, err in errors):
        return GeneratorError('Bedrock rejected the API key. It may have expired (short-term keys last 12 hours): generate a new key, then restart the app with it.')
    if errors and all('private marketplace' in err.lower() for _, err in errors):
        return GeneratorError('AWS Private Marketplace is blocking activation of the configured model. '
                              'Ask your workshop organizer or AWS account administrator to enable its model subscription '
                              'and Private Marketplace eligibility, then retry Test connection after five minutes.')
    shown = '; '.join(f'{label(c)}: {err}' for c, err in errors[:3])
    return GeneratorError(f'No configured text model is available to this key in {REGION}. First errors: {shown}. '
                          'Check Bedrock Model access and ask the organizers whether the event key allows the configured model and inference profile.')


def call_any(request, effort, skip=()):
    """Send the request to the first (endpoint, model) this key can use."""
    global _active
    errors = []
    for candidate in dict.fromkeys([active_model()] + CANDIDATES):
        if candidate in _unavailable or candidate in skip:
            continue
        try:
            message = call(client(candidate[0], candidate[1]), candidate[1], output_config={'effort': effort}, **request)
        except ModelUnavailable as e:
            if candidate == _active:
                raise GeneratorError(f'{label(candidate)} stopped working: {e}')
            _unavailable.add(candidate);errors.append((candidate, str(e)))
            continue
        _active = candidate
        return message, candidate
    raise _no_model_error(errors)


def tool_call(tool, request, effort):
    """One tool-shaped answer. After a refusal, retries once on the next available model."""
    message, used = call_any(request, effort)
    if message.stop_reason == 'refusal':
        # Bedrock has no server-side fallback, so retry once on another model.
        message, used = call_any(request, effort, skip={used})
    if message.stop_reason == 'refusal':
        raise GeneratorError('The model declined this request. Rephrase it and try again.')
    if message.stop_reason == 'max_tokens':
        raise GeneratorError('The response was too long. Shorten the input and try again.')
    calls = [b for b in message.content if b.type == 'tool_use' and b.name == tool]
    if len(calls) != 1:
        raise GeneratorError('The model did not return the expected result. Try again.')
    return calls[0].input, label(used)


def test_connection():
    """Try candidates in order, stopping at the first that works; report every attempt."""
    global _active
    _unavailable.clear();_active = None
    results, errors = [], []
    for candidate in CANDIDATES:
        try:
            call(client(candidate[0], candidate[1]), candidate[1], max_tokens=256, output_config={'effort': 'low'},
                 messages=[{'role': 'user', 'content': 'Reply with the single word: ready'}])
        except ModelUnavailable as e:
            _unavailable.add(candidate);errors.append((candidate, str(e)))
            results.append({'model': label(candidate), 'ok': False, 'error': str(e)})
            continue
        _active = candidate
        results.append({'model': label(candidate), 'ok': True})
        return {'ok': True, 'model': label(candidate), 'region': REGION, 'results': results}
    raise _no_model_error(errors)


def generate_case(req):
    """Call the configured text model on Bedrock and return (raw case dict, model id)."""
    request = dict(max_tokens=20000, system=SYSTEM, tools=[CASE_TOOL], tool_choice={'type': 'auto'},
                   messages=[{'role': 'user', 'content': request_content(req)}])
    return tool_call(CASE_TOOL['name'], request, 'medium')


def generate_portrait(image_prompt, age, sex, seed=7):
    """Stability Stable Image Core on Bedrock. Returns (jpeg bytes, None) or (None, reason)."""
    if not bedrock_key():
        return None, 'No Bedrock API key, so no portrait was generated.'
    prompt = (f'Head-and-shoulders portrait illustration of a fictional {age}-year-old {sex} patient. {image_prompt}. '
              'Soft neutral background, gentle lighting, respectful clinical-simulation style, no text, no logos.')[:9000]
    url = f'https://bedrock-runtime.{REGION}.amazonaws.com/model/{urllib.parse.quote(IMAGE_MODEL, safe="")}/invoke'
    for body in ({'prompt': prompt, 'aspect_ratio': '1:1', 'output_format': 'jpeg', 'seed': seed}, {'prompt': prompt}):
        request = urllib.request.Request(url, data=json.dumps(body).encode(), method='POST',
                                         headers={'Authorization': f'Bearer {bedrock_key()}', 'Content-Type': 'application/json', 'Accept': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = json.loads(response.read())
        except urllib.error.HTTPError as e:
            if e.code == 400 and 'aspect_ratio' in body:
                continue  # retry with the minimal body
            if e.code in (401, 403):
                return None, f'Portrait not generated: the key cannot use {IMAGE_MODEL} (expired key, or enable the model in Bedrock Model access).'
            return None, f'Portrait not generated: the image model returned an error ({e.code}).'
        except (urllib.error.URLError, TimeoutError, ValueError):
            return None, 'Portrait not generated: could not reach the image model.'
        reasons = [r for r in data.get('finish_reasons') or [] if r]
        if reasons or not data.get('images'):
            return None, 'Portrait not generated: the image model filtered the request. Edit the image description and try again.'
        return base64.b64decode(data['images'][0]), None
    return None, 'Portrait not generated: the image model rejected the request.'


def _phrases(values, limit=12):
    out = []
    for v in values if isinstance(values, list) else []:
        v = re.sub(r'\s+', ' ', str(v)).strip().lower()[:100]
        if v and v not in out:
            out.append(v)
    return out[:limit]


def normalize(raw, req, provenance):
    """Turn the model's case into the app's profile format, with review notes.
    Returns (profile, reports). Raises GeneratorError if required info is missing."""
    if not isinstance(raw, dict):
        raise GeneratorError('The generated case was not in the expected format. Try again.')
    missing = [m for m in raw.get('missing_required') or [] if isinstance(m, str)]
    age = raw.get('age')
    if type(age) != int or not 0 <= age <= 110:
        missing.append('age')
    if not str(raw.get('sex', '')).strip():
        missing.append('sex')
    objectives_text = [x for x in raw.get('learning_objectives') or [] if isinstance(x, str) and x.strip()]
    if not objectives_text:
        missing.append('learning objectives')
    if missing:
        raise GeneratorError('Add these to the description, then generate again: ' + ', '.join(dict.fromkeys(missing)) + '.')
    notes = ['AI-generated draft: check every fact, the patient wording, the reports, and the scoring criteria before publishing.']
    facts = []
    for i, f in enumerate(raw.get('facts') or []):
        if not isinstance(f, dict):
            continue
        release = f.get('release') if f.get('release') in ('initial', 'question', 'faculty_only') else 'question'
        fact = {'id': f'f{len(facts) + 1}', 'label': str(f.get('label', '')).strip() or f'Fact {i + 1}',
                'topic': f.get('topic') if f.get('topic') in TOPICS else 'history',
                'record': str(f.get('record', '')).strip(), 'patient_text': str(f.get('patient_text', '')).strip(),
                'keywords': _phrases(f.get('keywords')), 'release': release,
                'sensitivity': 'sensitive' if f.get('sensitivity') == 'sensitive' else 'routine',
                'source': f"{provenance} · {'from faculty brief' if f.get('origin') == 'faculty_brief' else 'AI-added detail'}"}
        if fact['release'] == 'faculty_only' and not fact['patient_text']:
            fact['patient_text'] = '(Faculty-only note. Never spoken in the encounter.)'
        if fact['release'] == 'question' and not fact['keywords']:
            fact['keywords'] = _phrases([fact['label']])
        if f.get('origin') != 'faculty_brief':
            notes.append(f"AI-added detail to verify: {fact['label']}.")
        facts.append((i, fact))
    index_to_id = {i: fact['id'] for i, fact in facts}
    hidden = {fact['id'] for _, fact in facts if fact['release'] == 'faculty_only'}
    objectives = []
    for o in raw.get('objectives') or []:
        if not isinstance(o, dict):
            continue
        refs = [index_to_id[x] for x in o.get('fact_indexes', []) if isinstance(x, int) and x in index_to_id and index_to_id[x] not in hidden]
        objectives.append({'id': f'o{len(objectives) + 1}', 'label': str(o.get('label', '')).strip() or 'Learning objective',
                           'fact_ids': list(dict.fromkeys(refs)), 'suggestion': str(o.get('suggestion', '')).strip()})
        if not refs:
            notes.append(f"Learning checkpoint “{objectives[-1]['label']}” is not linked to a fact; link it in the editor.")
    criteria = []
    for c in raw.get('scoring_criteria') or []:
        if not isinstance(c, dict) or type(c.get('domain')) != int or not 1 <= c['domain'] <= 7:
            continue
        criteria.append({'id': f'GEN-{len(criteria) + 1}', 'layer': 'case', 'domain': c['domain'],
                         'tier': c.get('tier') if c.get('tier') in ('critical', 'important', 'supplementary') else 'important',
                         'criterion': str(c.get('criterion', '')).strip(), 'cues': _phrases(c.get('cues')),
                         'feedback_if_missed': str(c.get('feedback_if_missed', '')).strip(),
                         'source': c.get('source') if c.get('source') in REFERENCES else 'General clinical communication practice'})
    vitals = {k: v for k, v in (raw.get('vitals') or {}).items() if k in VITAL_KEYS and isinstance(v, (int, float))}
    reports = []
    for r in raw.get('reports') or []:
        if isinstance(r, dict) and str(r.get('body', '')).strip():
            reports.append({'kind': r.get('kind') if r.get('kind') in ('lab', 'imaging', 'prior_note', 'other') else 'other',
                            'title': str(r.get('title', '')).strip() or 'Clinical report', 'body': str(r['body']).strip(),
                            'keywords': _phrases(r.get('keywords')) or ['records', 'report', 'results']})
            if r.get('origin') != 'faculty_brief':
                notes.append(f"AI-written report to verify: {reports[-1]['title']}.")
    temperament, openness = req['temperament'], req['openness']
    profile = {'name': str(raw.get('name', '')).strip(), 'age': age, 'gender': str(raw['sex']).strip(),
               'summary': str(raw.get('summary', '')).strip() or str(raw.get('concern', '')).strip(),
               'background': str(raw.get('background', '')).strip(), 'persona': str(raw.get('persona', '')).strip() or TEMPERAMENT[temperament],
               'behavior': str(raw.get('behavior', '')).strip(),
               'source_notes': 'Faculty description:\n' + str(req['text']).strip() + ('\n\nAttached files: ' + ', '.join(Path(f['name']).name for f in req.get('files') or []) if req.get('files') else ''),
               'facts': [f for _, f in facts], 'objectives': objectives, 'scoring_criteria': criteria, 'vitals': vitals,
               'difficulty': {'temperament': temperament, 'openness': openness}, 'dialogue_mode': 'generative',
               'learning_objectives': objectives_text, 'assessment_terms': _phrases(raw.get('assessment_terms'), 8),
               'key_findings': _phrases(raw.get('key_findings'), 10), 'image_prompt': str(raw.get('image_prompt', '')).strip(), 'version': 0, 'status': 'draft'}
    notes += consistency_notes(profile, reports, req)
    profile['validation_notes'] = list(dict.fromkeys(notes))
    return profile, reports


def consistency_notes(profile, reports, req):
    """Flag places where the generated case may not match the faculty description."""
    notes = []
    case_text = ' '.join([f"{f['record']} {f['patient_text']}" for f in profile['facts']] + [r['body'] for r in reports] + [profile['background'], profile['summary']])
    compact = case_text.replace(' ', '')
    for value in dict.fromkeys(re.findall(r'\d+(?:\.\d+)?(?:/\d+)?', str(req.get('text', '')))):
        if value == str(profile['age']) or (len(value) < 2 and '.' not in value):
            continue
        if value not in compact:
            notes.append(f'The value {value} from the description does not appear in the generated facts or reports.')
    if not any(f['release'] == 'question' for f in profile['facts']):
        notes.append('No facts are released by questioning, so the interview will have nothing to discover.')
    if len(profile['scoring_criteria']) < 3:
        notes.append('Fewer than three case scoring criteria were generated; add more or rely on the universal criteria.')
    if profile['difficulty']['openness'] >= 4 and not any(f['sensitivity'] == 'sensitive' and f['release'] == 'question' for f in profile['facts']):
        notes.append('The patient is set as guarded, but no facts are marked sensitive, so nothing is held back until rapport.')
    return notes


def load_example(name='pediatric-hearing'):
    path = EXAMPLES / f'{name}.json'
    if not path.is_file():
        raise GeneratorError('The static example file is missing.')
    data = json.loads(path.read_text())
    return copy.deepcopy(data['request']), copy.deepcopy(data['case'])
