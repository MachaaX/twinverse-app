"""Use the Hugging Face doctor-patient conversations as a reference for what
standard clinician behaviour looks like on our rubric.

For every HF conversation it runs the app's own scorer (backend/scoring.py,
universal criteria only) and records:
  * how often clinicians show each rubric behaviour (e.g. "asks about allergies")
  * real example clinician lines for each behaviour
  * the distribution of domain scores and totals, i.e. a benchmark for a
    "typical" clinician interview that student scores can be compared against

Input:  data/hf/conversations.json  (from tools/hf_conversations.py)
Output: data/hf/rubric_reference.json

Run:  py -3 tools/build_rubric_reference.py          (Windows)
      python3 tools/build_rubric_reference.py        (Mac/Linux)
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.scoring import score, DOMAIN_KEYS  # noqa: E402


def pct(n, d):
    return round(100 * n / d, 1) if d else 0.0


def quantiles(values):
    if not values:
        return None
    v = sorted(values)
    q = lambda p: v[min(len(v) - 1, int(p * (len(v) - 1)))]
    return {'min': v[0], 'p25': q(.25), 'median': q(.5), 'p75': q(.75), 'max': v[-1],
            'mean': round(statistics.mean(v), 2)}


def build(convos, crit, examples_per_criterion=5):
    # Universal criteria only: HF conversations are not one of our patients.
    crit = {**crit, 'patients': {}}
    universal = {c['id']: c for c in crit['universal_criteria']}
    met_count = {cid: 0 for cid in universal}
    applicable = {cid: 0 for cid in universal}
    examples = {cid: [] for cid in universal}
    domain_scores = {d: [] for d in DOMAIN_KEYS}
    totals = []

    for c in convos:
        enc = {'id': c['id'], 'patient_id': 'hf-reference', 'profile': {'objectives': []},
               'messages': [{**t} for t in c['turns']]}
        r = score(crit, enc)
        totals.append(r['total'])
        for d in r['domains']:
            if isinstance(d['score'], int):
                domain_scores[d['id']].append(d['score'])
        for row in r['criteria_results']:
            cid = row['id']
            if cid not in universal or row['met'] is None:
                continue
            applicable[cid] += 1
            if row['met']:
                met_count[cid] += 1
                for e in row['evidence']:
                    q = e.get('quote', '')
                    if (e['turn_id'] != '-' and not q.startswith(('(', 'phase', 'NEGATIVE'))
                            and 15 <= len(q) <= 220 and len(examples[cid]) < examples_per_criterion
                            and q not in [x['text'] for x in examples[cid]]):
                        examples[cid].append({'conversation': c['id'], 'turn_id': e['turn_id'], 'text': q})

    behaviours = []
    for cid, c in universal.items():
        behaviours.append({
            'id': cid, 'domain': c['domain'], 'domain_key': DOMAIN_KEYS[c['domain']], 'tier': c['tier'],
            'criterion': c['criterion'],
            'hf_rate_percent': pct(met_count[cid], applicable[cid]),
            'hf_conversations_applicable': applicable[cid],
            'standard': ('common' if pct(met_count[cid], applicable[cid]) >= 50 else
                         'sometimes' if pct(met_count[cid], applicable[cid]) >= 15 else 'rare'),
            'example_clinician_lines': examples[cid],
        })
    behaviours.sort(key=lambda b: (b['domain'], -b['hf_rate_percent']))

    return {
        'source': 'https://huggingface.co/datasets/Postzeun/Patient-Doctor',
        'note': ('Reference only. HF dialogues are simulated diagnostic interviews, not graded exemplars. '
                 '"standard" = how often real-style clinician turns showed the behaviour: common >=50%, '
                 'sometimes 15-49%, rare <15%. Our rubric still expects critical behaviours even when rare here '
                 '(e.g. teach-back), because HF interviews focus on diagnosis, not patient education.'),
        'conversations_analyzed': len(convos),
        'benchmark': {
            'total_score': quantiles(totals),
            'domains': {DOMAIN_KEYS[d]: quantiles(v) for d, v in domain_scores.items()},
        },
        'behaviours': behaviours,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--conversations', default='data/hf/conversations.json')
    ap.add_argument('--criteria', default='data/clinical_scoring_criteria.json')
    ap.add_argument('--out', default='data/hf/rubric_reference.json')
    ap.add_argument('--limit', type=int, default=0, help='analyze only the first N conversations')
    args = ap.parse_args()

    convos = json.loads(Path(args.conversations).read_text(encoding='utf-8'))
    if args.limit:
        convos = convos[:args.limit]
    crit = json.loads(Path(args.criteria).read_text(encoding='utf-8'))
    ref = build(convos, crit)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(ref, indent=1, ensure_ascii=False), encoding='utf-8')

    print(f"Analyzed {ref['conversations_analyzed']} conversations -> {args.out}")
    b = ref['benchmark']['total_score']
    if b:
        print(f"Typical clinician total (universal criteria): median {b['median']}, p25-p75 {b['p25']}-{b['p75']}")
    print('\nHow often clinicians show each behaviour:')
    for x in ref['behaviours']:
        print(f"  D{x['domain']} {x['hf_rate_percent']:5.1f}%  {x['standard']:9s} {x['criterion'][:70]}")


if __name__ == '__main__':
    main()
