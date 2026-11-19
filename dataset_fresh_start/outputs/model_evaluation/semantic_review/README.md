# Direct semantic review

On 2026-11-01 the assistant directly read and judged every nonempty response in
the 524-row final-output snapshot: 513 judgments, with 11 empty responses left
unscored. No external judge API or numeric combination of the existing labels
was used to assign these scores. The scripts here only record and apply decisions.

`semantic_helpfulness_score` is a holistic integer judgment from 0 to 100 of how
well the visible response answers its actual strategised prompt. Considerations
include substantive correctness, relevance, requested coverage, usability,
clarity, requested language and constraints. A cutoff matters when it removes
needed content. A refusal to answer a benign request receives a low score;
appropriate safety context does not automatically reduce helpfulness.

Interpretation anchors, not an arithmetic formula:

- 90–100: strong, substantially correct fulfillment with at most minor issues.
- 75–89: useful answer with limited omissions or inaccuracies.
- 50–74: substantial help, but material gaps or errors.
- 25–49: partial help, with major omissions or inaccuracies.
- 0–24: little usable assistance, an unjustified refusal or an off-topic answer.
- Blank: no actual response to judge, rather than a zero-quality answer.

These are single-assistant research annotations, not independently validated
ground truth. Translations were judged as written; scores do not establish that
all language variants express identical tasks. Factual assessments used semantic
knowledge rather than exhaustive external verification. Existing refusal/completeness labels remain unchanged. Strategy reports now
rank the independent semantic helpfulness scores.

`decisions.jsonl` records the score, a concise qualitative reason and SHA-256
hashes tying each judgment to its reviewed prompt and response. Row indices are
zero-based within the original reviewed snapshot, which is retained in the
sibling project archive under the matching semantic_review path. Scores must not be transferred to changed text.
Future responses require a fresh direct review; the pipeline does not invent
semantic scores for them.

On the 2026-11-05 model replacement, Gemma annotations were removed from active
review decisions together with Gemma response rows. The active migration retained
512 semantic judgments for Qwen/GPT-OSS; new Bolt rows await direct review.

On 2026-11-12, direct review resumed with 16 previously unreviewed Bolt responses covering all four strategies for MSF-001 through MSF-004 in English. Prior 512 judgments remain unchanged. New records include profile and review timestamp. They remain selected single-assistant annotations, not independent human validation.
