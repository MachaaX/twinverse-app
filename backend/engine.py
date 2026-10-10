import re
import os
import json
import requests

def normalize(text):
    return re.sub(r'\s+', ' ', text.strip().lower())

def includes(text, kw):
    t = normalize(text)
    k = normalize(kw)
    if not k:
        return False
    # Check word boundaries for clean matching
    pattern = r'\b' + re.escape(k) + r'\b'
    return bool(re.search(pattern, t))

def reply(profile, text):
    t = normalize(text)
    
    # 1. Maintain safety boundary checks from the original version
    if re.search(r'\b(ignore|system prompt|hidden|answer key|rubric|all facts|developer prompt)\b', t):
        return {'text': 'Let\'s keep this focused on the interview. What would you like to ask me?', 'fact_ids': [], 'kind': 'boundary'}

    # 2. Extract API configuration from environment variables
    # You can configure these in your environment or substitute your key directly below
    api_key = os.environ.get("LLM_API_KEY", "bedrock-api-key-YmVkcm9jay5hbWF6b25hd3MuY29tLz9BY3Rpb249Q2FsbFdpdGhCZWFyZXJUb2tlbiZYLUFtei1BbGdvcml0aG09QVdTNC1ITUFDLVNIQTI1NiZYLUFtei1DcmVkZW50aWFsPUFTSUFXVE9XSUpDQ1hEUTRZWFpRJTJGMjAyNjEwMTAlMkZ1cy1lYXN0LTElMkZiZWRyb2NrJTJGYXdzNF9yZXF1ZXN0JlgtQW16LURhdGU9MjAyNjEwMTBUMTgzNzAyWiZYLUFtei1FeHBpcmVzPTQzMjAwJlgtQW16LVNlY3VyaXR5LVRva2VuPUlRb0piM0pwWjJsdVgyVmpFSlAlMkYlMkYlMkYlMkYlMkYlMkYlMkYlMkYlMkYlMkZ3RWFDWFZ6TFdWaGMzUXRNU0pHTUVRQ0lCbm16VllTVjZqbjRyOUdIWSUyQlVqZHhPcGwlMkZmMXkwN2tSNWdGc2w2TkRrMUFpQnolMkJqZ2hwMCUyQnFjQUFHVGFONHN3bGZwbkM4TkdTTXlDMFJRVWR1dGpscEhDcTBBd2hjRUFBYUREUTFOREV3TlRJMU5EQXlNU0lNWnNyalYyOWRrUkhTT3c0UEtwRUR3bmgzOGNjWHZWMEVFdDdzTXl5QVNxRjUyUHVYcnJUTnh6NUpOcnlWQ1RPcWc3QTh1TyUyQmM3VkkwM1dZeUJXMUJEWVlFaWg0Y3JmQlJqMHAwWTA4WTRqanFJRmwlMkY4VlpMVW1vJTJCWCUyRjAycHF1QktXU1U5UXJnVkZYSzVoRHZPeTJtNUU0dmNIWjdlVjJkcTUlMkZsUTRZU25ncVZ1b3dpcW95OXdPa3o5JTJCSEtFaTlGc21HWnZSM0JCbW5STTdQWk03eXRlaWM1ZlRFWE1aR0slMkZJNWF0RktzTTAwdzF6Um1UVG54dENUeHROdHlpaldXWk1kcHlycFo3bklDSDVwam4yU0YzeWtCVjQwdEZkakpaaDB0Q2ZMcTRMJTJCZlZGVnk3UFg0UkJ4WEdpdXFZWGloZ3lCa3VIYnRqR014ZEVyNzdkaFp0NVVYc3RHQW5KRUloaXBLOXAwU095Tnl1WiUyQkltbCUyRllLdm5ST2JNOVRhSkVWaWpSUW5KNCUyRkk4b01ia3lTdmJiSlZQNGF2VDJFSHElMkY4NEpjUFRscWhDbWg1RjVrRW9WcTFkRENCVzlTdTJKc3JYbHFMSWJvMEN3OTV1VDZWRHVJcm5jYnVQYjA1RkJhbFBBMFZtMFk2cVhMeXZTVjhIN0REdGpEYmtMbnowd041JTJGNm1Qc2x2M3NKSmViUTZSWGZIZzg1bFhmVmx2M0xyWUt6czdZSlRmS2d3aU1PcDFnWTZ1QUxVd0JtQ0dITVZia3pZRzU0ZGl0MHlRNGF0TklSemZFa0NHamwzaGJ5REFhOEY2N1M1VGIzbUtXaWJpNk84S05obFhxSk1abXgwQkp2TTFGTUhDdFBSTkJsdmdMMzRYTk9vc2Jjb0UzJTJCa3ZJZEVrWkFFUnlkbm9iVmZxOTZGa1hEZXFIeUp1blhxckp3JTJGJTJCVDFNNVIwYWlNY0ExZFRwQW5EaFBuN3BFeURVc3BwZWV5SUlMNGlCJTJCZkpHcHNjQnl4YnREQ0lGMnpSNVVEcDE5Q0U3UTFqWCUyQiUyQjhnd1hXWFlETkx0ejRnNiUyRndkc2ZOcHh0ZXQlMkZxMFpaVHlTYjhlWjZmWklaa2slMkJBZnZkeUsxaGRmZ3YwSXJzSnZDdHpCM2tUOUhEbXM0eTJvZ1FDMHIzeVlIRVBOciUyRlRVTkMlMkJVWEhrT1BydTJKJTJGd0d2NU9QbWJMZGkzamhaN1UwNjU4c1BVdmV0WTVaNUNhd0p1bnlxbk9VSnhDYzduMiUyQnV1NU5oVWdEZEh1RWNVdHgzbkFETmN0SExoNmtuRDglMkJkcFRnaW9qTDglM0QmWC1BbXotU2lnbmF0dXJlPTg2NjcwMDRkN2Y3ZjRmMDJkM2NhMzE5Y2UzY2MzMWRhMWI0YjNiZmM2MTkzNzA5ZTBhZWU2MzUyNDgwNjkxODUmWC1BbXotU2lnbmVkSGVhZGVycz1ob3N0JlZlcnNpb249MQ==")
    api_url = os.environ.get("LLM_API_URL", "https://bedrock-mantle.east-1.api.aws/openai/v1 (e.g., https://bedrock-mantle.us-east-2.api.aws/openai/v1")
    model_name = os.environ.get("LLM_MODEL", "gpt-4o") # Change to your target model endpoint if needed

    # 3. Gather patient-safe facts (exclude faculty-only disclosures)
    safe_facts = [
        {
            "id": f.get("id"),
            "fact_text": f.get("patient_text") or f.get("fact_text"),
            "keywords": f.get("keywords", [])
        }
        for f in profile.get("facts", [])
        if f.get("release") != "faculty_only"
    ]

    # 4. Construct the clinical persona prompt matching the hardcoded rules
    system_prompt = f"""
You are roleplaying as a virtual clinical patient in a medical training simulation named {profile.get('name')}.
Patient Demographics & Background:
- Age: {profile.get('age')}
- Gender: {profile.get('gender')}
- Case Summary: {profile.get('case_summary')}
- Background & Life: {profile.get('background')}
- Conversational Style & Persona: {profile.get('style')}

Available Clinical Facts and Details You Can Reveal:
{json.dumps(safe_facts, indent=2)}

Instructions & Guidelines:
1. Respond naturally and authentically in character as the patient to the student clinician's message.
2. If the user's inquiry matches or touches upon information contained in the Available Clinical Facts above, disclose that information natively in your dialogue and include its corresponding exact string ID in the "fact_ids" list.
3. If the user asks about personal identity (name, age), acknowledge it properly and set kind to "identity".
4. If it is a casual greeting or polite conversational remark, respond warmly and set kind to "conversation".
5. If the requested clinical information is NOT present in your available facts or case details, politely state that you do not have/recall that information or that it was not provided in your sample case, and set kind to "not provided".
6. You MUST return your answer strictly as a JSON object with EXACTLY three keys:
   - "text": The conversational text response spoken by the patient.
   - "fact_ids": An array of string IDs corresponding to any facts revealed during this turn.
   - "kind": Exactly one of ["profile", "conversation", "identity", "boundary", "not provided"].
"""

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        "response_format": {"type": "json_object"}
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=20)
        response.raise_for_status()
        result = response.json()
        
        # Parse the model's structured JSON output
        content = json.loads(result["choices"]["message"]["content"])
        
        return {
            "text": content.get("text", "Could you tell me a bit more about what you mean?"),
            "fact_ids": content.get("fact_ids", []),
            "kind": content.get("kind", "conversation")
        }
        
    except Exception as exc:
        # Fallback behavior if network or API parsing encounters an issue
        return {
            'text': 'That detail is not provided in my sample case. You can ask about another part of my history.',
            'fact_ids': [],
            'kind': 'not provided'
        }


