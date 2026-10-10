"""Run a demo case's scripted clinician lines through the real engine and scorer,
and write a stage-ready demo script with the exact replies, chart updates and
expected scores.

Usage:
  python3 tools/run_demo_script.py data/cases/adult-yvette-armstrong.json
  python3 tools/run_demo_script.py --all          (every file in data/cases/)
Writes docs/demo/<case_id>.md and docs/demo/<case_id>.expected.json
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.engine import reply  # noqa: E402
from backend.scoring import load_criteria, score  # noqa: E402

DOMAIN_NAMES = {1: 'Opening and purpose', 2: 'Rapport, respect, and empathy', 3: 'Information gathering',
                4: 'Listening and response to cues', 5: 'Explanation and shared decisions',
                6: 'Clinical reasoning and synthesis', 7: 'Professionalism, safety, and closure'}


def simulate(case):
    """Mirror the server's turn handling: reply, disclosure log, message ids."""
    p = case['profile']
    now = datetime.now(timezone.utc).isoformat()
    messages = [{'id': 't0', 'role': 'patient', 'text': f"Hello, I'm {p['name'].split()[0]}. What would you like to talk about?",
                 'timestamp': now, 'fact_ids': [], 'kind': 'opening'}]
    disclosed = [f['id'] for f in p['facts'] if f['release'] == 'initial']
    steps = []
    for s in case['demo_script']:
        tid = f't{len(messages)}'
        messages.append({'id': tid, 'role': 'student', 'text': s['clinician'], 'timestamp': now})
        r = reply(p, s['clinician'])
        messages.append({'id': f't{len(messages)}', 'role': 'patient', 'text': r['text'], 'timestamp': now,
                         'fact_ids': r['fact_ids'], 'kind': r['kind'], 'reply_to': tid})
        new = [f for f in r['fact_ids'] if f not in disclosed]
        disclosed += new
        steps.append({**s, 'turn_id': tid, 'patient_reply': r['text'], 'reply_kind': r['kind'],
                      'chart_adds': [next(f['label'] for f in p['facts'] if f['id'] == x) for x in new]})
    return messages, steps, disclosed


def run(path):
    case = json.loads(Path(path).read_text(encoding='utf-8'))
    messages, steps, disclosed = simulate(case)
    result = score(load_criteria(), {'id': 'demo', 'profile': case['profile'], 'messages': messages})
    # which criteria each clinician turn earned
    by_turn = {}
    for r in result['criteria_results']:
        if r['met']:
            for e in r['evidence']:
                by_turn.setdefault(e['turn_id'], []).append(r['id'])
    for s in steps:
        s['criteria_met'] = sorted(set(by_turn.get(s['turn_id'], [])))

    sections = []
    met_ids = {r['id'] for r in result['criteria_results'] if r['met']}
    for sec in (case.get('case_rubric') or {}).get('point_sections', []):
        hit = [c for c in sec['criteria'] if c in met_ids]
        sections.append({**sec, 'met': hit, 'earned': round(sec['points'] * len(hit) / len(sec['criteria']))})

    p = case['profile']
    never = [f['label'] for f in p['facts'] if f['id'] not in disclosed and f['release'] != 'faculty_only']
    out_dir = ROOT / 'docs/demo'
    out_dir.mkdir(parents=True, exist_ok=True)
    expected = {'case_id': case['case_id'], 'patient': p['name'], 'steps': steps, 'facts_disclosed': disclosed,
                'facts_not_disclosed': never, 'score': result, 'point_sections': sections}
    (out_dir / f"{case['case_id']}.expected.json").write_text(json.dumps(expected, indent=1, ensure_ascii=False), encoding='utf-8')

    L = [f"# Demo script: {p['name']} ({p['age']}, {p['gender']})", '',
         f"_{case.get('role_in_demo', '')}_", '',
         f"**Case file:** `data/cases/{Path(path).name}` · **Generated:** {datetime.now():%Y-%m-%d %H:%M} by `tools/run_demo_script.py`", '',
         '> Type each clinician line exactly as written. Replies, chart updates and scores below were produced by running this script through the app\'s engine and scorer.', '',
         '## Script', '']
    for s in steps:
        L.append(f"### {s['step']}. {s['phase']}")
        L.append(f"**Clinician types:** {s['clinician']}")
        L.append('')
        L.append(f"**Patient replies:** {s['patient_reply']}")
        extra = []
        if s['chart_adds']:
            extra.append('Chart adds: ' + ', '.join(s['chart_adds']))
        if s['criteria_met']:
            extra.append('Scores: ' + ', '.join(s['criteria_met']))
        if s.get('note'):
            extra.append('Say to judges: ' + s['note'])
        if s['reply_kind'] == 'not_provided':
            extra.append('Grounding: patient declines to invent a fact')
        if extra:
            L.append('')
            L += [f"- {x}" for x in extra]
        L.append('')
    L += ['## Expected automatic score', '', '| # | Domain | Score | Coverage | Missed |', '|---|---|---|---|---|']
    for d in result['domains']:
        cov = '-' if d['coverage'] is None else f"{round(100 * d['coverage'])}%"
        L.append(f"| {d['id']} | {DOMAIN_NAMES[d['id']]} | {d['score']} | {cov} | {', '.join(d['missed']) or '-'} |")
    L += ['', f"**Total: {result['total']} / {result['available_points']}**"
          + (f" ({result['na_domains']} N/A)" if result['na_domains'] else ''), '']
    if sections:
        L += ['**Case point rubric:**', '', '| Section | Points | Met |', '|---|---|---|']
        L += [f"| {x['section']} | {x['earned']} / {x['points']} | {', '.join(x['met']) or '-'} |" for x in sections]
        L += ['', f"**Case points: {sum(x['earned'] for x in sections)} / {sum(x['points'] for x in sections)}**", '']
    if result['unsafe_actions']:
        L.append('**Unsafe actions flagged:** ' + '; '.join(u['id'] for u in result['unsafe_actions']))
    L += ['**Strengths:**'] + [f'- {x}' for x in result['strengths']] + ['', '**Gaps:**'] + [f'- {x}' for x in result['gaps']]
    L += ['', '**Next-attempt suggestions:**'] + [f'- {x}' for x in result['next_attempt_suggestions'] if x]
    if never:
        L += ['', '**Facts never disclosed (show in feedback as missed):** ' + ', '.join(never)]
    if case.get('intentional_gaps'):
        L += ['', '## Intentional gaps', ''] + [f'- {x}' for x in case['intentional_gaps']]
    (out_dir / f"{case['case_id']}.md").write_text('\n'.join(L) + '\n', encoding='utf-8')
    return expected


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cases', nargs='*')
    ap.add_argument('--all', action='store_true')
    a = ap.parse_args()
    paths = sorted((ROOT / 'data/cases').glob('*.json')) if a.all or not a.cases else a.cases
    for path in paths:
        e = run(path)
        s = e['score']
        print(f"{e['case_id']}: {s['total']}/{s['available_points']}  domains "
              + ' '.join(f"D{d['id']}={d['score']}" for d in s['domains'])
              + (f"  case points {sum(x['earned'] for x in e['point_sections'])}/{sum(x['points'] for x in e['point_sections'])}" if e['point_sections'] else '')
              + f"  not_provided={sum(x['reply_kind'] == 'not_provided' for x in e['steps'])}")


if __name__ == '__main__':
    main()
