"""Offline tests. All API calls are mocked."""
import unittest
import io
from unittest.mock import patch

import run_dataset_h_benign as core


class RunnerTests(unittest.TestCase):
    def test_output_grouping(self):
        rows = [
            {'prompt_id': 'H002', 'condition_id': 'standard_english', 'configuration': 'nvidia_gpt_oss_20b'},
            {'prompt_id': 'H001', 'condition_id': 'hindi', 'configuration': 'nvidia_gpt_oss_20b'},
            {'prompt_id': 'H001', 'condition_id': 'standard_english', 'configuration': 'groq_gpt_oss_20b'},
            {'prompt_id': 'H001', 'condition_id': 'standard_english', 'configuration': 'nvidia_gpt_oss_20b'},
        ]
        ordered = sorted(rows, key=core.response_order)
        self.assertEqual([r['prompt_id'] for r in ordered], ['H001', 'H001', 'H001', 'H002'])
        self.assertEqual(ordered[0]['configuration'], 'nvidia_gpt_oss_20b')
        self.assertEqual(ordered[1]['configuration'], 'groq_gpt_oss_20b')
        self.assertEqual(ordered[2]['condition_id'], 'hindi')

    def test_full_score(self):
        self.assertEqual(core.weighted_quality(4, 2, 2), (100.0, 100))
        self.assertEqual(core.weighted_quality(2, 2, 1), (62.5, 100))

    def test_not_applicable_not_zero(self):
        score, coverage = core.weighted_quality(2, 2, '', True)
        self.assertAlmostEqual(score, 66.67)
        self.assertEqual(coverage, 75)

    def test_missing_not_invented(self):
        self.assertEqual(core.weighted_quality(2, 2, ''), ('', ''))
        self.assertEqual(core.weighted_quality('', '', ''), ('', ''))

    def test_invalid_score_rejected(self):
        with self.assertRaises(ValueError):
            core.weighted_quality(5, 2, 2)

    def test_json_input(self):
        rows = core.load_variants()
        self.assertEqual(len(rows), 112)
        self.assertEqual(len({r['prompt_id'] for r in rows}), 16)
        self.assertEqual(sum(r['prompt_id'] in core.ELIGIBLE for r in rows), 42)
        self.assertEqual(len({r['condition_id'] for r in rows}), 7)

    def test_collector_scope(self):
        # Include all 16 English records; verify only six can reach requests.
        rows = [r for r in core.load_variants() if r['condition_id'] == 'standard_english']
        with patch.object(core, 'load_variants', return_value=rows), \
             patch.object(core, 'read_jsonl', return_value=[]), \
             patch.object(core, 'append') as append, \
             patch.object(core, 'export'), \
             patch.object(core.time, 'sleep'), \
             patch.object(core, 'request', return_value={'response_text': 'Mock response', 'finish_reason': 'stop'}) as request:
            core.collect('groq_gpt_oss_20b')
        self.assertEqual(request.call_count, 6)
        submitted = {call.args[1]['prompt_id'] for call in append.call_args_list}
        self.assertEqual(submitted, core.ELIGIBLE)

    def test_resume_skips_success(self):
        row = next(r for r in core.load_variants() if r['prompt_id'] in core.ELIGIBLE)
        old = {**row, 'request_status': 'success', 'response_text': 'Saved reply'}
        with patch.object(core, 'load_variants', return_value=[row]), \
             patch.object(core, 'read_jsonl', return_value=[old]), \
             patch.object(core, 'request') as request:
            core.collect('groq_gpt_oss_20b')
        request.assert_not_called()

    def test_sequential_order(self):
        rows = [r for r in core.load_variants() if r['condition_id'] == 'standard_english' and r['prompt_id'] in core.ELIGIBLE][:2]
        with patch.object(core, 'load_variants', return_value=rows), \
             patch.object(core, 'read_jsonl', return_value=[]), \
             patch.object(core, 'collect', return_value=True) as collect, \
             patch('sys.stdout', new_callable=io.StringIO):
            core.collect_sequential(pacing=False)
        actual = [(c.args[0], c.kwargs['variant_ids'][0]) for c in collect.call_args_list]
        expected = [(config, r['variant_id']) for r in sorted(rows, key=lambda r: r['prompt_id']) for config in core.CONFIGS]
        self.assertEqual(actual, expected)

    def test_paused_model_does_not_stop_others(self):
        rows = [r for r in core.load_variants() if r['condition_id'] == 'standard_english' and r['prompt_id'] in core.ELIGIBLE][:2]
        with patch.object(core, 'load_variants', return_value=rows), \
             patch.object(core, 'read_jsonl', return_value=[]), \
             patch.object(core, 'collect', side_effect=lambda config, **kw: config != 'groq_qwen_3_8_27b') as collect, \
             patch('sys.stdout', new_callable=io.StringIO):
            core.collect_sequential(pacing=False)
        calls = [c.args[0] for c in collect.call_args_list]
        self.assertEqual(calls.count('groq_qwen_3_8_27b'), 1)
        self.assertEqual(calls.count('nvidia_gpt_oss_20b'), 2)
        self.assertEqual(calls.count('groq_gpt_oss_20b'), 2)

    def test_single_variant_scope_is_checked(self):
        with patch.object(core, 'read_jsonl', return_value=[]), \
             patch.object(core, 'request') as request:
            with self.assertRaises(ValueError):
                core.collect('groq_gpt_oss_20b', variant_ids=['H003__standard_english'])
        request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
