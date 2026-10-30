"""Offline checks of the strategy manipulation and source preservation."""
import csv
from pathlib import Path
import unittest

from strategy_content import CONTENT, STRATEGIES, expand


class DesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(__file__).resolve().parents[2] / 'data/source_prompts_research_v1.csv'
        with source.open(encoding='utf-8', newline='') as f:
            cls.rows = [r for r in csv.DictReader(f) if r['expected_outcome'] == 'answer']

    def test_exact_source_set(self):
        self.assertEqual(len(self.rows), 40)
        self.assertEqual({r['prompt_id'] for r in self.rows}, set(CONTENT))

    def test_questions_verbatim_in_every_condition(self):
        for row in self.rows:
            for strategy in STRATEGIES:
                self.assertIn(row['canonical_english_prompt'], expand(row, strategy))

    def test_160_distinct_expansions(self):
        text = [expand(r, s) for r in self.rows for s in STRATEGIES]
        self.assertEqual(len(text), 160)
        self.assertEqual(len(set(text)), 160)

    def test_explicit_strategy_markers(self):
        for row in self.rows:
            self.assertTrue(expand(row, 'persona_builder').startswith('I am '))
            self.assertTrue(expand(row, 'emotional_stakes').startswith('I am worried'))
            self.assertIn('\n1. ', expand(row, 'task_decomposition'))
            self.assertIn('\n2. ', expand(row, 'task_decomposition'))
            self.assertTrue(expand(row, 'audience_framing').startswith('The answer is intended for '))

    def test_original_teen_audience_not_overridden(self):
        row = next(r for r in self.rows if r['prompt_id'] == 'MSF-043')
        introduction = expand(row, 'audience_framing').split('\n\n')[0]
        self.assertIn('older teenagers', introduction)
        self.assertNotIn('adults', introduction)


if __name__ == '__main__':
    unittest.main()
