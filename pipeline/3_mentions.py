""" Count how often each character is mentioned, and which charachters appear together. """

import csv
import itertools
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CHAPTERS_CSV, CHARACTER_CSV, COOCCURRENCES_CSV, MENTIONS_CSV

PRONOUNS = {
    "male": re.compile(r"\b(he|him|his|himself)\b", re.I),
    "female": re.compile(r"\b(she|her|hers|herself)\b", re.I),
}

def load_characters():
    """ Read character list and build a lookup from name varient to character. """
    with open(CHARACTER_CSV, encoding="utf-8") as f:
        characters = list(csv.DictReader(f))

    variant_to_character = {}
    for row in characters:
        for variant in row["variants"].split(";"):
            variant = variant.strip()
            if variant in variant_to_character:
                sys.exit(
                    f'Name variant "{variant}" is listed for two characters in characters.csv'
                )
            variant_to_character[variant] = row

    return characters, variant_to_character

def build_name_pattern(variants):
    """ Build one regular expression that matches any name variant. """
    ordered = sorted(variants, key = len, reverse = True)
    alternatives = "|".join(re.escape(v) for v in ordered)

    return re.compile(r"(?<![\w-])(" + alternatives + r")(?![\w-])")

def main():
    csv.field_size_limit(sys.maxsize)
    chapters = pd.read_csv(CHAPTERS_CSV)
    characters, variant_to_character = load_characters()
    name_pattern = build_name_pattern(variant_to_character)

    mention_rows = []
    pair_counts = Counter()

    for chapter in chapters.itertuples():
        chapter_info = {
            "book": chapter.book,
            "book_title": chapter.book_title,
            "chapter": chapter.chapter,
            "title": chapter.title,
        }
        counts = Counter()

        for paragraph in chapter.text.split("\n\n"):
            named_here = set()
            for match in name_pattern.finditer(paragraph):
                name = variant_to_character[match.group(1)]["character"]
                counts[name] += 1
                named_here.add(name)

            for a, b in itertools.combinations(sorted(named_here), 2):
                pair_counts[(chapter.book, a, b)] += 1

        for row in characters:
            name = row["character"]
            if counts[name] > 0:
                mention_rows.append({**chapter_info, "character": name, "gender": row["gender"], "group": row["group"], "kind": "name", "mentions": counts[name]})

        for gender, pattern in PRONOUNS.items():
            mention_rows.append({**chapter_info, "character": f"pronoun ({gender})", "gender": gender, "group": "pronoun", "kind": "pronoun", "mentions": len(pattern.findall(chapter.text))})

    MENTIONS_CSV.parent.mkdir(parents=True, exist_ok=True)
    mentions = pd.DataFrame(mention_rows)
    mentions.to_csv(MENTIONS_CSV, index = False)

    cooccurrence = pd.DataFrame([{"book": book, "character_a": a, "character_b": b, "paragraphs": n} for (book, a, b), n in pair_counts.items()]).sort_values(["book", "paragraphs"], ascending=[True, False])
    cooccurrence.to_csv(COOCCURRENCES_CSV, index=False)

    names = mentions[mentions.kind == "name"]
    top = names.groupby("character").mentions.sum().sort_values(ascending = False).head(5)

    print("Most mentioned:", ", ".join(f"{c} ({n:,})" for c, n in top.items()))

    by_book = mentions.groupby(["book", "kind", "gender"]).mentions.sum().unstack()
    share = (by_book["female"] / (by_book["female"] + by_book["male"]) * 100).unstack().round(1)

    print("Share of mentions that are female (%), per book:")
    print(share.to_string())
    print(f"Wrote {len(mentions):,} rows to {MENTIONS_CSV}")
    print(f"Wrote {len(cooccurrence):,} character pairs to {COOCCURRENCES_CSV}")

if __name__ == "__main__":
    main()