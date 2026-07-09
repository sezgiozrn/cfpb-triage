"""
Step 2 of the LLM triage-feasibility eval: classify sampled narratives and
score against official CFPB product categories.

Method:
- Model: claude-sonnet-4-6 via the Anthropic API
- Task: given only the consumer's narrative text, assign exactly one of the
  10 core product categories (the same closed set the intake process uses)
- Grader: exact match against the official CFPB-assigned product category
- Honest-grader notes:
  * The official category is NOT guaranteed ground truth -- it reflects
    whatever the consumer selected or intake assigned, which is exactly the
    process being evaluated for redesign. Disagreements are inspected by
    hand (Step 3) before being counted as model errors.
  * Narratives are redacted by CFPB (XXXX masking), which removes some
    category-relevant signal (company names, amounts). This handicaps the
    model relative to a production integration that would see full text.

Reads:  evals/sample.csv
Writes: evals/results.csv (complaint_id, product_official, product_predicted, match)
        evals/confusion_summary.txt

API key: loaded from career-ops .env (ANTHROPIC_API_KEY), never printed.
"""

import csv
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

ENV_PATH = Path(__file__).parent.parent / ".env"
MODEL = "claude-sonnet-4-6"
API = "https://api.anthropic.com/v1/messages"

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

PROMPT = """You are classifying a consumer financial complaint into exactly one product category.

Categories (choose exactly one, verbatim):
{categories}

Complaint narrative:
<narrative>
{narrative}
</narrative>

Respond with ONLY the category name, exactly as written above. No explanation."""


def load_api_key() -> str:
    for line in ENV_PATH.read_text().splitlines():
        if line.startswith("ANTHROPIC_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(f"ANTHROPIC_API_KEY not found in {ENV_PATH}")


def classify(narrative: str, api_key: str) -> str | None:
    body = {
        "model": MODEL,
        "max_tokens": 50,
        "messages": [{
            "role": "user",
            "content": PROMPT.format(
                categories="\n".join(f"- {c}" for c in CATEGORIES),
                narrative=narrative[:6000],  # cap very long narratives
            ),
        }],
    }
    for attempt in range(4):
        try:
            r = requests.post(
                API,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=body,
                timeout=60,
            )
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            text = "".join(
                b.get("text", "") for b in r.json().get("content", [])
                if b.get("type") == "text"
            ).strip()
            # exact-match the closed set; tolerate stray whitespace/case only
            for c in CATEGORIES:
                if text.lower() == c.lower():
                    return c
            return f"UNPARSEABLE::{text[:60]}"
        except requests.RequestException:
            time.sleep(5 * (attempt + 1))
    return None


def main():
    api_key = load_api_key()

    rows = list(csv.DictReader(open("evals/sample.csv")))
    print(f"{len(rows)} narratives to classify")

    out = open("evals/results.csv", "w", newline="")
    w = csv.writer(out)
    w.writerow(["complaint_id", "product_official", "product_predicted", "match"])

    agree = 0
    confusion = defaultdict(int)

    for i, row in enumerate(rows, 1):
        pred = classify(row["narrative"], api_key)
        match = pred == row["product"]
        agree += match
        confusion[(row["product"], pred)] += 1
        w.writerow([row["complaint_id"], row["product"], pred, match])
        if i % 25 == 0:
            print(f"  {i}/{len(rows)} done, running agreement {agree}/{i} "
                  f"({100*agree/i:.1f}%)", flush=True)
        time.sleep(0.2)

    out.close()

    with open("evals/confusion_summary.txt", "w") as f:
        f.write(f"Overall agreement: {agree}/{len(rows)} ({100*agree/len(rows):.1f}%)\n\n")
        f.write("Disagreements by (official -> predicted), descending:\n")
        for (off, pred), n in sorted(confusion.items(), key=lambda x: -x[1]):
            if off != pred:
                f.write(f"  {n:3d}  {off}  ->  {pred}\n")

    print(f"\nDone. Agreement {agree}/{len(rows)} ({100*agree/len(rows):.1f}%)")
    print("Results: evals/results.csv, evals/confusion_summary.txt")


if __name__ == "__main__":
    main()
