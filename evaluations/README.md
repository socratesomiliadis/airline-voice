# Judge regression and calibration evidence

`judge-calibration.json` has five policy explanation cases. The requester labelled the recorded
counterexample and explicitly reviewed and confirmed the four additional policy
judgments in this session. All five cases carry label provenance and
`human_review_required=false`. The recorded message is preserved
verbatim, with explicit fictional timestamps supplied as context.

`judge-calibration-result.json` records a live raw-judge invocation for each case,
including the exact judge instructions used. It bypasses deterministic score
enforcement so retries cannot hide a false passing score. The separate factual
checks are also retained. The raw judge agreed with all five human labels in this run. This small set does
not establish calibration for
naturalness, transaction consent, or difficult interactions, and model scores are
stochastic. Later judge instruction changes require another run for comparison.

Run from the repository root with configured model credentials:

```sh
uv run --all-packages python scripts/calibrate_judge.py \
  --output artifacts/judge-calibration.json
```

Labels use per-criterion passing decisions at the configured score threshold. Keep
label provenance and pending human reviews in any expanded set. Include both
correct and incorrect explanations rather than evaluating only known failures.
