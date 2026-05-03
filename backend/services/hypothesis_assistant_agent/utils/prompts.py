"""
utils/prompts.py (biomedically accurate – all prompts present)
"""

from langchain_core.prompts.prompt import PromptTemplate


PAPER_ANALYSIS_PROMPT = PromptTemplate(
    input_variables=["abstracts"],
    template="""You are a biomedical NLP system. Extract structured knowledge from each abstract below.

For each abstract, extract:
- drugs: brand names AND generic names (e.g. "sotorasib", "AMG 510")
- genes: gene symbols only (e.g. "KRAS", "EGFR", "TP53")
- pathways: biological pathways mentioned (e.g. "MAPK", "PI3K/AKT")
- outcome: the main experimental result (one specific sentence)
- conclusion: what the authors conclude about the field (one sentence)
- study_type: one of [in_vitro, in_vivo, clinical_trial, review, case_report]

Abstracts:
{abstracts}

Return ONLY a valid JSON list. Each object must have these exact keys:
"paper_id", "entities", "outcome", "conclusion", "study_type"

Where "entities" has keys: "drugs", "genes", "pathways" (each a list of strings).
No markdown, no explanation. Valid JSON only."""
)


GAP_DETECTION_PROMPT = PromptTemplate(
    input_variables=["summaries", "query", "study_types", "causal_paths"],
    template="""You are a critical research analyst identifying SPECIFIC mechanistic gaps in scientific literature.
You may ONLY use the information provided in the summaries and causal paths below.
Do NOT invent new molecules, interactions, or pathways. If a gap cannot be precisely stated using the given data, skip it.

Research topic: {query}
Study types found: {study_types}
Causal paths extracted (cross-paper chains): {causal_paths}

Extracted findings:
{summaries}

Identify exactly 5 research gaps that are **mechanistic** and **directly testable**.
REJECT gaps of the form:
- "more studies are needed"
- "clinical trials are lacking"
- "larger cohorts required"

REQUIRE gaps of the form:
- "the mechanism by which X causes Y is unknown"
- "no study has tested whether A interacts with B under condition C"
- "it is unclear whether [specific molecule] acts upstream or downstream of [pathway]"
- "the causal path A→B→C is missing experimental validation of the B intermediate"

Use the causal paths to identify missing edges or uncharacterized intermediates.
Format each gap EXACTLY as:
GAP [1]: <what is missing AND why it matters>
GAP [2]: ...

Return ONLY the 5 gaps, no preamble."""
)


CONFLICT_DETECTION_PROMPT = PromptTemplate(
    input_variables=["findings", "triples"],
    template="""You are a scientific fact-checker identifying contradictions in research literature.
You MUST base every claim on the findings or triples provided. Do NOT invent or assume contradictions.

Findings:
{findings}

Extracted causal triples (subject-relation-object, with paper IDs):
{triples}

Find REAL contradictions. There are two types:

TYPE 1 — EXPLICIT CONTRADICTION:
Papers that study the SAME thing but report OPPOSITE results.

TYPE 2 — IMPLICIT TENSION:
Papers that study the same phenomenon but invoke incompatible primary mechanisms.
Examples:
- genetic vs non-genetic resistance attribution
- cell-autonomous vs microenvironment-driven effects
- in_vitro mechanism contradicted by clinical observation

For each genuine conflict (only if supported by the data):
CONFLICT [N] [SEVERITY: low|medium|high] [CONTRADICTION|TENSION]:
- Claim A (paper X): <finding/mechanism>
- Claim B (paper Y): <conflicting finding/mechanism>
- Why it matters: <implication>

If NO genuine conflicts: write exactly "NO CONFLICTS DETECTED"

Return ONLY the conflicts or the no-conflicts message."""
)


