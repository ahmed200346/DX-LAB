# Clinical Annotation Protocol — AI Drug Safety

Purpose
-------
This document defines the protocol for clinician annotation of a gold-standard
dataset used to evaluate the AI Drug Safety agent. The goal is to produce
high-quality, reproducible annotations for interaction detection, adverse
outcomes and causality (Naranjo-like scoring) to support clinical evaluation.

Scope
-----
- Single-drug evaluations: annotate known/suspected interactions and adverse
  events for a given indexed drug.
- Prefer authoritative sources (product labels, openFDA, guideline statements)
  for evidence extraction during annotation.

Annotator Requirements
----------------------
- Clinical background (pharmacist, clinician) with experience in drug safety.
- Familiarity with common drug interaction categories (major/moderate/minor) and
  Naranjo ADR causality principles.
- Two independent annotators per case; adjudication by a senior reviewer if
  disagreement persists.

Data Fields and Definitions
---------------------------
- `id`: Unique identifier for the case/row.
- `drug`: Free-text drug name to be evaluated (input to the system).
- `rxcui`: Optional normalized RxNorm RXCUI for the indexed drug.
- `major_interaction` (boolean): True if there exists at least one clinically
  important (major/serious) interaction for this drug in the context of the
  presented patient (or generally if patient unspecified).
- `major_interaction_targets` (list): Semicolon-separated list of interacting
  drugs considered major (e.g., `warfarin;dabigatran`).
- `naranjo_score` (integer, 0-13): Annotator-assigned Naranjo causality score
  when an ADR/outcome is associated with the drug. Use the standard Naranjo
  questionnaire and record the resulting integer.
- `adverse_outcome` (boolean): True if there is at least one documented severe
  ADR or outcome (hospitalization, death, life-threatening event) linked to the
  drug in the reference evidence.
- `annotator_id`, `annotator_date`, `notes`: Administrative and reasoning notes.

Annotation Process
------------------
1. Read the drug name and any provided patient context.
2. Search authoritative sources: product label (DailyMed/openFDA), RxNorm,
   clinical guidelines, and peer-reviewed literature only as needed.
3. For interactions, record only clinically meaningful interactions (those that
   would alter prescribing or require monitoring). Use `major` for life- or
   organ-threatening interactions (e.g., increased bleeding risk with
   anticoagulants).
4. For Naranjo scoring, apply the standard 10-question instrument and record
   the integer total. If no ADR is being adjudicated, leave blank.
5. Save the source citations (URL or document title) in `notes` or a separate
   evidence file.

Adjudication and Quality Control
--------------------------------
- Compute inter-rater agreement (Cohen's kappa) for key binary labels
  (`major_interaction`, `adverse_outcome`). Aim for kappa ≥ 0.8.
- Disagreements should be adjudicated by a senior clinician with ties broken
  by consensus and documented rationale.

Example Row
-----------
`1,aspirin,1191,True,warfarin,5,False,clin1,Verified in openFDA label; increased bleeding with warfarin`

Notes
-----
This protocol prioritizes clinical significance and reproducibility. Store
annotations in CSV format (UTF-8) and retain raw evidence links for auditing.
