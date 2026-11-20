""" Measure how accurate the spaCy extraction (step 4) is, by checking a random sample of rows by hand. """

import argparse
import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (DESCRIPTIONS_CSV, RANDOM_SEED, VALIDATION_CSV,  # noqa: E402
                    VALIDATION_SAMPLE_SIZE)


def wilson_interval(correct, total, z=1.96):
    """ 95% confidence interval for a proportion (the Wilson score interval). """
    if total == 0:
        return 0.0, 0.0
    p = correct / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return max(0.0, centre - margin), min(1.0, centre + margin)


def draw_sample(force=False):
    """Write a random, relation-balanced sample of rows for hand-checking."""
    if VALIDATION_CSV.exists() and not force:
        existing = pd.read_csv(VALIDATION_CSV)
        if existing["correct"].notna().any():
            sys.exit(f"{VALIDATION_CSV.name} already has answers in it. " f"Use --force to replace it (your answers would be lost).")

    if not DESCRIPTIONS_CSV.exists():
        sys.exit("No descriptions.csv yet: run step 4 (4_extract.py) first.")
    descriptions = pd.read_csv(DESCRIPTIONS_CSV)

    relations = sorted(descriptions.relation.unique())
    per_relation = math.ceil(VALIDATION_SAMPLE_SIZE / len(relations))
    parts = [rows.sample(min(per_relation, len(rows)), random_state=RANDOM_SEED)
             for _, rows in descriptions.groupby("relation")]
    sample = (pd.concat(parts).sample(frac=1, random_state=RANDOM_SEED).head(VALIDATION_SAMPLE_SIZE))

    sample = sample[["book", "chapter", "character", "kind", "voice", "relation", "word", "sentence"]].copy()
    sample.insert(0, "id", range(1, len(sample) + 1))
    sample["correct"] = ""   # you fill in y / n
    sample["note"] = ""      # optional comment
    sample.to_csv(VALIDATION_CSV, index=False)
    print(f"Wrote {len(sample)} rows to {VALIDATION_CSV}")
    print("Fill in the 'correct' column with y or n, save, then run:  python pipeline/validate.py score")


def score():
    """Print the accuracy of the hand-checked sample."""
    if not VALIDATION_CSV.exists():
        sys.exit("No validation sample yet: run  python pipeline/validate.py sample  first.")
    sample = pd.read_csv(VALIDATION_CSV)

    answers = sample["correct"].astype(str).str.strip().str.lower()
    sample["ok"] = answers.map({"y": True, "yes": True, "1": True, "true": True, "n": False, "no": False, "0": False, "false": False})
    checked = sample[sample.ok.notna()]
    if checked.empty:
        sys.exit("No rows have been checked yet (the 'correct' column is empty).")

    def report(label, rows):
        n, k = len(rows), int(rows.ok.sum())
        low, high = wilson_interval(k, n)
        print(f"{label:12} {k:>3}/{n:<3} = {k / n:6.1%}   95% CI {low:5.1%} - {high:5.1%}")

    print(f"Checked {len(checked)} of {len(sample)} rows.\n")
    report("overall", checked)
    print()
    for relation, rows in checked.groupby("relation"):
        report(relation, rows)
    print()
    for kind, rows in checked.groupby("kind"):
        report(kind, rows)

    notes = checked[checked.ok == False].note.dropna()  # noqa: E712
    if len(notes):
        print("\nNotes on wrong rows:")
        for note in notes:
            print("  -", note)


def main():
    parser = argparse.ArgumentParser(description="Hand-check the spaCy extraction.")
    parser.add_argument("command", choices=["sample", "score"],
                        help="sample: draw rows to check; score: compute the accuracy")
    parser.add_argument("--force", action="store_true", help="overwrite an existing sample")
    args = parser.parse_args()

    if args.command == "sample":
        draw_sample(force=args.force)
    else:
        score()


if __name__ == "__main__":
    main()