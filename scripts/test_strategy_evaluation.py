"""Offline checks for paired rankings and missing-data handling."""
import csv
import tempfile
import unittest
from pathlib import Path

from evaluate_strategies import evaluate, paired_interval, read_input, summarize
from run_prompt_pipeline import FIELDS, MODELS, load_prompts, save_csv


class EvaluationTests(unittest.TestCase):
    def test_original_multilingual_input_has_coverage_reports_without_strategy_ranking(self):
        source = self.root / 'original.csv'
        with source.open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=['variant_id', 'prompt_id', 'language', 'prompt_text', 'review_status'])
            writer.writeheader()
            for lang in ('English', 'Hindi'):
                writer.writerow(dict(variant_id='H1__'+lang, prompt_id='H1', language=lang,
                                     prompt_text='Unchanged question '+lang, review_status='needs_review'))
        prompts = load_prompts(source)
        rows = {}
        for prompt in prompts:
            for model, *_ in MODELS:
                row = dict.fromkeys(FIELDS, '')
                row.update(prompt, model=model, response='Appropriate refusal', status='success',
                           binary_refusal_label=1, completeness_score=2)
                rows[(prompt['prompt_id'], model)] = row
        path = self.root / 'final.csv';save_csv(path, rows)
        result = evaluate(source, path, self.root / 'original_reports')
        self.assertEqual(result['expected_responses'], 6)
        self.assertEqual(result['scored_responses'], 6)
        self.assertEqual(result['observed_leaders'], [])
        self.assertFalse((self.root / 'original_reports/strategy_summary.csv').exists())
        self.assertTrue((self.root / 'original_reports/model_summary.csv').exists())
        self.assertTrue((self.root / 'original_reports/language_summary.csv').exists())

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.input = self.root / "input.csv"
        with self.input.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["variant_id", "prompt_id", "strategy", "language", "prompt_text", "review_status"])
            writer.writeheader()
            for base in ("P1", "P2"):
                for strategy in ("a", "b"):
                    writer.writerow(dict(variant_id=f"{base}__{strategy}__en", prompt_id=base,
                                         strategy=strategy, language="English", prompt_text=f"Prompt {base} {strategy}",
                                         review_status="needs_independent_review"))
        self.prompts, self.index = read_input(self.input)

    def results(self):
        rows = []
        for prompt in self.prompts:
            for model, *_ in MODELS:
                row = dict.fromkeys(FIELDS, "")
                c = 2 if "__a__" in prompt["prompt_id"] else 1
                row.update(prompt, model=model, response="answer", status="success", binary_refusal_label=0,
                           completeness_score=c, semantic_helpfulness_score=100 if c == 2 else 75)
                rows.append(row)
        return rows

    def test_complete_ranking_and_clustered_difference(self):
        rows = self.results()
        summary, matched = summarize(self.index, rows)
        self.assertEqual([r["expected"] for r in summary], [6, 6])
        self.assertEqual([r["matched_mean_semantic_score"] for r in summary], [100, 75])
        low, high, clusters = paired_interval(matched, "a", "b")
        self.assertEqual((low, high, clusters), (25, 25, 2))

    def test_error_excludes_entire_paired_cell_not_just_one_strategy(self):
        rows = self.results()
        rows[-1]["status"] = "api_error"
        rows[-1]["response"] = ""
        rows[-1]["semantic_helpfulness_score"] = ""
        for name in FIELDS[5:]:
            rows[-1][name] = ""
        summary, matched = summarize(self.index, rows)
        self.assertEqual([r["scored"] for r in summary], [6, 5])
        self.assertEqual([r["matched_reviewed"] for r in summary], [5, 5])
        self.assertEqual(len(matched), 10)
        # Empty score cells never enter means, refusal rates, or comparisons.
        self.assertEqual(summary[1]["mean_semantic_score"], 75)

    def test_no_results_never_claims_winner(self):
        summary = evaluate(self.input, self.root / "missing.csv", self.root / "reports")
        self.assertFalse(summary["collection_complete"])
        self.assertEqual(summary["observed_leaders"], [])
        self.assertEqual(summary["missing_responses"], 12)
        self.assertIn("No strategy winner", (self.root / "reports/strategy_report.md").read_text())

    def test_saved_csv_roundtrip_and_breakdowns(self):
        path = self.root / "results.csv"
        rows = {(r["prompt_id"], r["model"]): r for r in self.results()}
        save_csv(path, rows)
        result = evaluate(self.input, path, self.root / "reports")
        self.assertTrue(result["collection_complete"])
        self.assertEqual(result["observed_leaders"], ["a"])
        self.assertEqual(result["scored_responses"], 12)
        with (self.root / "reports/strategy_by_model.csv").open() as f:
            self.assertEqual(len(list(csv.DictReader(f))), 6)

    def test_truncated_scored_answers_are_not_selectively_dropped(self):
        rows = self.results()
        rows[-1]["status"] = "truncated_scored"
        rows[-1]["completeness_score"] = 0
        rows[-1]["semantic_helpfulness_score"] = 35
        summary, matched = summarize(self.index, rows)
        self.assertEqual([r["matched_reviewed"] for r in summary], [6, 6])
        self.assertEqual(len(matched), 12)
        self.assertLess(summary[1]["matched_mean_semantic_score"], 75)

    def test_provider_switch_does_not_become_a_strategy_effect(self):
        rows = self.results()
        providers = {(r["prompt_id"], r["model"]): "groq" for r in rows}
        providers[(rows[-1]["prompt_id"], rows[-1]["model"])] = "nvidia"
        summary, matched = summarize(self.index, rows, providers=providers)
        self.assertEqual([r["matched_reviewed"] for r in summary], [5, 5])
        self.assertEqual([r["scored"] for r in summary], [6, 6])

    def test_semantic_ranking_is_independent_of_api_labels_and_status(self):
        rows = self.results()
        for row in rows:
            row['status'] = 'pending_scoring'
            row['binary_refusal_label'] = row['completeness_score'] = ''
        summary, matched = summarize(self.index, rows)
        self.assertEqual([r['scored'] for r in summary], [0, 0])
        self.assertEqual([r['matched_reviewed'] for r in summary], [6, 6])
        self.assertEqual([r['matched_mean_semantic_score'] for r in summary], [100, 75])
        rows[-1]['semantic_helpfulness_score'] = ''
        summary, matched = summarize(self.index, rows)
        self.assertEqual([r['matched_reviewed'] for r in summary], [5, 5])

    def test_api_labels_without_semantic_reviews_cannot_produce_a_winner(self):
        rows = self.results()
        for row in rows:
            row['semantic_helpfulness_score'] = ''
        summary, matched = summarize(self.index, rows)
        self.assertFalse(matched)
        self.assertEqual([r['scored'] for r in summary], [6, 6])
        self.assertEqual([r['semantic_reviewed'] for r in summary], [0, 0])


if __name__ == "__main__":
    unittest.main()
