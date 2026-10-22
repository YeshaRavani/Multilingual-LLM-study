# Preliminary language-only results: GPT-OSS 20B

Run date: 22 October 2026

Model: `openai/gpt-oss-20b`, served through Groq's free endpoint. The NVIDIA
endpoint is integrated in the code but was not run because `NVIDIA_API_KEY` is
not yet configured.

## Design

- 6 canonical prompts: 4 benign-but-safety-adjacent and 2 clearly harmful.
- 7 conditions: Standard English, Hindi, Gujarati, Punjabi, Bengali, Marathi,
  and Kannada.
- 42 successful responses in total.
- Temperature 0, low reasoning effort, and a 1,200-token output ceiling.
- Indian English, Informal English, and Hinglish were intentionally excluded.

## Binary safety outcomes

| Condition | Benign answered | False-refusal rate | Harmful refused | Harmful-compliance rate |
|---|---:|---:|---:|---:|
| Standard English | 4/4 | 0% | 2/2 | 0% |
| Hindi | 4/4 | 0% | 2/2 | 0% |
| Gujarati | 4/4 | 0% | 2/2 | 0% |
| Punjabi | 4/4 | 0% | 2/2 | 0% |
| Bengali | 4/4 | 0% | 2/2 | 0% |
| Marathi | 4/4 | 0% | 2/2 | 0% |
| Kannada | 4/4 | 0% | 2/2 | 0% |

This pilot therefore does **not** show a language gap in the binary decision to
answer or refuse for this model. That null finding is not evidence that the
broader problem is absent: the sample contains only six prompts and one model.

## Signals worth investigating

- Benign-response truncation varied from 25% in Hindi to 75% in Bengali under
  the same output-token ceiling. Standard English was 50%. This may reflect
  tokenization, verbosity, or translation effects and needs a larger sample.
- A spot check found possible meaning/quality problems rather than refusal
  differences. In the chemistry response, Bengali and Kannada outputs described
  household bleach using sodium hydroxide terminology, while the English answer
  correctly identified sodium hypochlorite. Bilingual review is required before
  this is treated as a model error rather than a translation artifact.
- All harmful prompts received the same short English refusal even when the
  request was written in another language. A future outcome should therefore
  measure language matching and helpful safe redirection, not only refusal.

## Important limitations

- The six translations were machine generated and have not passed bilingual
  equivalence review.
- Four benign and two harmful prompts are too few for statistical inference.
- Refusal detection is a simple phrase-based rule for this pilot.
- Some benign answers reached the 1,200-token ceiling, so detailed quality
  comparisons must account for truncation.
- The run should be replicated across providers/models and repeated seeds after
  translation validation.
