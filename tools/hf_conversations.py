"""Download Postzeun/Patient-Doctor from Hugging Face and convert it into
TwinVerse-style conversations.

Dataset format (one line of text per row, blank rows in between):
    This is a conversation between a patient and a doctor. ...   <- starts a conversation
    This patient has the following symptoms:                     <- symptom list
    Additionally, this information about the patient may be useful:  <- patient info
    ---                                                          <- dialogue starts
    D: What brought you in today?
    P: I'm having a lot of chest pain ...

Output (default data/hf/conversations.json): a list of
    {"id": "hf-00001", "symptoms": [...], "patient_info": [...],
     "turns": [{"id": "t0", "role": "student"|"patient", "text": "..."}]}
Doctor turns use role "student" to match the app's message format.

Setup once:  pip install datasets
Run:         py -3 tools/hf_conversations.py            (Windows)
             python3 tools/hf_conversations.py          (Mac/Linux)
Offline:     py -3 tools/hf_conversations.py --text-file my_export.txt
"""
import argparse
import json
import re
from pathlib import Path

DATASET = 'Postzeun/Patient-Doctor'
SOURCE = f'https://huggingface.co/datasets/{DATASET}'
HEADER = re.compile(r'^\s*this is a conversation between', re.I)
SYMPTOMS = re.compile(r'^\s*this patient has the following symptoms', re.I)
INFO = re.compile(r'^\s*additionally, this information about the patient', re.I)
SPEAKER = re.compile(r'^\s*(D|P|Doctor|Patient)\s*:\s*(.*)$', re.I)


def parse(lines):
    """Turn raw dataset lines into conversations with symptoms, patient info and turns."""
    convos, cur, section = [], None, None

    def close():
        if cur and cur['turns']:
            convos.append(cur)

    for raw in lines:
        for line in (raw or '').splitlines() or ['']:
            s = line.strip()
            if not s:
                continue
            if HEADER.match(s):
                close()
                cur, section = {'symptoms': [], 'patient_info': [], 'turns': []}, 'header'
                continue
            if cur is None:  # data before the first header: start an unlabeled conversation
                cur, section = {'symptoms': [], 'patient_info': [], 'turns': []}, 'dialogue'
            if SYMPTOMS.match(s):
                section = 'symptoms'; continue
            if INFO.match(s):
                section = 'patient_info'; continue
            if s == '---':
                section = 'dialogue'; continue
            m = SPEAKER.match(s)
            if m:
                section = 'dialogue'
                role = 'student' if m.group(1).lower().startswith('d') else 'patient'
                text = m.group(2).strip()
                turns = cur['turns']
                if turns and turns[-1]['role'] == role:
                    turns[-1]['text'] += ' ' + text
                else:
                    turns.append({'role': role, 'text': text})
            elif section in ('symptoms', 'patient_info'):
                cur[section].append(s)
            elif section == 'dialogue' and cur['turns']:
                cur['turns'][-1]['text'] += ' ' + s
    close()
    return convos


def load_lines(text_file=None):
    if text_file:
        return Path(text_file).read_text(encoding='utf-8').splitlines()
    try:
        from datasets import load_dataset
    except ImportError:
        raise SystemExit('Missing package. Run:  pip install datasets')
    print(f'Downloading {DATASET} from Hugging Face ...')
    return (r['text'] for r in load_dataset(DATASET, split='train'))


def build(lines, min_turns=4, limit=0):
    convos = [c for c in parse(lines) if len(c['turns']) >= min_turns]
    if limit:
        convos = convos[:limit]
    return [{'id': f'hf-{i:05d}', 'source': SOURCE, 'symptoms': c['symptoms'], 'patient_info': c['patient_info'],
             'turns': [{'id': f't{j}', **t} for j, t in enumerate(c['turns'])]} for i, c in enumerate(convos, 1)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--limit', type=int, default=0, help='max conversations to keep (0 = all)')
    ap.add_argument('--min-turns', type=int, default=4, help='skip conversations shorter than this')
    ap.add_argument('--text-file', help='parse a local text export instead of downloading')
    ap.add_argument('--out', default='data/hf/conversations.json')
    args = ap.parse_args()

    out = build(load_lines(args.text_file), args.min_turns, args.limit)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
    print(f'Saved {len(out)} conversations ({sum(len(c["turns"]) for c in out)} turns) to {path}')
    if out:
        c = out[0]
        print('\nFirst conversation:', '; '.join(c['symptoms'][:3]) or '(no symptom list)')
        for t in c['turns'][:6]:
            print(f"  {'Doctor ' if t['role'] == 'student' else 'Patient'}: {t['text'][:90]}")


if __name__ == '__main__':
    main()
