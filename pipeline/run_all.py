""" Run all steps 1-5. """

import argparse
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent 

STEPS = {
    1: "1_chapters.py",
    2: "2_characters.py",
    3: "3_mentions.py",
    4: "4_extract.py",
    5: "5_aggregate.py",
}
SPACY_STEPS = {2, 4}


def main():
    parser = argparse.ArgumentParser(description="Run the data pipeline.")
    parser.add_argument("--skip-spacy", action="store_true", help="skip steps 2 and 4 (spaCy)")
    parser.add_argument("--from", dest="start", type=int, default=1, choices=STEPS,
                        help="first step to run (default 1)")
    parser.add_argument("--to", dest="end", type=int, default=max(STEPS), choices=STEPS,
                        help="last step to run (default: the last one)")
    args = parser.parse_args()

    for number, script in STEPS.items():
        if number < args.start or number > args.end:
            continue
        if number in SPACY_STEPS and args.skip_spacy:
            print(f"\n=== Step {number}: {script}  (skipped: --skip-spacy)")
            continue
        print(f"\n=== Step {number}: {script}")
        sys.argv = [str(HERE / script)]
        runpy.run_path(str(HERE / script), run_name="__main__")

    print("\nPipeline finished. Start the app with:  python app/app.py")


if __name__ == "__main__":
    main()