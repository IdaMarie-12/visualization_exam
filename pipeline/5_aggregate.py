""" Turn the extracted descriptions into tables. """

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import(MENTIONS_CSV, CHARACTER_TOTALS_CSV, DESCRIPTIONS_CSV, DISTINCTIVE_WORDS_CSV, LEAVE_OUT, LEXICON_DIR, MIN_PROFILE_MENTIONS, MIN_WORD_COUNT, PROFILE_TOP_WORDS, PROFILES_CSV, THEMES_CSV, USE_LINKED_PRONOUNS, WORD_COUNTS_CSV)

ALL_BOOKS = 0
VOICES = ["all", "narration", "dialogue"]
GROUP_NAMES = {"female": "All female characters", "male": "All male characters"}
OTHER = {"female": "male", "male": "female"}

#--------------------------------
# Helpers
#--------------------------------
def apply_linking_setting(table):
    """ If USE_LINKED_PRONOUNS is False, rows found through a linked prnoun count only for their gender. """
    if USE_LINKED_PRONOUNS:
        return table
    table = table.copy()
    linked = table.kind == "linked"
    table.loc[linked, "character"] = "pronoun (" + table.loc[linked, "gender"] + ")"
    table.loc[linked, "group"] = "pronoun"

    return table

def scopes(table):
    """ Yield (book, voice, rows) for every scope: book 0 (all) and 1-7. """
    for book in [ALL_BOOKS] + sorted(table.book.unique()):
        in_book = table if book == ALL_BOOKS else table[table.book == book]
        for voice in VOICES:
            rows = in_book if voice == "all" else in_book[in_book.voice == voice]
            yield book, voice, rows

def weighted_log_odds(a, b, prior):
    """ Weighted log-odds z-score with an informative Dirichlet prior. """
    a, b, a_w = np.asarray(a, float), np.asarray(b, float), np.asarray(prior, float)
    a_0, n_a, n_b = a_w.sum(), a.sum(), b.sum()
    log_odds_a = np.log((a + a_w) / (n_a + a_0 - a - a_w))
    log_odds_b = np.log((b + a_w) / (n_b + a_0 - b - a_w))

    return (log_odds_a - log_odds_b) / np.sqrt(1 / (a + a_w) + 1 / (b + a_w))

def load_lexicons():
    """ Read every resources/lexicon/<theme>.txt into {theme: set of words}."""
    lexicon = {}
    for file in sorted(LEXICON_DIR.glob("*.txt")):
        lines = [l.strip().lower() for l in file.read_text(encoding = "utf-8").splitlines()]
        lexicon[file.stem] = {l for l in lines if l and not l.startswith("#")}

    return lexicon

#--------------------------------
# Tables
#--------------------------------
def build_character_totals(mentions):
    """ Table 1: mentions per (book, voice, character). """
    return (mentions.groupby(["book", "voice", "character", "gender", "group"], as_index = False).mentions.sum())

def build_word_counts(descriptions):
    """ Table 2: count of each (book, voice, character, relation, word). """
    keys = ["book", "voice", "character", "gender", "group", "relation", "word"]

    return descriptions.groupby(keys, as_index = False).size().rename(columns = {"size": "count"})

def build_distinctive_words(descriptions, mentions, priors):
    """ Table 3: female vs male log-odds per scope, for all characters and without LEAVE_OUT."""
    results = []

    subsets = {"all": (descriptions, mentions), "without": (descriptions[~descriptions.character.isin(LEAVE_OUT)], mentions[~mentions.character.isin(LEAVE_OUT)])}
    for subset, (desc, ment) in subsets.items():
        totals = {(b, v): rows.groupby("gender").mentions.sum() for b, v, rows in scopes(ment)}
        for book, voice, rows in scopes(desc):
            gender_mentions = totals[(book, voice)]
            for relation, rel_rows in rows.groupby("relation"):
                counts = rel_rows.groupby(["word", "gender"]).size().unstack(fill_value = 0)
                counts = counts.reindex(columns = ["female", "male"], fill_value = 0)
                prior = priors[relation].reindex(counts.index, fill_value = 0)
                table = counts.reset_index()
                table["z"] = weighted_log_odds(counts.female, counts.male, prior)
                table["female_per_1000"] = table.female / gender_mentions.get("female", np.nan) * 1000
                table["male_per_1000"] = table.male / gender_mentions.get("male", np.nan) * 1000
                table = table[table.female + table.male >= MIN_WORD_COUNT]
                results.append(table.assign(book=book, voice=voice, subset=subset, relation=relation))

    columns = ["book", "voice", "subset", "relation", "word", "female", "male",
               "female_per_1000", "male_per_1000", "z"]
    return pd.concat(results, ignore_index=True)[columns].round(4)

def top_words(table):
    """ Keep the PROFILE_TOP_WORDS most frequent and most typical words of one profile. """
    frequent = table.nlargest(PROFILE_TOP_WORDS, "count")
    typical = table.nlargest(PROFILE_TOP_WORDS, "z")
    return pd.concat([frequent, typical]).drop_duplicates("word")

