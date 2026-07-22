"""
Misrouting audit, step 2: classify every DCM narrative with TWO independent
probes, so the misrouting estimate doesn't rest on a single prompt design.

Probe A (comparability): the exact 10-way closed-set classification from
  evals/classify_and_score.py -- same model, same prompt. A narrative is
  "misrouting-flagged" if the predicted category != "Debt or credit
  management".

Probe B (definition check): a binary rubric derived from CFPB's own
  definition of the category -- does the narrative concern CREDIT
  COUNSELING / DEBT MANAGEMENT PLAN / DEBT SETTLEMENT SERVICES (the things
  the category is FOR)? Asked independently, without showing Probe A's
  answer or the category list.

Where both probes agree the complaint doesn't belong, that's a
high-confidence misroute candidate. Where they disagree, that's the
uncertainty band -- reported, not hidden.

Reads:  evals/misrouting/dcm_narratives.csv
Writes: evals/misrouting/results.csv
        evals/misrouting/summary.txt

API key: loaded from career-ops .env (ANTHROPIC_API_KEY), same as
classify_and_score.py. Never printed.
"""

import csv
import time
from collections import Counter
from pathlib import Path

import requests

ENV_PATH = Path.home() / "Downloads" / "career-ops" / ".env"
MODEL = "claude-sonnet-4-6"
API = "https://api.anthropic.com/v1/messages"
DIR = Path(__file__).parent

CATEGORIES = [
    "Checking or savings account",
    "Credit card",
    "Debt collection",
    "Debt or credit management",
    "Money transfer, virtual currency, or money service",
    "Mortgage",
    "Payday loan, title loan, personal loan, or advance loan",
    "Prepaid card",
    "Student loan",
    "Vehicle loan or lease",
]

PROMPT_A = """You are classifying a consumer financial complaint into exactly one product category.

Categories (choose exactly one, verbatim):
{categories}

Complaint narrative:
<narrative>
{narrative}
</narrative>

Respond with ONLY the category name, exactly as written above. No explanation."""

PROMPT_B = """The CFPB product category "Debt or credit management" covers complaints about \
CREDIT COUNSELING, DEBT MANAGEMENT PLAN, DEBT SETTLEMENT, or CREDIT REPAIR SERVICES \
-- i.e., a company the consumer engaged (or was solicited by) to help manage, settle, \
consolidate, or repair their debts or credit.

It does NOT cover: being pursued by a debt collector, disputing an alleged debt, \
collection harassment, or complaints about the underlying loan/card/account itself.

Complaint narrative:
<narrative>
{narrative}
</narrative>

Question: does this narrative concern credit counseling / debt management plan / \
debt settlement / credit repair SERVICES as defined above?

Respond with ONLY one word: YES or NO."""


def load_api_key() -> str:
    import os
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    for line in ENV_PATH.read_text().splitlines():
        if line.startswith("ANTHROPIC_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(f"ANTHROPIC_API_KEY not found in {ENV_PATH}")


def call_model(prompt: str, api_key: str) -> str | None:
    body = {"model": MODEL, "max_tokens": 50,
            "messages": [{"role": "user", "content": prompt}]}
    for attempt in range(4):
        try:
            r = requests.post(API, headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }, json=body, timeout=60)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            return "".join(
                b.get("text", "") for b in r.json().get("content", [])
                if b.get("type") == "text"
            ).strip()
        except requests.RequestException:
            time.sleep(5 * (attempt + 1))
    return None


def parse_a(text: str | None) -> str:
    if text is None:
        return "API_FAILURE"
    for c in CATEGORIES:
        if text.lower() == c.lower():
            return c
    return f"UNPARSEABLE::{text[:60]}"


def parse_b(text: str | None) -> str:
    if text is None:
        return "API_FAILURE"
    t = text.strip().upper().rstrip(".")
    return t if t in ("YES", "NO") else f"UNPARSEABLE::{text[:60]}"


def main():
    api_key = load_api_key()
    rows = list(csv.DictReader(open(DIR / "dcm_narratives.csv")))
    print(f"{len(rows)} DCM narratives, 2 probes each ({2*len(rows)} calls)")

    out = open(DIR / "results.csv", "w", newline="")
    w = csv.writer(out)
    w.writerow(["complaint_id", "date_received", "probe_a_category",
                "probe_b_belongs", "verdict"])

    verdicts = Counter()
    a_cats = Counter()

    for i, row in enumerate(rows, 1):
        text = row["narrative"][:6000]
        a = parse_a(call_model(
            PROMPT_A.format(
                categories="\n".join(f"- {c}" for c in CATEGORIES),
                narrative=text), api_key))
        time.sleep(0.2)
        b = parse_b(call_model(PROMPT_B.format(narrative=text), api_key))
        time.sleep(0.2)

        a_flag = a not in ("Debt or credit management",) and not a.startswith(
            ("UNPARSEABLE", "API_FAILURE"))
        b_flag = b == "NO"
        unusable = a.startswith(("UNPARSEABLE", "API_FAILURE")) or b.startswith(
            ("UNPARSEABLE", "API_FAILURE"))
        if unusable:
            verdict = "unusable"
        elif a_flag and b_flag:
            verdict = "misroute_both_probes"
        elif a_flag or b_flag:
            verdict = "misroute_one_probe"
        else:
            verdict = "belongs"
        verdicts[verdict] += 1
        a_cats[a] += 1
        w.writerow([row["complaint_id"], row["date_received"], a, b, verdict])
        if i % 25 == 0:
            print(f"  {i}/{len(rows)}  {dict(verdicts)}", flush=True)

    out.close()
    n = len(rows)
    usable = n - verdicts["unusable"]
    both = verdicts["misroute_both_probes"]
    one = verdicts["misroute_one_probe"]

    with open(DIR / "summary.txt", "w") as f:
        f.write(f"DCM misrouting audit -- {n} narratives (CA, "
                f"2024-01-01..2026-06-30), model {MODEL}\n\n")
        f.write(f"usable: {usable}/{n}\n")
        f.write(f"misroute (BOTH probes agree):  {both}/{usable} "
                f"({100*both/usable:.1f}%)  <- headline lower bound\n")
        f.write(f"misroute (ONE probe only):     {one}/{usable} "
                f"({100*one/usable:.1f}%)  <- uncertainty band\n")
        f.write(f"belongs (both probes):         {verdicts['belongs']}/{usable} "
                f"({100*verdicts['belongs']/usable:.1f}%)\n\n")
        f.write("Probe A predicted-category distribution:\n")
        for cat, c in a_cats.most_common():
            f.write(f"  {c:4d}  {cat}\n")
    print(open(DIR / "summary.txt").read())


if __name__ == "__main__":
    main()
