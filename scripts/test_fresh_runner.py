"""Offline test for deferred-model recovery in the long-running wrapper."""
import importlib.util
import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("fresh_runner", Path(__file__).resolve().parents[1] / "dataset_fresh_start/run_models.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class FreshRunnerTests(unittest.TestCase):
    def test_parallel_supervisor_does_not_race_generator_for_final_lock(self):
        class Process:
            calls = 0
            def poll(self):
                self.calls += 1
                return None if self.calls == 1 else 0
        with tempfile.TemporaryDirectory() as directory:
            args = argparse.Namespace(output_dir=Path(directory), stage='parallel')
            summary = dict(scored_responses=3, expected_responses=3, collection_complete=True,
                           generation_complete=True, generated_responses=3, observed_leaders=[])
            with patch.object(runner.subprocess, 'Popen', side_effect=[Process(), Process()]), \
                 patch.object(runner, 'refresh', return_value=summary) as refresh, \
                 patch.object(runner.time, 'monotonic', side_effect=[31, 62]), \
                 patch.object(runner.time, 'sleep'):
                self.assertEqual(runner.collect_parallel({'generate': ['gen'], 'score': ['score']}, args), 0)
            self.assertFalse(refresh.call_args_list[0].kwargs['merge_labels'])
            self.assertTrue(refresh.call_args_list[1].kwargs['merge_labels'])

    def test_parallel_mode_separates_writers_and_follows_new_responses(self):
        with tempfile.TemporaryDirectory() as directory:
            summary = dict(scored_responses=0, expected_responses=3, collection_complete=False,
                           generation_complete=False, generated_responses=1, observed_leaders=[])
            with patch.object(runner.sys, 'argv', ['run_models.py', '--stage', 'parallel', '--output-dir', directory]), \
                 patch.object(runner, 'collect_parallel', return_value=1) as collect, \
                 patch.object(runner, 'refresh', return_value=summary):
                self.assertEqual(runner.main(), 1)
            commands = collect.call_args.args[0]
            self.assertIn('--labels-input', commands['generate'])
            self.assertIn('--follow', commands['score'])
            self.assertIn(str(Path(directory) / 'api_scores.csv'), commands['score'])
            self.assertNotIn('--mirror-output', commands['score'])
            self.assertTrue((Path(directory) / 'generated_responses.csv').exists())
            self.assertTrue((Path(directory) / 'final_output.csv').exists())

    def test_incomplete_generation_does_not_start_scoring(self):
        with tempfile.TemporaryDirectory() as directory:
            summary = dict(scored_responses=0, expected_responses=3,
                           collection_complete=False, generation_complete=False,
                           generated_responses=1, observed_leaders=[])
            argv = ['run_models.py', '--output-dir', directory, '--stage', 'all']
            with patch.object(runner.sys, 'argv', argv), \
                 patch.object(runner, 'collect', return_value=1) as collect, \
                 patch.object(runner, 'evaluate', return_value=summary):
                self.assertEqual(runner.main(), 1)
            self.assertEqual(collect.call_count, 1)
            self.assertIn('generate', collect.call_args.args[0])

    def test_all_runs_generation_and_scoring_in_distinct_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            summary = dict(scored_responses=3, expected_responses=3,
                           collection_complete=True, generation_complete=True, generated_responses=3, observed_leaders=["example"])
            argv = ["run_models.py", "--output-dir", str(out), "--stage", "all"]
            with patch.object(runner.sys, "argv", argv), \
                 patch.object(runner, "collect", side_effect=[0, 0]) as collect, \
                 patch.object(runner, "evaluate", return_value=summary):
                self.assertEqual(runner.main(), 0)
            second_command = collect.call_args_list[1].args[0]
            self.assertIn("score", second_command)
            self.assertIn("--responses", second_command)
            self.assertIn("generate", collect.call_args_list[0].args[0])
            self.assertIn('--mirror-output', collect.call_args_list[0].args[0])
            self.assertNotIn('--mirror-output', second_command)
            self.assertNotEqual(collect.call_args_list[0].args[0], second_command)
            status = json.loads((out / "job_status.json").read_text())
            self.assertEqual(status["state"], "complete")
            self.assertEqual(status["scored"], 3)


if __name__ == "__main__":
    unittest.main()
