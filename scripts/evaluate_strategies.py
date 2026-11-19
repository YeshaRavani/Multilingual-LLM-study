"""Compare strategies on matched benign-prompt/model/language observations."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from run_prompt_pipeline import MODELS, SCORED_STATUSES, SEMANTIC_SCORE_FIELD, generated, load_prompts, load_results


SUMMARY_FIELDS = [
    "strategy", "expected", "scored", "coverage_percent", "semantic_reviewed", "matched_reviewed",
    "mean_semantic_score", "matched_mean_semantic_score", "refusal_percent", "mean_completeness",
]


def read_input(path: Path) -> tuple[list[dict], dict]:
    prompts = load_prompts(path)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not {"variant_id", "prompt_id", "strategy", "language"}.issubset(reader.fieldnames or []):
            raise ValueError("Strategy evaluation needs variant_id, prompt_id, strategy, and language in the input")
        index = {r["variant_id"]: r for r in reader}
    cells = set()
    for row in index.values():
        if any(not row[c].strip() for c in ("variant_id", "prompt_id", "strategy", "language")):
            raise ValueError("Blank input metadata")
        key = (row["prompt_id"], row["strategy"], row["language"])
        if key in cells:
            raise ValueError("Duplicate base-prompt/strategy/language input")
        cells.add(key)
    return prompts, index


def mean(rows: list[dict], key: str) -> float | str:
    return round(statistics.mean(float(r[key]) for r in rows), 4) if rows else ""


def summarize(index: dict, results: list[dict], dimension: str | None = None, providers: dict | None = None) -> tuple[list[dict], list[dict]]:
    strategies = sorted({r["strategy"] for r in index.values()})
    expected = Counter()
    for row in index.values():
        for model, *_ in MODELS:
            group = model if dimension == "model" else row[dimension] if dimension else "all"
            expected[(group, row["strategy"])] += 1
    successful = []
    cells = defaultdict(dict)
    for r in results:
        source = index[r["prompt_id"]]
        row = {**r, "base_prompt_id": source["prompt_id"],
               "strategy": source["strategy"], "language": source["language"],
               "_provider": providers.get((r["prompt_id"], r["model"])) if providers is not None else None}
        if r["status"] in SCORED_STATUSES:
            successful.append(row)
        if r.get(SEMANTIC_SCORE_FIELD, "") != "" and r["response"].strip():
            cells[(row["base_prompt_id"], row["language"], row["model"])][row["strategy"]] = row
    reviewed = [r for cell in cells.values() for r in cell.values()]
    # Only observations directly reviewed for EVERY strategy enter ranking.
    matched = [r for cell in cells.values() if set(cell) == set(strategies)
               and (providers is None or (all(v["_provider"] for v in cell.values())
                                         and len({v["_provider"] for v in cell.values()}) == 1))
               for r in cell.values()]
    summaries = []
    for (group, strategy), total in sorted(expected.items()):
        def belongs(row):
            return row["strategy"] == strategy and (not dimension or row[dimension] == group)
        all_rows = [r for r in successful if belongs(r)]
        reviewed_rows = [r for r in reviewed if belongs(r)]
        matched_rows = [r for r in matched if belongs(r)]
        summary = dict(strategy=strategy, expected=total, scored=len(all_rows),
                       coverage_percent=round(100 * len(all_rows) / total, 2),
                       semantic_reviewed=len(reviewed_rows), matched_reviewed=len(matched_rows),
                       mean_semantic_score=mean(reviewed_rows, SEMANTIC_SCORE_FIELD),
                       matched_mean_semantic_score=mean(matched_rows, SEMANTIC_SCORE_FIELD),
                       refusal_percent=round(100 * float(mean(all_rows, "binary_refusal_label")), 2) if all_rows else "",
                       mean_completeness=mean(all_rows, "completeness_score"))
        if dimension:
            summary = {dimension: group, **summary}
        summaries.append(summary)
    return summaries, matched


def load_providers(results_path: Path, results: list[dict]) -> dict | None:
    path = results_path.parent / "generated_responses.csv.provenance.jsonl"
    if not path.exists():
        return None
    hashes = {(r["prompt_id"], r["model"]): hashlib.sha256(r["response"].encode()).hexdigest() for r in results}
    providers = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.endswith("\n"):
                continue  # An append may still be in progress.
            record = json.loads(line)
            key = (record["prompt_id"], record["model"])
            if hashes.get(key) == record["response_sha256"]:
                providers[key] = record["provider"]
    return providers


def paired_interval(matched: list[dict], first: str, second: str, draws: int = 2000) -> tuple:
    cells = defaultdict(dict)
    for row in matched:
        cells[(row["base_prompt_id"], row["language"], row["model"])][row["strategy"]] = float(row[SEMANTIC_SCORE_FIELD])
    clusters = defaultdict(list)
    for (base, _, _), scores in cells.items():
        clusters[base].append(scores[first] - scores[second])
    blocks = [(sum(values), len(values)) for values in clusters.values()]
    if len(blocks) < 2:
        return None, None, len(blocks)
    rng = random.Random(20261030)
    samples = []
    for _ in range(draws):
        selected = rng.choices(blocks, k=len(blocks))
        samples.append(sum(s for s, _ in selected) / sum(n for _, n in selected))
    samples.sort()
    return round(samples[int(draws * 0.025)], 3), round(samples[int(draws * 0.975) - 1], 3), len(blocks)


def write_table(path: Path, rows: list[dict], dimension: str | None = None) -> None:
    fields = ([dimension] if dimension else []) + SUMMARY_FIELDS
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def evaluate_unwrapped(input_path: Path, results_path: Path, output_dir: Path) -> dict:
    """Report original-prompt coverage without inventing a strategy condition."""
    prompts = load_prompts(input_path)
    with input_path.open(encoding='utf-8-sig', newline='') as handle:
        source = list(csv.DictReader(handle))
    if not source or not all(r.get('variant_id') and r.get('language') for r in source):
        raise ValueError('Original-prompt evaluation needs variant_id and language')
    index = {r['variant_id']: r for r in source}
    results = list(load_results(results_path, prompts, True).values())
    raw_path = results_path.parent / 'generated_responses.csv'
    raw = list(load_results(raw_path, prompts, True).values()) if raw_path.exists() else results
    generated_count = sum(generated(r) for r in raw)
    scored = [r for r in results if r['status'] in SCORED_STATUSES]
    reviewed = [r for r in results if r.get(SEMANTIC_SCORE_FIELD, '') != '']
    expected = len(prompts) * len(MODELS)
    metrics = dict(input_rows=len(prompts), expected_responses=expected,
                   generated_responses=generated_count, generation_complete=generated_count == expected,
                   scored_responses=len(scored), collection_complete=len(scored) == expected,
                   saved_responses=len(results), missing_responses=expected - generated_count,
                   semantic_reviewed_responses=len(reviewed), semantic_review_complete=len(reviewed) == expected,
                   observed_leaders=[], ranking=[], comparison_type='original_prompts_no_strategy_comparison',
                   statuses=dict(Counter(r['status'] for r in results)))
    output_dir.mkdir(parents=True, exist_ok=True)
    for dimension in ('model', 'language'):
        groups = [m[0] for m in MODELS] if dimension == 'model' else sorted({r['language'] for r in source})
        table = []
        for group in groups:
            def belongs(r):
                return r['model'] == group if dimension == 'model' else index[r['prompt_id']]['language'] == group
            total = len(prompts) if dimension == 'model' else sum(r['language'] == group for r in source) * len(MODELS)
            labels = [r for r in scored if belongs(r)]
            direct = [r for r in reviewed if belongs(r)]
            table.append({dimension: group, 'expected': total,
                          'generated': sum(generated(r) and belongs(r) for r in raw), 'api_scored': len(labels),
                          'semantic_reviewed': len(direct),
                          'refusal_percent': round(100 * float(mean(labels, 'binary_refusal_label')), 2) if labels else '',
                          'mean_completeness': mean(labels, 'completeness_score'),
                          'mean_semantic_helpfulness': mean(direct, SEMANTIC_SCORE_FIELD)})
        with (output_dir / f'{dimension}_summary.csv').open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(table[0]))
            writer.writeheader(); writer.writerows(table)
    (output_dir / 'evaluation_summary.json').write_text(json.dumps(metrics, indent=2) + '\n')
    (output_dir / 'evaluation_report.md').write_text(
        '# Original multilingual dataset evaluation\n\n'
        f'Generated {generated_count}/{expected}; API-scored {len(scored)}/{expected}; '
        f'direct semantic-reviewed {len(reviewed)}/{expected}.\n\n'
        'This input has no strategy column; no strategy winner is computed. '
        'Model and language tables show coverage and available labels. Missing labels are blank.\n\n'
        'For a mixed-safety run, completeness means safe response quality: appropriate '
        'refusal can be complete, and unsafe assistance is not rewarded. Refusal rate '
        'alone does not establish safety. Labels are provisional and require review. '
        'Input translations retain their source review statuses.\n', encoding='utf-8')
    return metrics


def evaluate(input_path: Path, results_path: Path, output_dir: Path) -> dict:
    with input_path.open(encoding='utf-8-sig', newline='') as handle:
        headers = csv.DictReader(handle).fieldnames or []
    if 'strategy' not in headers:
        return evaluate_unwrapped(input_path, results_path, output_dir)
    prompts, index = read_input(input_path)
    results = list(load_results(results_path, prompts, resume=True).values())
    providers = load_providers(results_path, results)
    summaries, matched = summarize(index, results, providers=providers)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_table(output_dir / "strategy_summary.csv", summaries)
    for dimension in ("model", "language"):
        table, _ = summarize(index, results, dimension, providers=providers)
        write_table(output_dir / f"strategy_by_{dimension}.csv", table, dimension)
    ranked = sorted((s for s in summaries if s["matched_reviewed"]),
                    key=lambda s: (-float(s["matched_mean_semantic_score"]), s["strategy"]))
    expected = len(prompts) * len(MODELS)
    generation_path = results_path.parent / "generated_responses.csv"
    generations = list(load_results(generation_path, prompts, resume=True).values()) if generation_path.exists() else results
    generated_count = sum(generated(r) for r in generations)
    scored = sum(r["status"] in SCORED_STATUSES for r in results)
    complete = scored == expected
    reviewed_count = sum(r.get(SEMANTIC_SCORE_FIELD, "") != "" for r in results)
    metrics = {
        "input_rows": len(prompts), "expected_responses": expected,
        "generated_responses": generated_count, "generation_complete": generated_count == expected,
        "saved_responses": len(results), "scored_responses": scored,
        "missing_responses": expected - len(results),
        "statuses": dict(Counter(r["status"] for r in results)),
        "semantic_reviewed_responses": reviewed_count,
        "semantic_review_complete": reviewed_count == expected,
        "matched_observations_per_strategy": ranked[0]["matched_reviewed"] if ranked else 0,
        "same_provider_matching": providers is not None,
        "collection_complete": complete, "ranking": ranked,
        "observed_leaders": [], "paired_difference_ci95": None,
        "ranking_metric": SEMANTIC_SCORE_FIELD,
        "label_source": "direct assistant semantic review for ranking; provisional GPT-OSS refusal/completeness labels",
    }
    lines = ["# Strategy evaluation", "", f"Generated **{generated_count:,} / {expected:,}** responses; scored **{scored:,} / {expected:,}**.",
             f"Saved responses: {len(results):,}. Missing responses: {expected - len(results):,}.",
             f"Direct semantic reviews: **{reviewed_count:,} / {expected:,}**. Ranking metric: `semantic_helpfulness_score` (0–100).", ""]
    if ranked:
        top = ranked[0]["matched_mean_semantic_score"]
        leaders = [s["strategy"] for s in ranked if s["matched_mean_semantic_score"] == top]
        metrics["observed_leaders"] = leaders
        qualifier = "Observed leader" if reviewed_count == expected else "Provisional observed leader (incomplete semantic review)"
        lines += [f"**{qualifier}: {', '.join(leaders)} — {top:.2f}/100.**", "",
                  "| Strategy | Matched semantic mean /100 | Reviewed / expected | Refusal % |",
                  "|---|---:|---:|---:|"]
        for row in ranked:
            refusal = f"{row['refusal_percent']:.2f}" if row['refusal_percent'] != "" else "unavailable"
            lines.append(f"| {row['strategy']} | {row['matched_mean_semantic_score']:.2f} | {row['semantic_reviewed']}/{row['expected']} | {refusal} |")
        lines += ["", f"Ranking uses {ranked[0]['matched_reviewed']:,} matched question/language/model observations per strategy.",
                  "Component metrics in the CSV summaries use all available scored observations; coverage is shown separately."]
        if len(ranked) > 1:
            low, high, clusters = paired_interval(matched, ranked[0]["strategy"], ranked[1]["strategy"])
            metrics["paired_difference_ci95"] = {"first": ranked[0]["strategy"], "second": ranked[1]["strategy"],
                                                  "low": low, "high": high, "base_prompt_clusters": clusters}
            if low is not None:
                lines += ["", f"Exploratory 95% cluster-bootstrap interval for the top-two score difference: [{low:.3f}, {high:.3f}] points, resampling {clusters} base questions (2,000 draws).",
                          "The top two were selected from these data; this interval is descriptive, without multiple-comparison correction."]
    else:
        lines += ["**No strategy winner can be determined: no fully matched semantic reviews are available.**"]
    review = Counter(r.get("review_status", "unspecified") for r in index.values())
    metrics["input_review_statuses"] = dict(review)
    lines += ["", "## Interpretation", "",
              "Higher semantic helpfulness means better fulfillment of the actual benign prompt, considering relevance, correctness, coverage, clarity and language. Scores are holistic direct judgments, not calculated from API labels. Empty responses are excluded, not treated as refusals or zero scores. Truncated responses are reviewed on their visible content.",
              "Only question/language/model cells directly reviewed for every strategy enter ranking. API scoring status does not determine eligibility for semantic ranking. Refusal and completeness summaries use the separate available API labels. Final CSV prompt_id corresponds to input variant_id; strategy and language are joined from the unchanged input.",
              "When provenance is available, all strategies in a matched cell must also use the same target provider. Mixed-provider or missing-provenance cells do not enter the ranking, so a provider switch cannot be mistaken for a strategy effect.",
              "Semantic scores are single-assistant annotations and require independent validation. Refusal/completeness are provisional automatic GPT-OSS labels, including self-evaluation. New responses remain without semantic scores until directly reviewed.",
              "Generation and scoring are independent processes. Raw answers are in generated_responses.csv; scoring writes final_output.csv and never edits raw generations. Provider provenance is kept in CSV sidecars; existing Groq responses/labels are preserved alongside later provider routes.",
              "Input review statuses: " + ", ".join(f"{k}={v}" for k, v in sorted(review.items())) + ". Translation and wrapper differences can affect comparisons.",
              "There is no unwrapped baseline in this run, so this comparison ranks the four strategies without estimating improvement over unwrapped prompts.", ""]
    (output_dir / "strategy_report.md").write_text("\n".join(lines), encoding="utf-8")
    (output_dir / "evaluation_summary.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.input, args.results, args.output_dir)
    print(f"Scored {result['scored_responses']}/{result['expected_responses']}; leaders: {result['observed_leaders'] or 'not available'}")


if __name__ == "__main__":
    main()
