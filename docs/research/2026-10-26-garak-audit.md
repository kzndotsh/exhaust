# Audit: NVIDIA/garak

Source: [github.com/NVIDIA/garak](https://github.com/NVIDIA/garak). An actively maintained (pushed within the week), 9,700-plus-star LLM vulnerability scanner: it probes a model directly (prompt injection, jailbreaks, data leakage, hallucination, unsafe content) rather than probing a live network Target, a genuinely different domain from every web/infra-pentest tool audited so far. Read directly, not via subagent fan-out, after a shallow clone and a targeted read of its core abstractions (`harnesses/base.py`, `detectors/base.py`, `attempt.py`, `evaluators/base.py`, `analyze/bootstrap_ci.py`, `detectors/packagehallucination.py`).

## An independent confirmation of our own core vocabulary

Garak's own architecture is named, unprompted, in exactly our terms: a **Harness** coordinates running **probes** against a **generator** (the model under test), scores the output with **detectors**, and produces a result through an **evaluator**. Its own module docstring: "a harness coordinates running probes on a generator, running detectors on the outputs, and evaluating the results." This is the single strongest outside confirmation yet that "Harness" is the right word for exhaust's orchestrating loop, independently arrived at by a major, NVIDIA-maintained project in an adjacent domain, not borrowed from any tool audited so far. No ADR change needed; recorded here because it is a genuine, welcome outside validation of a term we settled early by our own judgment.

## Adopted: an independent-ground-truth differential, as a concrete fifth Oracle mechanism

Folded into [ADR 0008](../adr/0008-confirmed-requires-a-host-run-oracle.md). Garak's package-hallucination detector extracts an imported package name from a model's generated code and checks it against a dated, independently sourced snapshot of what packages genuinely existed on PyPI at that point, rather than trusting anything the model says about its own output. This is a clean, concrete instance of a pattern none of the four previously catalogued Oracle mechanisms quite captured: checking an extracted claim against a real, versioned, externally sourced corpus the thing being tested has no influence over. Directly applicable to exhaust: a claimed CVE ID, package version, or known-vulnerable component is a claim to check against a real advisory feed or registry, not evidence because an agent or a Target's own banner states it.

## Adopted: correct the headline eval number for the judge's own error rate

Folded into [ADR 0014](../adr/0014-eval-uses-blind-held-out-ground-truth.md). Garak's evaluator computes attack-success-rate with a non-parametric bootstrap confidence interval, corrected using each detector's own known sensitivity and specificity rather than treating the detector as a perfectly accurate judge and reporting the raw hit count. This is a level of statistical discipline no other audited tool carries. Exhaust's own eval reporting should do the same: report a confidence interval, not a bare percentage, and where the Oracle or scoring detector has a known error rate, correct the headline number with it rather than footnoting it.

## Also used to update ADR 0014 directly: the xbow saturation finding

While amending ADR 0014 for the bootstrap-CI lesson, the already-gathered xbow-engineering/validation-benchmarks finding (its own README states the benchmark is now saturated and its vulnerabilities trained into current models) was folded in at the same time, since both lessons concern the same ADR and the earlier xbow audit file had only confirmed, not amended, it. The lesson: a held-out fixture set is not held out permanently; it needs active rotation against exactly this kind of after-the-fact contamination, not a one-time construction.

## Noted, not adopted: why garak's detectors don't need an Oracle the way exhaust's do

Worth being precise about, as with the oss-crs scope-authorization note. Garak's detectors mostly classify model output text directly (does this response contain a leaked system prompt, a slur, a hallucinated package) rather than confirming a claimed effect on a separate live system. For garak's domain, the model's output *is* the artifact under test, so inspecting it directly is first-party evidence, not a self-report needing independent replay. Exhaust's problem is harder specifically because a Finding claims an effect on a Target distinct from the agent's own transcript, which is exactly what an agent under adversarial pressure (or simply mistaken) can misreport. Not evidence against ADR 0008; a reminder that the Oracle requirement exists because of what kind of claim exhaust's Findings make, not because self-classification is inherently untrustworthy.

## What this settled for exhaust

- [ADR 0008](../adr/0008-confirmed-requires-a-host-run-oracle.md): a fifth concrete Oracle mechanism added, the independent-ground-truth differential.
- [ADR 0014](../adr/0014-eval-uses-blind-held-out-ground-truth.md): eval results should report a bootstrap confidence interval corrected for the judging mechanism's own known error rate, not a bare point estimate; also folded in the xbow saturation finding as a concrete instance of "rotate held-out fixtures against contamination."
- No ADR change, but a welcome independent confirmation that "Harness" is the right word for the orchestrating loop: a major, unrelated project in an adjacent domain converged on the exact same term on its own.