HYPOTHESIS_GENERATION_PROMPT = PromptTemplate(
    input_variables=["query", "extracted_knowledge", "gaps", "conflicts", "causal_paths", "known_findings", "num_hypotheses"],
    template="""You are a world-class research strategist generating novel, testable scientific hypotheses.
ABSOLUTE RULE: Every molecular interaction you propose must either be:
  - explicitly stated in the provided extracted knowledge, OR
  - directly derived from a causal path present in the causal_paths.
Do NOT invent interactions or pathways that are not in the data. If you propose a combination, state which paper supports each component.
If you cannot generate a hypothesis with the given evidence, output exactly "NO HYPOTHESES POSSIBLE" and nothing else.

Research topic: {query}

--- EXTRACTED KNOWLEDGE ---
{extracted_knowledge}

--- RESEARCH GAPS ---
{gaps}

--- LITERATURE CONFLICTS ---
{conflicts}

--- CROSS-PAPER CAUSAL PATHS ---
{causal_paths}

--- KNOWN FINDINGS (do NOT reproduce) ---
{known_findings}

---

Generate exactly {num_hypotheses} research hypotheses. Each hypothesis MUST:
1. Address a SPECIFIC gap OR resolve a SPECIFIC conflict
2. Fuse evidence from ≥2 different papers (cite paper IDs, e.g. [2,5])
3. Name only molecules, genes, drugs, or pathways that appear in the provided knowledge
4. Be testable with currently available methods
5. Represent a genuine advance beyond known findings

Format EACH hypothesis EXACTLY as follows (replace N with the hypothesis number):

HYPOTHESIS [N]:
Statement: <1-2 sentence mechanistic hypothesis, using only data from papers>
Addresses: <"GAP [N]" or "CONFLICT [N]">
Rationale: <2-3 sentences, citing specific paper IDs and explaining how they combine>
Experiment: <specific experimental design>
Impact Score: <integer 1-10>
Novelty Score: <integer 1-10>
Theme: <Drug Resistance | Biomarker | Combination Therapy | Mechanism | Pathway Crosstalk | Immunology>

If you lack evidence, return "NO HYPOTHESES POSSIBLE". Do not guess."""
)


HYPOTHESIS_SCORING_PROMPT = PromptTemplate(
    input_variables=["hypotheses", "query"],
    template="""You are a research grant reviewer scoring hypotheses.

Research area: {query}

Hypotheses:
{hypotheses}

For each hypothesis:
SCORE [n]:
Feasibility: <1-10>
Clinical Relevance: <1-10>
Scientific Novelty: <1-10>
Risk Level: <low|medium|high>
Recommended Next Step: <first experiment>
Funding Priority: <top|medium|low>

Return ONLY the scores."""
)


RELEVANCE_FILTER_PROMPT = PromptTemplate(
    input_variables=["abstract", "query"],
    template="""Is this abstract directly relevant to: "{query}"?

Abstract:
{abstract}

Reply ONLY: RELEVANT or NOT_RELEVANT"""
)


THEME_CLUSTERING_PROMPT = PromptTemplate(
    input_variables=["hypotheses"],
    template="""Group these hypotheses into 2-4 thematic clusters.

Hypotheses:
{hypotheses}

Format:
THEME [n]: <Theme name>
Hypotheses: <comma-separated indices>
Description: <1 sentence>

Return ONLY the themes."""
)


RELATIONSHIP_EXTRACTION_PROMPT = PromptTemplate(
    input_variables=["abstract", "paper_id"],
    template="""Extract ONLY explicitly stated causal triples from the abstract below.
Do NOT infer relations; only extract if the sentence clearly states a direct interaction or causation between specific molecules.
Paper ID: {paper_id}
Abstract: {abstract}

Use only these relations:
activates, inhibits, stabilizes, degrades, promotes, reduces, bypasses,
induces, regulates, phosphorylates, upregulates, downregulates,
interacts_with, is_upstream_of, is_downstream_of.

Return ONLY a JSON list of objects with keys: "subject", "relation", "object", "context", "paper_id", "confidence".
Confidence: "high" (explicitly stated), "medium" (stated but indirect), or "low" (weakly implied). 
If no direct causal relations exist, return an empty list []."""
)


NOVELTY_CHECK_PROMPT = PromptTemplate(
    input_variables=["hypothesis_statement", "papers"],
    template="""Is the following hypothesis already explicitly stated in the literature provided?
Only use the abstracts given; do not infer or guess.

Hypothesis statement: {hypothesis_statement}

Literature abstracts (with paper IDs):
{papers}

Answer in JSON:
{{
  "already_known": boolean,
  "confidence": number (0.0-1.0),
  "closest_paper_id": string or null,
  "verbatim_match": boolean,
  "reason": string
}}
Return ONLY the JSON."""
)


SUMMARY_REPORT_PROMPT = PromptTemplate(
    input_variables=["query", "hypotheses", "gaps", "conflicts", "causal_paths"],
    template="""You are a scientific summarizer. Produce a 1‑page structured summary of a hypothesis generation session.

Topic: {query}
Hypotheses: {hypotheses}
Gaps: {gaps}
Conflicts: {conflicts}
Causal paths: {causal_paths}

Return JSON:
{{
  "executive_summary": "3-sentence plain English summary",
  "strongest_hypothesis": {{...}},
  "most_critical_gap": "...",
  "recommended_first_experiment": "...",
  "confidence_assessment": "low|medium|high"
}}
Return ONLY the JSON."""
)