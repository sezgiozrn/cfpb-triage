# Phase 2: LLM Classification Feasibility Eval

## Purpose

Before recommending AI-assisted triage in the BRD, this evaluates whether an
LLM can reliably classify complaint narratives against CFPB's own product
taxonomy — a feasibility check on one specific capability the future-state
process (docs/02_brd.md, Section 6) would depend on, not a general AI demo.

## Method

- **Model:** Claude Sonnet 4.6, via the Anthropic API
- **Sample:** 500 complaint narratives from `complaints_core`, stratified
  50-per-product across all 10 core categories (not proportional — see
  "Known limitation" below for why)
- **Task:** classify each narrative into exactly one of the 10 categories,
  given only the narrative text (no company, no other metadata)
- **Grader:** exact match against the CFPB-assigned official category
- **Reproducibility:** fixed random seed (20260709), sample and results
  saved in `evals/sample.csv` and `evals/results.csv`

## Known limitation: sample is not representative of all complaints

Narratives exist only where the consumer opted in to publish them, and
opt-in rates vary 25.3%–73.1% by product (docs/04_data_notes.md). This
sample describes *complaints with published narratives*, not the full
complaint population. A production triage system would see all complaints,
not just this subset — treat the numbers below as a feasibility signal, not
a deployment-ready accuracy estimate.

## Results

**Overall agreement: 399/500 (79.8%)**

This headline number is the least important result here — see below.

**Per-category agreement (the more useful breakdown):**

| Product | Agreement |
|---|---|
| Debt or credit management | 44.0% (22/50) |
| Payday loan, title loan, personal loan, or advance loan | 66.0% (33/50) |
| Money transfer, virtual currency, or money service | 78.0% (39/50) |
| Prepaid card | 78.0% (39/50) |
| Checking or savings account | 84.0% (42/50) |
| Credit card | 86.0% (43/50) |
| Vehicle loan or lease | 86.0% (43/50) |
| Mortgage | 90.0% (45/50) |
| Student loan | 92.0% (46/50) |
| Debt collection | 94.0% (47/50) |

Full confusion breakdown: `evals/confusion_summary.txt`

## The actual finding: low agreement in one category looks like a labeling problem, not a model problem

"Debt or credit management" is the clear outlier — 20+ points below the next
lowest category, and its most common disagreement (13 of 50) is the model
calling it "Debt collection" instead. Hand-inspecting four of those
disagreements:

1. *"I am getting a letter saying I have an account or a debt but I have no
   debt or made a purchase with this company."* — official label: Debt or
   credit management. Model: Debt collection. **This reads as a straightforward
   debt-collection dispute** (denying an alleged debt), not a credit-counseling
   or debt-management-plan issue.
2. *"I don't believe that the debt reported on my credit report is valid."*
   — same pattern. Reads as a collections dispute.
3. *"Relentless calls 10 in a row at times this is harassment"* — official:
   Debt or credit management. Model: Debt collection. **This is textbook
   FDCPA-style collector harassment language.** The model's classification
   looks more accurate than the official label here.
4. *"I spoke with transunion rep and she instructed me to file a complaint
   through the ftc."* — genuinely ambiguous; too short to confidently
   classify either way. Included here so this writeup doesn't cherry-pick
   only the clean cases.

Three of four examples suggest the model's classification was **more**
accurate than the original CFPB category, not less. CFPB's own definition of
"Debt or credit management" refers to credit-counseling and debt-management
*plan* services — not being pursued by a collector — so complaints like #1
and #3 look like they were misfiled at intake or by the consumer's own
category selection, not misclassified by the model.

**This was checked in one category, not validated across all of them** —
this is a single worked example of the pattern, not a claim that every
low-agreement category has the same root cause. The Payday loan category
(66%) was not hand-inspected and may have a different explanation entirely.

## Recommendation for the BRD

This supports a narrow, specific next step, not a broad "deploy AI triage"
claim:

- **Feasible as a QA/audit layer, not yet as an autonomous router.** Use
  LLM classification to *flag* complaints where the model disagrees with
  the official category, for human review — not to silently reassign
  categories. The "Debt or credit management" finding suggests this would
  surface a real, actionable pattern (a specific category that appears to
  absorb misfiled debt-collection complaints).
- **Do not deploy without per-category validation.** The 50-point spread
  between categories (44%–94%) means a single "the model is X% accurate"
  claim would be misleading — some categories need dedicated review, others
  are already high-confidence.
- **Next step if pursued:** targeted audit of "Debt or credit management"
  specifically — pull all complaints in that category over a longer window,
  check what fraction resemble collections language, and quantify the
  potential misrouting rate before recommending a taxonomy or intake-form
  change.

## Files

- `build_sample.py` — stratified sampling script (re-fetches narrative text
  from CFPB's API by complaint_id; narratives are not stored locally)
- `classify_and_score.py` — classification + scoring
- `sample.csv`, `results.csv`, `confusion_summary.txt` — outputs
