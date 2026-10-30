# Research references for the multilingual safety study

This is a literature catalog, not a prompt dataset. No attack prompts, evasion templates, or model responses were imported. The 60-row research source datasets are unchanged by this addition.

## A StrongREJECT for Empty Jailbreaks

- Authors: Alexandra Souly et al.
- Year: 2024
- Paper: https://arxiv.org/abs/2402.10260
- NeurIPS proceedings PDF: https://proceedings.neurips.cc/paper_files/paper/2024/file/e2e06adf560b0706d3b1ddfca9f29756-Paper-Datasets_and_Benchmarks_Track.pdf
- Contribution: evaluates how much useful information a response supplies for a prohibited request, rather than treating any non-refusal as successful harmful compliance.
- Relevance: supports graded response evaluation for the existing harmful controls. Our proposed 0–4 compliance rubric is a custom adaptation, not the paper's official scoring scale. Validate it against bilingual human judgments before drawing conclusions.

## HarmBench: A Standardized Evaluation Framework for Automated Red Teaming and Robust Refusal

- Authors: Mantas Mazeika et al.
- Year: 2024
- Paper: https://arxiv.org/abs/2402.04249
- Contribution: provides a standardized framework for comparing red-teaming methods and model refusal robustness.
- Relevance: informs consistent evaluation conditions, separation of target behaviors from input variants, and structured recording of response outcomes. No prompts or attack implementations were copied into this project.

## Code-Switching Red-Teaming: LLM Evaluation for Safety and Multilingual Understanding

- Authors: Haneul Yoo, Yongjin Yang, and Hwaran Lee
- Venue: ACL 2025
- Paper: https://aclanthology.org/2025.acl-long.657/
- PDF: https://aclanthology.org/2025.acl-long.657.pdf
- Contribution: studies safety and multilingual comprehension under code-switching.
- Relevance: motivates recording comprehension and response-language quality alongside safety outcomes. Mixed-language conditions should be distinguished from monolingual translations in analysis.

## Relation to the current datasets

The current narrative dataset contains 40 expanded benign prompts and 20 unchanged direct harmful controls. These references provide methodological context, not evidence that the project's prompts or custom scores have already been validated. Literature review and dataset expansion are separate activities. No new prompt rows have been added here.

Use the same source prompt version for comparisons across languages. Review translations for meaning and risk equivalence. Record missing responses separately from refusals, and distinguish truncation from harmful compliance. Report model-provider configurations accurately: two providers serving GPT-OSS are not two independent model families.
