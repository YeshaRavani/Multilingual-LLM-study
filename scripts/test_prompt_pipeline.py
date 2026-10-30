"""Offline tests: no credentials, prompt datasets, or live APIs are used."""
import argparse
import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SPEC = importlib.util.spec_from_file_location("pipeline", Path(__file__).with_name("run_prompt_pipeline.py"))
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.prompts = [{"prompt_id": "P1", "original_prompt": "Original, question\nनमस्ते",
                         "strategised_prompt": "Wrapped question\nગુજરાતી"}]
        self.args = argparse.Namespace(output=self.root / "out.csv", delay=0,
                                      max_tokens=1200, temperature=0, timeout=300, attempts=2)
        self.scores = json.dumps(dict(binary_refusal_label=0, completeness_score=2, harmful_compliance=0))

    def test_input_mapping_and_duplicate_rejection(self):
        source = self.root / "input.csv"
        with source.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "original", "wrapped"])
            writer.writerow(list(self.prompts[0].values()))
        self.assertEqual(p.load_prompts(source, ("id", "original", "wrapped")), self.prompts)
        before = source.read_bytes()
        with source.open("a", newline="") as f:
            csv.writer(f).writerow(list(self.prompts[0].values()))
        with self.assertRaises(ValueError):
            p.load_prompts(source, ("id", "original", "wrapped"))
        self.assertTrue(before)

    def test_formula_and_invalid_labels(self):
        self.assertEqual(p.final_score(0, 2, 0), 100)
        self.assertEqual(p.final_score(1, 0, 0), 25)
        self.assertEqual(p.final_score(0, 1, 0), 75)
        self.assertLess(p.final_score(0, 2, 4), p.final_score(0, 2, 0))
        for refusal in (True, "1", 2):
            with self.assertRaises(ValueError):
                p.parse_scores(json.dumps(dict(binary_refusal_label=refusal, completeness_score=2, harmful_compliance=0)))
        with self.assertRaises(ValueError):
            p.parse_scores('{"unscorable":true}')

    def test_resume_rejects_changed_generation_settings(self):
        p.save_csv(self.args.output, {})
        metadata = self.args.output.with_suffix(".csv.meta.json")
        metadata.write_text(json.dumps(p.run_metadata(self.args)))
        p.check_metadata(self.args)
        self.args.max_tokens = 2400
        with self.assertRaises(ValueError):
            p.check_metadata(self.args)

    def test_sequential_calls_exact_schema_and_resume(self):
        def reply(model, messages, args, *, judging=False):
            if not judging:
                self.assertEqual(messages, [{"role": "user", "content": self.prompts[0]["strategised_prompt"]}])
            return (self.scores if judging else 'Answer, with "quotes"\nहिंदी'), "stop"
        rows = {}
        with patch.object(p, "call_model", side_effect=reply) as call:
            self.assertEqual(p.run(self.prompts, rows, self.args), 0)
        self.assertEqual([c.args[0][0] for c in call.call_args_list],
                         [p.MODELS[0][0], p.MODELS[1][0], p.MODELS[1][0],
                          p.MODELS[1][0], p.MODELS[2][0], p.MODELS[1][0]])
        loaded = p.load_results(self.args.output, self.prompts, True)
        self.assertEqual(len(loaded), 3)
        with self.args.output.open(newline="") as f:
            reader = csv.DictReader(f)
            self.assertEqual(reader.fieldnames, p.FIELDS)
            self.assertEqual(next(reader)["original_prompt"], self.prompts[0]["original_prompt"])
        with patch.object(p, "call_model") as call:
            self.assertEqual(p.run(self.prompts, loaded, self.args), 0)
            call.assert_not_called()
        with self.assertRaises(ValueError):
            p.load_results(self.args.output, self.prompts, False)
        with self.assertRaises(ValueError):
            p.load_results(self.args.output, [{**self.prompts[0], "strategised_prompt": "Changed"}], True)

    def test_generation_failure_truncation_and_scoring_recovery(self):
        calls = [p.CallError("HTTP 401"), ("Partial", "length"), ("Good answer", "stop"), ("invalid JSON", "stop")]
        rows = {}
        with patch.object(p, "call_model", side_effect=calls):
            self.assertEqual(p.run(self.prompts, rows, self.args), 1)
        self.assertEqual([r["status"] for r in rows.values()], ["api_error", "truncated", "scoring_error"])
        self.assertTrue(all(r["binary_refusal_label"] == "" for r in rows.values()))
        self.assertTrue(all(r["final_compliance_score"] == "" for r in rows.values()))
        recovery = [("Recovered", "stop"), (self.scores, "stop"),
                    ("Recovered", "stop"), (self.scores, "stop"), (self.scores, "stop")]
        with patch.object(p, "call_model", side_effect=recovery) as call:
            self.assertEqual(p.run(self.prompts, rows, self.args), 0)
        self.assertTrue(call.call_args_list[-1].kwargs["judging"])
        self.assertEqual(len(p.load_results(self.args.output, self.prompts, True)), 3)

    def test_http_retry_and_provider_payloads(self):
        throttled = MagicMock(status_code=429, headers={"Retry-After": "1"})
        success = MagicMock(status_code=200)
        success.json.return_value = {"choices": [{"message": {"content": "Answer"}, "finish_reason": "stop"}]}
        throttled.__enter__.return_value = throttled
        success.__enter__.return_value = success
        with patch.dict(p.os.environ, {"GROQ_API_KEY": "test-only"}), \
             patch.object(p.requests, "post", side_effect=[throttled, success]) as post, \
             patch.object(p.time, "sleep") as sleep:
            self.assertEqual(p.call_model(p.MODELS[0], [], self.args), ("Answer", "stop"))
            self.assertEqual(post.call_count, 2)
            sleep.assert_called_once()
            self.assertEqual(post.call_args.kwargs["json"]["model"], "qwen/qwen3.8-27b")
            self.assertEqual(post.call_args.kwargs["json"]["reasoning_effort"], "none")
        denied = MagicMock(status_code=401)
        denied.__enter__.return_value = denied
        with patch.dict(p.os.environ, {"NVIDIA_API_KEY": "test-only"}), \
             patch.object(p.requests, "post", return_value=denied) as post:
            with self.assertRaises(p.CallError):
                p.call_model(p.MODELS[2], [], self.args)
            self.assertEqual(post.call_count, 1)


if __name__ == "__main__":
    unittest.main()
