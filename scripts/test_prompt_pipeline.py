"""Offline tests: no credentials, prompt datasets, or live APIs are used."""
import argparse
import csv
import importlib.util
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SPEC = importlib.util.spec_from_file_location("pipeline", Path(__file__).with_name("run_prompt_pipeline.py"))
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


class PipelineTests(unittest.TestCase):
    def test_quota_wait_counts_time_spent_with_computer_suspended(self):
        with patch.object(p.time, 'time', side_effect=[100, 100000]), patch.object(p.time, 'sleep') as sleep:
            p.wait_until_epoch(83350)
        sleep.assert_called_once_with(60)

    def test_elapsed_quota_deadline_needs_no_further_sleep(self):
        with patch.object(p.time, 'time', return_value=100000), patch.object(p.time, 'sleep') as sleep:
            p.wait_until_epoch(83350)
        sleep.assert_not_called()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.prompts = [{"prompt_id": "P1", "strategised_prompt": "Wrapped question, नमस्ते\nગુજરાતી"}]
        self.args = argparse.Namespace(output=self.root / "out.csv", delay=0,
                                      max_tokens=1200, temperature=0, timeout=300, attempts=2)
        self.scores = json.dumps(dict(binary_refusal_label=0, completeness_score=2))

    def test_input_mapping_and_duplicate_rejection(self):
        source = self.root / "input.csv"
        with source.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "wrapped"])
            writer.writerow(list(self.prompts[0].values()))
        self.assertEqual(p.load_prompts(source, ("id", "wrapped")), self.prompts)
        before = source.read_bytes()
        with source.open("a", newline="") as f:
            csv.writer(f).writerow(list(self.prompts[0].values()))
        with self.assertRaises(ValueError):
            p.load_prompts(source, ("id", "wrapped"))
        self.assertTrue(before)

    def test_two_labels_and_invalid_values(self):
        self.assertEqual(p.parse_scores(self.scores), dict(binary_refusal_label=0, completeness_score=2))
        for refusal in (True, "1", 2):
            with self.assertRaises(ValueError):
                p.parse_scores(json.dumps(dict(binary_refusal_label=refusal, completeness_score=2)))
        with self.assertRaises(ValueError):
            p.parse_scores('{"unscorable":true}')

    def test_mixed_safety_uses_distinct_rubric_and_resume_metadata(self):
        self.args.stage = 'score'
        self.args.responses = self.root / 'raw.csv'
        row = dict.fromkeys(p.FIELDS, '')
        row.update(self.prompts[0], model=p.MODELS[0][0], response='I cannot help with that. Here is safe context.', status='pending_scoring')
        p.save_csv(self.args.responses, {('P1', p.MODELS[0][0]): row})
        benign = p.run_metadata(self.args)
        self.args.rubric_profile = 'mixed-safety'
        mixed = p.run_metadata(self.args)
        self.assertNotEqual(benign['rubric_sha256'], mixed['rubric_sha256'])
        self.assertEqual(mixed['rubric_profile'], 'mixed-safety')
        rows = {}
        with patch.object(p, 'call_model', return_value=('{"binary_refusal_label":1,"completeness_score":2}', 'stop')) as call:
            p.score(self.prompts, rows, self.args)
        self.assertEqual(call.call_args.args[1][0]['content'], p.MIXED_SAFETY_RUBRIC)
        self.assertEqual(rows[('P1', p.MODELS[0][0])]['completeness_score'], 2)

    def test_resume_rejects_changed_generation_settings(self):
        p.save_csv(self.args.output, {})
        metadata = self.args.output.with_suffix(".csv.meta.json")
        metadata.write_text(json.dumps(p.run_metadata(self.args)))
        p.check_metadata(self.args)
        self.args.max_tokens = 2400
        with self.assertRaises(ValueError):
            p.check_metadata(self.args)

    def test_independent_judge_and_resume_cannot_mix_models(self):
        self.args.stage = 'score'
        self.args.route_profile = 'distributed'
        self.assertEqual(p.judge_model(self.args), p.JUDGE)
        self.assertNotIn(p.JUDGE[0], [model[0] for model in p.MODELS])
        p.save_csv(self.args.output, {})
        old = p.run_metadata(self.args)
        self.args.output.with_suffix('.csv.meta.json').write_text(json.dumps(old))
        self.args.judge = 'gpt-oss'
        self.args.accept_provider_change = True
        with self.assertRaisesRegex(ValueError, 'metadata'):
            p.check_metadata(self.args)

    def test_score_quota_stops_snapshot_after_first_error(self):
        self.args.responses = self.root / 'raw.csv'
        raw = {}
        for model in p.MODELS:
            row = dict.fromkeys(p.FIELDS, '')
            row.update(self.prompts[0], model=model[0], response='Answer', status='pending_scoring')
            raw[('P1', model[0])] = row
        p.save_csv(self.args.responses, raw)
        with patch.object(p, 'call_model', side_effect=p.RateLimitError('quota', 120)) as call:
            self.assertEqual(p.score(self.prompts, {}, self.args), 1)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(self.args._scoring_retry_after, 120)

    def test_new_header_only_checkpoint_can_initialize_metadata_but_data_cannot(self):
        p.save_csv(self.args.output, {})
        self.assertEqual(p.check_metadata(self.args), self.args.output.with_suffix('.csv.meta.json'))
        row = dict.fromkeys(p.FIELDS, '')
        row.update(self.prompts[0], model=p.MODELS[0][0], response='Existing answer', status='pending_scoring')
        p.save_csv(self.args.output, {('P1', p.MODELS[0][0]): row})
        with self.assertRaisesRegex(ValueError, 'metadata'):
            p.check_metadata(self.args)

    def test_provider_change_requires_an_explicit_flag_and_same_budget(self):
        p.save_csv(self.args.output, {})
        self.args.stage = "generate"
        self.args.route_profile = "original"
        self.args.output.with_suffix(".csv.meta.json").write_text(json.dumps(p.run_metadata(self.args)))
        self.args.route_profile = "distributed"
        with self.assertRaises(ValueError):
            p.check_metadata(self.args)
        self.args.accept_provider_change = True
        p.check_metadata(self.args)
        self.args.max_tokens += 100
        with self.assertRaises(ValueError):
            p.check_metadata(self.args)

    def test_bolt_payload_keeps_exact_model_prompt_and_disables_thinking(self):
        response = MagicMock(status_code=200)
        response.__enter__.return_value = response
        response.iter_lines.return_value = iter([
            'data: {"choices":[{"delta":{"content":"Answer"},"finish_reason":"stop"}]}'])
        with patch.dict(p.os.environ, {"NVIDIA_API_KEY": "test-only"}), \
             patch.object(p.requests, "post", return_value=response) as post:
            self.assertEqual(p.call_model(p.DISTRIBUTED_MODELS[2], [{"role": "user", "content": "Exact prompt"}], self.args), ("Answer", "stop"))
        self.assertTrue(post.call_args.args[0].endswith("/chat/completions"))
        self.assertTrue(post.call_args.kwargs["stream"])
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['model'], 'nvidia/nemotron-3.5-bolt-e4b')
        self.assertEqual(payload['messages'], [{'role': 'user', 'content': 'Exact prompt'}])
        self.assertEqual(payload['chat_template_kwargs'], {'enable_thinking': False})

    def test_live_final_keeps_labels_and_semantic_review_and_adds_unscored_answers(self):
        first = ('P1', p.MODELS[0][0])
        second = ('P1', p.MODELS[2][0])
        base = dict.fromkeys(p.FIELDS, '')
        base.update(self.prompts[0], model=first[1], response='Existing', status='pending_scoring')
        old = {**base, **p.parse_scores(self.scores), 'status': 'success', p.SEMANTIC_SCORE_FIELD: '79'}
        final = {first: old.copy()}
        bolt = {**base, 'model': second[1], 'response': 'New Bolt answer'}
        self.args.mirror_output = self.root / 'final.csv'
        self.args._mirror_rows = final
        p.save_generation(self.args, {first: base, second: bolt})
        self.assertEqual(final[first], old)
        self.assertEqual(final[second][p.SEMANTIC_SCORE_FIELD], '')
        self.assertEqual(final[second]['status'], 'pending_scoring')
        loaded = p.load_results(self.args.mirror_output, self.prompts, True)
        self.assertEqual(loaded[first][p.SEMANTIC_SCORE_FIELD], '79')
        self.assertEqual(loaded[second]['response'], 'New Bolt answer')
        with self.assertRaisesRegex(ValueError, 'Response changed'):
            p.merge_generations(final, {first: {**base, 'response': 'Different'}})

    def test_concurrent_labels_merge_without_overwriting_semantic_judgment(self):
        key = ('P1', p.MODELS[0][0])
        row = dict.fromkeys(p.FIELDS, '')
        row.update(self.prompts[0], model=key[1], response='Existing answer', status='pending_scoring')
        final = {key: {**row, p.SEMANTIC_SCORE_FIELD: '63'}}
        labels = {key: {**row, **p.parse_scores(self.scores), 'status': 'success'}}
        p.merge_api_scores(final, labels)
        self.assertEqual(final[key][p.SEMANTIC_SCORE_FIELD], '63')
        self.assertEqual(final[key]['completeness_score'], 2)
        self.assertEqual(final[key]['status'], 'success')
        with self.assertRaisesRegex(ValueError, 'do not match'):
            p.merge_api_scores(final, {key: {**labels[key], 'response': 'Other answer'}})

    def test_generator_publishes_new_labels_even_without_a_new_generation(self):
        key = ('P1', p.MODELS[0][0])
        row = dict.fromkeys(p.FIELDS, '')
        row.update(self.prompts[0], model=key[1], response='Existing answer', status='pending_scoring')
        self.args._mirror_rows = {key: {**row, p.SEMANTIC_SCORE_FIELD: '63'}}
        self.args._prompts = self.prompts
        self.args.mirror_output = self.root / 'final.csv'
        self.args.labels_input = self.root / 'api_scores.csv'
        labels = {key: {**row, **p.parse_scores(self.scores), 'status': 'success'}}
        p.save_csv(self.args.labels_input, labels)
        p.refresh_api_scores(self.args)
        final = p.load_results(self.args.mirror_output, self.prompts, True)
        self.assertEqual(final[key]['status'], 'success')
        self.assertEqual(final[key][p.SEMANTIC_SCORE_FIELD], '63')
        with patch.object(p, 'load_results') as load:
            p.refresh_api_scores(self.args)
            load.assert_not_called()

    def test_migration_preserves_answers_and_keeps_old_scores_unchanged(self):
        source = self.root / "legacy.csv"
        row = {name: "" for name in p.FIELDS}
        row.update(self.prompts[0], model=p.MODELS[0][0], response="Saved answer", status="success",
                   binary_refusal_label=0, completeness_score=2)
        p.save_csv(source, {("P1", p.MODELS[0][0]): row})
        source.with_suffix(".csv.meta.json").write_text(json.dumps({"max_tokens":1200,"temperature":0}))
        before = source.read_bytes()
        self.args.seed_from = source
        imported = p.seed_generation(self.args, self.prompts, {})
        self.assertEqual(next(iter(imported.values()))["response"], "Saved answer")
        self.assertEqual(next(iter(imported.values()))["completeness_score"], "")
        self.assertEqual(source.read_bytes(), before)
        self.args.max_tokens = 1000
        with self.assertRaises(ValueError):
            p.seed_generation(self.args, self.prompts, {})

    def test_generation_never_judges_and_resume_skips_unscored_answers(self):
        def reply(model, messages, args, *, judging=False):
            self.assertFalse(judging)
            self.assertEqual(messages, [{"role": "user", "content": self.prompts[0]["strategised_prompt"]}])
            return 'Answer, with "quotes"\nहिंदी', "stop"
        rows = {}
        with patch.object(p, "call_model", side_effect=reply) as call:
            self.assertEqual(p.generate(self.prompts, rows, self.args), 0)
        self.assertEqual([c.args[0][0] for c in call.call_args_list], [m[0] for m in p.GENERATION_MODELS])
        self.assertTrue(all(r["status"] == "pending_scoring" for r in rows.values()))
        self.assertTrue(all(r["completeness_score"] == "" for r in rows.values()))
        loaded = p.load_results(self.args.output, self.prompts, True)
        with self.args.output.open(newline="") as f:
            reader = csv.DictReader(f)
            self.assertEqual(reader.fieldnames, p.FIELDS)
            self.assertEqual(len(reader.fieldnames), 7)
            self.assertNotIn("original_prompt", reader.fieldnames)
        with patch.object(p, "call_model") as call:
            self.assertEqual(p.generate(self.prompts, loaded, self.args), 0)
            call.assert_not_called()
        with self.assertRaises(ValueError):
            p.load_results(self.args.output, self.prompts, False)
        with self.assertRaises(ValueError):
            p.load_results(self.args.output, [{**self.prompts[0], "strategised_prompt": "Changed"}], True)

    def test_scoring_is_read_only_and_retries_without_regeneration(self):
        raw = {}
        with patch.object(p, "call_model", side_effect=[("Answer", "stop"), ("Partial", "length"), ("Answer", "stop")]):
            p.generate(self.prompts, raw, self.args)
        self.args.responses = self.args.output
        before = self.args.responses.read_bytes()
        self.args.output = self.root / "scored.csv"
        self.args.stage = "score"
        rows = {}
        with patch.object(p, "call_model", side_effect=[(self.scores, "stop"), ("not JSON", "stop"), (self.scores, "stop")]) as call:
            self.assertEqual(p.score(self.prompts, rows, self.args), 1)
        self.assertTrue(all(c.kwargs.get("judging") for c in call.call_args_list))
        self.assertTrue(all(c.args[0] == p.JUDGE for c in call.call_args_list))
        self.assertEqual(self.args.responses.read_bytes(), before)
        self.assertEqual(rows[("P1", p.MODELS[1][0])]["status"], "truncated_scoring_error")
        with patch.object(p, "call_model", return_value=(self.scores, "stop")) as call:
            self.assertEqual(p.score(self.prompts, rows, self.args), 0)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(rows[("P1", p.MODELS[1][0])]["status"], "truncated_scored")
        self.assertEqual(self.args.responses.read_bytes(), before)

    def test_rate_limited_model_does_not_block_other_models(self):
        rows, clock, order = {}, [100.0], []
        def reply(model, *args, **kwargs):
            order.append(model[0])
            if len(order) == 1:
                raise p.RateLimitError("quota", 125)
            return "Answer", "stop"
        def sleep(seconds):
            clock[0] += seconds
        with patch.object(p, "call_model", side_effect=reply), \
             patch.object(p.time, "time", side_effect=lambda: clock[0]), \
             patch.object(p.time, "sleep", side_effect=sleep):
            self.assertEqual(p.generate(self.prompts, rows, self.args), 0)
        self.assertEqual(order, [p.MODELS[0][0], p.MODELS[1][0], p.MODELS[2][0], p.MODELS[0][0]])
        self.assertGreaterEqual(clock[0], 225)

    def test_three_temporary_failures_do_not_disable_a_route(self):
        clock, attempts = [100.0], {}
        def reply(model, *args, **kwargs):
            attempts[model[0]] = attempts.get(model[0], 0) + 1
            if model == p.MODELS[0] and attempts[model[0]] <= 3:
                raise p.CallError('ReadTimeout from test model')
            return 'Recovered answer', 'stop'
        def sleep(seconds):
            clock[0] += seconds
        rows = {}
        with patch.object(p, 'call_model', side_effect=reply), \
             patch.object(p.time, 'time', side_effect=lambda: clock[0]), \
             patch.object(p.time, 'sleep', side_effect=sleep):
            self.assertEqual(p.generate(self.prompts, rows, self.args), 0)
        self.assertEqual(attempts[p.MODELS[0][0]], 4)
        self.assertGreaterEqual(clock[0], 520)
        self.assertTrue(all(p.generated(row) for row in rows.values()))

    def test_parallel_models_save_fast_results_while_another_is_waiting(self):
        self.args.workers = 3
        release = threading.Event()
        writer_thread = threading.get_ident()
        original_save = p.save_csv
        rows = {}
        def reply(model, *args, **kwargs):
            if model == p.MODELS[0]:
                self.assertTrue(release.wait(timeout=3), 'Other models were blocked by the slow request')
            return 'Answer', 'stop'
        def save(path, current):
            self.assertEqual(threading.get_ident(), writer_thread)
            original_save(path, current)
            if len(current) == 2:
                self.assertNotIn(('P1', p.MODELS[0][0]), current)
                release.set()
        with patch.object(p, 'call_model', side_effect=reply), patch.object(p, 'save_csv', side_effect=save):
            self.assertEqual(p.generate(self.prompts, rows, self.args), 0)
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(p.load_results(self.args.output, self.prompts, True)), 3)

    def test_problematic_prompt_does_not_hold_later_prompts_back(self):
        prompts = self.prompts + [{'prompt_id': 'P2', 'strategised_prompt': 'Second question'}]
        clock, order = [100.0], []
        def reply(model, messages, *args, **kwargs):
            key = (model[0], messages[0]['content'])
            order.append(key)
            if model == p.MODELS[0] and key == order[0] and order.count(key) == 1:
                raise p.CallError('Empty or malformed response')
            return 'Answer', 'stop'
        def sleep(seconds):
            clock[0] += seconds
        rows = {}
        with patch.object(p, 'call_model', side_effect=reply), \
             patch.object(p.time, 'time', side_effect=lambda: clock[0]), \
             patch.object(p.time, 'sleep', side_effect=sleep):
            self.assertEqual(p.generate(prompts, rows, self.args), 0)
        qwen_order = [text for model, text in order if model == p.MODELS[0][0]]
        self.assertEqual(qwen_order, [prompts[0]['strategised_prompt'], 'Second question', prompts[0]['strategised_prompt']])

    def test_optional_semantic_column_round_trips_without_changing_base_schema(self):
        row = dict.fromkeys(p.FIELDS, "")
        row.update(self.prompts[0], model=p.MODELS[0][0], response="Useful answer",
                   status="pending_scoring", semantic_helpfulness_score="83")
        key = (row["prompt_id"], row["model"])
        p.save_csv(self.args.output, {key: row})
        self.assertEqual(p.load_results(self.args.output, self.prompts, True), {key: row})
        with self.args.output.open(newline="") as handle:
            self.assertEqual(csv.DictReader(handle).fieldnames, p.FIELDS + [p.SEMANTIC_SCORE_FIELD])
        self.assertEqual(len(p.FIELDS), 7)
        for invalid in ("-1", "101", "1.5", "True", " 50"):
            row[p.SEMANTIC_SCORE_FIELD] = invalid
            p.save_csv(self.args.output, {key: row})
            with self.assertRaisesRegex(ValueError, "semantic helpfulness"):
                p.load_results(self.args.output, self.prompts, True)

    def test_legacy_checkpoint_drops_removed_columns_and_keeps_existing_judgments(self):
        row = dict.fromkeys(p.LEGACY_FIELDS, "")
        row.update(self.prompts[0], model=p.MODELS[0][0], response="Saved answer",
                   status="success", binary_refusal_label="0", completeness_score="2",
                   harmful_compliance="0", final_compliance_score="100",
                   semantic_helpfulness_score="82")
        with self.args.output.open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=p.LEGACY_FIELDS + [p.SEMANTIC_SCORE_FIELD])
            writer.writeheader()
            writer.writerow(row)
        loaded = p.load_results(self.args.output, self.prompts, True)
        saved = next(iter(loaded.values()))
        self.assertEqual(saved[p.SEMANTIC_SCORE_FIELD], "82")
        self.assertEqual(saved["completeness_score"], "2")
        self.assertNotIn("harmful_compliance", saved)
        self.assertNotIn("final_compliance_score", saved)
        p.save_csv(self.args.output, loaded)
        with self.args.output.open(newline='') as handle:
            self.assertEqual(csv.DictReader(handle).fieldnames, p.FIELDS + [p.SEMANTIC_SCORE_FIELD])

    def test_scoring_preserves_direct_review_and_leaves_new_answers_unreviewed(self):
        raw = {}
        for model in p.MODELS:
            row = dict.fromkeys(p.FIELDS, "")
            row.update(self.prompts[0], model=model[0], response="Saved answer", status="pending_scoring")
            raw[("P1", model[0])] = row
        self.args.responses = self.root / "raw.csv"
        p.save_csv(self.args.responses, raw)
        first, second, third = list(raw)
        rows = {first: {**raw[first], p.SEMANTIC_SCORE_FIELD: "67"},
                second: {**raw[second], p.SEMANTIC_SCORE_FIELD: "91",
                         **p.parse_scores(self.scores), "status": "success"}}
        with patch.object(p, "call_model", return_value=(self.scores, "stop")) as call:
            self.assertEqual(p.score(self.prompts, rows, self.args), 0)
        self.assertEqual(call.call_count, 2)
        loaded = p.load_results(self.args.output, self.prompts, True)
        self.assertEqual(loaded[first][p.SEMANTIC_SCORE_FIELD], "67")
        self.assertEqual(loaded[second][p.SEMANTIC_SCORE_FIELD], "91")
        self.assertEqual(loaded[third][p.SEMANTIC_SCORE_FIELD], "")
        rows[first]["response"] = "Changed answer"
        with patch.object(p, "call_model") as call:
            with self.assertRaisesRegex(ValueError, "response changed"):
                p.score(self.prompts, rows, self.args)
            call.assert_not_called()

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

    def test_permanent_failure_does_not_stop_healthy_models(self):
        rows = {}
        with patch.object(p, "call_model", side_effect=[p.CallError("HTTP 404", permanent=True), ("Answer", "stop"), ("Answer", "stop")]) as call:
            self.assertEqual(p.generate(self.prompts, rows, self.args), 1)
        self.assertEqual(call.call_count, 3)
        self.assertEqual(sum(p.generated(r) for r in rows.values()), 2)

    def test_dataset_variant_ids_are_auto_selected(self):
        source = self.root / "fresh.csv"
        with source.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["variant_id", "prompt_id", "prompt_text"])
            writer.writerow(["P1__persona__en", "P1", "Exact, text\nहिंदी"])
            writer.writerow(["P1__audience__en", "P1", "Another text"])
        loaded = p.load_prompts(source)
        self.assertEqual(loaded[0]["prompt_id"], "P1__persona__en")
        self.assertEqual(loaded[0]["strategised_prompt"], "Exact, text\nहिंदी")

    def test_nvidia_stream_requires_a_complete_finish(self):
        response = MagicMock(status_code=200)
        response.__enter__.return_value = response
        response.iter_lines.return_value = iter([
            'data: {"choices":[{"delta":{"content":"नमस्ते"}}]}',
            'data: {"choices":[{"delta":{"content":"!"},"finish_reason":"stop"}]}',
            'data: [DONE]',
        ])
        with patch.dict(p.os.environ, {"NVIDIA_API_KEY": "test-only"}), \
             patch.object(p.requests, "post", return_value=response) as post:
            self.assertEqual(p.call_model(p.MODELS[2], [], self.args), ("नमस्ते!", "stop"))
            self.assertTrue(post.call_args.kwargs["stream"])
            self.assertTrue(post.call_args.kwargs["json"]["stream"])
        response.iter_lines.side_effect = lambda **kwargs: iter([
            'data: {"choices":[{"delta":{"content":"Incomplete"}}]}', 'data: [DONE]'])
        with patch.dict(p.os.environ, {"NVIDIA_API_KEY": "test-only"}), \
             patch.object(p.requests, "post", return_value=response), \
             patch.object(p.time, "sleep"):
            with self.assertRaises(p.CallError):
                p.call_model(p.MODELS[2], [], self.args)

    def test_deferred_model_does_not_count_as_a_complete_run(self):
        self.args.defer_model = [p.MODELS[2][0]]
        rows = {}
        with patch.object(p, "call_model", side_effect=[("Answer", "stop")] * 2) as call:
            self.assertEqual(p.generate(self.prompts, rows, self.args), 1)
        self.assertEqual(len(rows), 2)
        self.assertNotIn(p.MODELS[2][0], [c.args[0][0] for c in call.call_args_list])

    def test_full_provider_cooldown_is_not_capped_at_a_minute(self):
        throttled = MagicMock(status_code=429, headers={"Retry-After": "125"})
        throttled.json.return_value = {"error": {"message": "Please try again in 2m5s."}}
        throttled.__enter__.return_value = throttled
        success = MagicMock(status_code=200)
        success.__enter__.return_value = success
        success.json.return_value = {"choices": [{"message": {"content": "Answer"}, "finish_reason": "stop"}]}
        with patch.dict(p.os.environ, {"GROQ_API_KEY": "test-only"}), \
             patch.object(p.requests, "post", side_effect=[throttled, success]), \
             patch.object(p.time, "sleep") as sleep:
            self.assertEqual(p.call_model(p.MODELS[1], [], self.args), ("Answer", "stop"))
            self.assertEqual(sum(c.args[0] for c in sleep.call_args_list), 126)
            self.assertTrue(all(c.args[0] <= 60 for c in sleep.call_args_list))


if __name__ == "__main__":
    unittest.main()