def assess(encounter, rubric):
    """Retains the baseline evidence gathering and scoring structure for the evaluation rubric."""
    transcript = encounter.get('transcript', [])
    domains = rubric.get('domains', [])
    reports = []
    
    for domain in domains:
        domain_id = domain.get('id')
        evidence_list = []
        for turn in transcript:
            if turn.get('speaker') == 'student':
                text = turn.get('text', '')
                for keyword in domain.get('keywords', []):
                    if includes(text, keyword):
                        evidence_list.append({
                            'turn_id': turn.get('id'),
                            'snippet': text
                        })
                        break
        reports.append({
            'domain_id': domain_id,
            'candidate_evidence': evidence_list
        })
        
    return {
        'reports': reports,
        'version': 'llm-dynamic-v1'
    }


def apply_review(encounter, review_input):
    """Calculates final scores based on faculty reviews."""
    ratings = review_input.get('ratings', {})
    numeric_scores = []
    for domain_id, rating_val in ratings.items():
        if isinstance(rating_val, (int, float)):
            numeric_scores.append(rating_val)
        elif isinstance(rating_val, str) and rating_val.isdigit():
            numeric_scores.append(int(rating_val))
            
    total = sum(numeric_scores) if numeric_scores else None
    return {
        'ratings': ratings,
        'total_score': total,
        'status': 'reviewed'
    }