def build_profiles(descriptions, mentions, priors):
    """ Table 4: per character (and gender group), the most frquent and most typical describing words, with a comparison rate. """
    totals = {(b, v): rows.groupby(["character", "gender"]).mentions.sum()
              for b, v, rows in scopes(mentions)}
    profiles = []

    for book, voice, rows in scopes(descriptions):
        char_mentions = totals[(book, voice)]
        gender_mentions = char_mentions.groupby(level="gender").sum()
        gender_of = dict(char_mentions.index)  # character -> gender

        for relation, rel_rows in rows.groupby("relation"):
            matrix = rel_rows.groupby(["word", "character"]).size().unstack(fill_value=0)
            words = matrix.index
            prior = priors[relation].reindex(words, fill_value=0).to_numpy()
            total = matrix.sum(axis=1).to_numpy()
            by_gender = {g: matrix[[c for c in matrix.columns if gender_of.get(c) == g]].sum(axis=1).to_numpy()
                         for g in ("female", "male")}
            gender_rate = {g: by_gender[g] / gender_mentions.get(g, np.nan) * 1000 for g in by_gender}

            # Named characters: compared with everyone else.
            for character in matrix.columns:
                gender = gender_of.get(character)
                n = char_mentions.get((character, gender), 0)
                if character.startswith("pronoun") or n < MIN_PROFILE_MENTIONS:
                    continue
                own = matrix[character].to_numpy()
                table = pd.DataFrame({
                    "word": words, "count": own, "mentions": n,
                    "per_1000": own / n * 1000,
                    "z": weighted_log_odds(own, total - own, prior),
                    "compare_per_1000": gender_rate[gender],
                    "compare_label": f"{gender} characters",
                })
                table = top_words(table[table["count"] > 0])
                profiles.append(table.assign(book=book, voice=voice, character=character,
                                             gender=gender, relation=relation))

            # The two gender groups: compared with the other gender.
            for gender, name in GROUP_NAMES.items():
                own, other = by_gender[gender], by_gender[OTHER[gender]]
                table = pd.DataFrame({
                    "word": words, "count": own, "mentions": gender_mentions.get(gender, 0),
                    "per_1000": gender_rate[gender],
                    "z": weighted_log_odds(own, other, prior),
                    "compare_per_1000": gender_rate[OTHER[gender]],
                    "compare_label": f"{OTHER[gender]} characters",
                })
                table = top_words(table[table["count"] > 0])
                profiles.append(table.assign(book=book, voice=voice, character=name,
                                             gender=gender, relation=relation))

    columns = ["book", "voice", "character", "gender", "relation", "word", "count",
               "mentions", "per_1000", "z", "compare_per_1000", "compare_label"]
    return pd.concat(profiles, ignore_index=True)[columns].round(4)

def build_themes(descriptions, mentions, lexicons):
    """ Table 5: describing words per gender that belong to each theme. """
    descriptions = descriptions.copy()  
    totals = {(b, v): rows.groupby("gender").mentions.sum() for b, v, rows in scopes(mentions)}
    parts = descriptions.word.str.split(" ")
    rows_out = []
    for theme, words in lexicons.items():
        descriptions[f"in_{theme}"] = parts.map(lambda ws: any(w in words for w in ws))
    for book, voice, rows in scopes(descriptions):
        all_words = rows.groupby("gender").size()
        for theme in lexicons:
            in_theme = rows[rows[f"in_{theme}"]].groupby("gender").size()
            for gender in ("female", "male"):
                count = int(in_theme.get(gender, 0))
                rows_out.append({
                    "book": book, "voice": voice, "gender": gender, "theme": theme, "count": count,
                    "per_1000": round(count / totals[(book, voice)].get(gender, np.nan) * 1000, 3),
                    "share": round(count / all_words.get(gender, np.nan) * 100, 3),
                })
    return pd.DataFrame(rows_out)

#--------------------------------
# Main
#--------------------------------
def main():
    if not DESCRIPTIONS_CSV.exists() or not MENTIONS_CSV.exists():
        print("No descriptions yet: run step 4 (4_extract.py) first. Step 5 skipped.")
        return

    descriptions = apply_linking_setting(
        pd.read_csv(DESCRIPTIONS_CSV, usecols=lambda c: c != "sentence"))
    mentions = apply_linking_setting(pd.read_csv(MENTIONS_CSV))

    priors = {relation: rows.word.value_counts()
              for relation, rows in descriptions.groupby("relation")}

    tables = {
        CHARACTER_TOTALS_CSV: build_character_totals(mentions),
        WORD_COUNTS_CSV: build_word_counts(descriptions),
        DISTINCTIVE_WORDS_CSV: build_distinctive_words(descriptions, mentions, priors),
        PROFILES_CSV: build_profiles(descriptions, mentions, priors),
        THEMES_CSV: build_themes(descriptions, mentions, load_lexicons()),
    }
    for path, table in tables.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(path, index=False)
        print(f"Wrote {len(table):,} rows to {path.name}")

    # A short preview, to see right away whether the result makes sense.
    d = tables[DISTINCTIVE_WORDS_CSV]
    for subset in ("all", "without"):
        part = d[(d.book == ALL_BOOKS) & (d.voice == "all") & (d.subset == subset)
                 & (d.relation == "modifier")]
        print(f"Female-typical adjectives ({subset}):", ", ".join(part.nlargest(8, "z").word))
        print(f"Male-typical adjectives ({subset}):  ", ", ".join(part.nsmallest(8, "z").word))


if __name__ == "__main__":
    main()
