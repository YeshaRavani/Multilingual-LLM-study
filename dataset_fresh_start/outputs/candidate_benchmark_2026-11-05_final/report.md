# Free candidate endpoint benchmark

Three current NVIDIA-hosted free prototype endpoints were tested using the same unchanged MSF-001 persona-builder prompt in eight language variants. Temperature 0, maximum 1,000 output tokens; one concurrent request per model. Bolt thinking was explicitly disabled using the documented setting; other models used provider defaults. Qwen and GPT-OSS background collection remained active.

| Model | Completed / attempted | Median end-to-end (completed only) | Median first content | Outcome |
|---|---:|---:|---:|---|
| nvidia/nemotron-3.5-bolt-e4b | 8/8 | 13.06s | 0.34s | All eight languages finished normally |
| deepseek-ai/deepseek-v4.1-flash | 0/2 | unavailable | none | Both attempts timed out at about 45s; other six languages not tested |
| minimaxai/minimax-m3.1-flash | 0/2 | unavailable | none | Both attempts timed out at about 45s; other six languages not tested |

## Recommendation

Nemotron 3.5 Bolt E4B is the only successful deadline-oriented candidate in this pilot. It returned a five-sign phishing-awareness answer and a reporting checklist in every requested language. Direct spot checks found useful content but also overly broad claims about grammatical errors and occasional wrong-script words in Kannada. This is an endpoint speed and basic usability screen, not a validated quality score or a broad safety evaluation.

The eight full responses took 4.26–14.87 seconds each. Straight-line extrapolation from the sample mean/median suggests roughly 4–5 hours for 1,280 generations on one worker if this speed holds. This excludes scoring and review. Provider quotas, outages, different response lengths and load can make the full run substantially slower; this is not a completion guarantee.

No study model was replaced, no background collector was stopped, and no paid route or account upgrade was enabled. Benchmark outputs remain separate from study results. If selected later, the replacement needs its own correctly labelled 1,280 responses; saved Gemma rows cannot be relabelled.

## Free endpoint verification

- NVIDIA describes eligible developer access as free for prototyping, with model/account-specific limits: https://docs.api.nvidia.com/nim/docs/product
- Bolt page explicitly lists a free API endpoint: https://build.nvidia.com/nvidia/nemotron-3.5-bolt-e4b
- DeepSeek page explicitly lists a free API endpoint: https://build.nvidia.com/deepseek-ai/deepseek-v4.1-flash
- MiniMax page explicitly lists a free API endpoint: https://build.nvidia.com/minimaxai/minimax-m3.1-flash

These are free hosted prototype services, not unrestricted production capacity. The benchmark used only https://integrate.api.nvidia.com/v1/chat/completions. No partner-hosted paid inference was used.

## Availability screening

Mistral NeMo 12B and Phi-3.5 MoE appeared in the authenticated catalog but returned HTTP 404 for both initial tests and were excluded. Their evidence remains in the initial candidate_benchmark_2026-11-05 directory. Catalog listing alone did not establish a working endpoint.

## Individual timings

| Model | Language | Seconds | First content seconds | Status |
|---|---|---:|---:|---|
| nvidia/nemotron-3.5-bolt-e4b | English | 4.256 | 0.297 | success |
| nvidia/nemotron-3.5-bolt-e4b | Hindi | 12.346 | 0.293 | success |
| nvidia/nemotron-3.5-bolt-e4b | Gujarati | 14.612 | 0.343 | success |
| minimaxai/minimax-m3.1-flash | English | 45.076 | none | timeout |
| deepseek-ai/deepseek-v4.1-flash | English | 45.077 | none | timeout |
| nvidia/nemotron-3.5-bolt-e4b | Punjabi | 14.874 | 0.34 | success |
| nvidia/nemotron-3.5-bolt-e4b | Kannada | 13.775 | 0.339 | success |
| nvidia/nemotron-3.5-bolt-e4b | Tamil | 10.255 | 0.345 | success |
| nvidia/nemotron-3.5-bolt-e4b | Malayalam | 14.175 | 0.329 | success |
| minimaxai/minimax-m3.1-flash | Hindi | 45.083 | none | timeout |
| deepseek-ai/deepseek-v4.1-flash | Hindi | 45.089 | none | timeout |
| nvidia/nemotron-3.5-bolt-e4b | Marathi | 10.605 | 0.338 | success |
