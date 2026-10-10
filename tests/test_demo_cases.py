"""Demo case files load, run deterministically, and keep their expected scores."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
from backend.server import validate_profile  # noqa: E402
import run_demo_script  # noqa: E402
import hf_conversations  # noqa: E402

CASES = sorted((ROOT / 'data/cases').glob('*.json'))


class DemoCases(unittest.TestCase):
    def test_profiles_are_valid(self):
        for f in CASES:
            v = validate_profile(json.loads(f.read_text())['profile'])
            self.assertEqual(v['errors'], [], f.name)

    def test_scripts_are_deterministic_and_grounded(self):
        for f in CASES:
            a, b = run_demo_script.run(f), run_demo_script.run(f)
            self.assertEqual(a['score']['total'], b['score']['total'])
            self.assertEqual([s['patient_reply'] for s in a['steps']], [s['patient_reply'] for s in b['steps']])
            self.assertFalse(a['score']['unsafe_actions'], f.name)

    def test_hf_parser_reads_dataset_format(self):
        lines = (ROOT / 'tests/fixtures/hf_sample.txt').read_text().splitlines()
        convos = hf_conversations.build(lines, min_turns=2)
        self.assertEqual(len(convos), 2)
        self.assertEqual(convos[0]['turns'][0], {'id': 't0', 'role': 'student', 'text': 'What brought you in today?'})
        self.assertIn('Male, 39 years old', convos[0]['patient_info'])


if __name__ == '__main__':
    unittest.main()
