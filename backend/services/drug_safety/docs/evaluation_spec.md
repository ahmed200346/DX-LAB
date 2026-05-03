# Evaluation Specification — AI Drug Safety

Purpose
-------
Define the primary and secondary endpoints, metrics, and analysis plan for a
clinical evaluation of the AI Drug Safety agent. This specification is intended
to be used together with the annotation protocol and a clinician-annotated
gold-standard dataset.

Primary Objectives
------------------
- Measure sensitivity (recall) for detection of clinically important (major)
  drug–drug interactions. Priority is to minimize false negatives for major
  interactions.
- Measure precision (positive predictive value) for the flagged major
  interactions.

Secondary Objectives
--------------------
- Score discrimination and calibration of the agent's numeric risk score
  (AUROC, AUPRC, Brier score, calibration plots).
- Agreement between model Naranjo-like scores and clinician Naranjo scores
  (Spearman correlation, mean absolute error).
- Normalization coverage (RXCUI mapping rate) and evidence support rate.

Metrics
-------
- Sensitivity = TP / (TP + FN) for `major_interaction` detection.
- Precision = TP / (TP + FP) for `major_interaction` detection.
- F1-score for `major_interaction` detection.
- AUROC / AUPRC for risk score where outcome labels exist.
- Calibration metrics: Brier score, calibration-in-the-large, calibration slope.
- Spearman's rho between model and clinician Naranjo scores.
- RXCUI mapping rate = (# records mapped to RXCUI) / total.
- Evidence support rate = (# claims with ≥1 authoritative source) / total.

Analysis Plan
-------------
1. Pre-specify the primary endpoint (major interaction sensitivity) and
   analysis threshold.
2. Use cross-validation or internal/external split: use internal (development)
   set for tuning, and external held-out validation for reporting final
   performance.
3. Report point estimates with 95% confidence intervals (bootstrap for small
   datasets if necessary).
4. Present stratified performance by age group, polypharmacy (>5 drugs), and
   comorbidity count.

Sample Size & Power (Guidance)
------------------------------
- Aim for at least 200–500 annotated cases for robust estimates of sensitivity
  and precision when the prevalence of events is moderate. For low-prevalence
  major interactions, oversample positive cases or use enriched cohorts.

Reporting
---------
- Include confusion matrices, ROC and PR curves, calibration plots, DCA net
  benefit plots (if outcomes available), and exemplar failure cases with
  evidence citations.
- Provide the annotation protocol, raw annotations (redacted if needed), and
  analysis scripts to enable reproducibility.
