""" Find the characters and write the character list. """

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (CHAPTERS_CSV, CHARACTER_CANDIDATES_CSV, CHARACTERS_CSV,  # noqa: E402
                    LEAVE_OUT, MAX_CHARACTERS, MIN_NAME_COUNT, SPACY_MODEL)

# spaCy is imported inside find_names() only, so the grouping functions below can be
# imported and tested without spaCy installed.

# ======================================================================================
# Human knowledge: the parts spaCy cannot work out on its own
# ======================================================================================

# Nicknames, epithets and titled surnames, per character: "canonical name": [variants].
# These variants always belong to that character, whatever the automatic grouping says.
# The canonical name is the character's name in the app; if spaCy also finds that name,
# its other variants join automatically.
ALIASES = {
    "Harry Potter": ["the Boy Who Lived", "Potter"],
    "Lord Voldemort": ["Voldemort", "You-Know-Who", "He-Who-Must-Not-Be-Named",
                       "the Dark Lord", "Tom Riddle", "Riddle"],
    "Sirius Black": ["Padfoot", "Snuffles", "Black"],
    "Peter Pettigrew": ["Wormtail", "Scabbers"],
    "Remus Lupin": ["Moony"],
    "James Potter": ["Prongs"],
    "Lily Potter": ["Lily Evans"],
    "Alastor Moody": ["Mad-Eye", "Mad-Eye Moody"],
    "Hermione Granger": ["Granger", "Miss Granger"],
    "Ron Weasley": ["Ronald"],
    "Ginny Weasley": ["Ginevra"],
    "Draco Malfoy": ["Malfoy"],
    "Molly Weasley": ["Mrs. Weasley"],
    "Arthur Weasley": ["Mr. Weasley"],
    "Petunia Dursley": ["Aunt Petunia", "Mrs. Dursley"],
    "Vernon Dursley": ["Uncle Vernon", "Mr. Dursley"],
    "Lucius Malfoy": ["Mr. Malfoy"],
    "Narcissa Malfoy": ["Mrs. Malfoy"],
    "Poppy Pomfrey": ["Madam Pomfrey"],
    "Olympe Maxime": ["Madame Maxime"],
}

# Corrections for a wrong majority vote: "character": "female" / "male".
GENDER_OVERRIDES = {}

# Words spaCy sometimes marks as PERSON but that are not characters (houses, places,
# creatures, spells, brooms, ...). Compared without titles and without a final "s".
NOT_PERSONS = {
    "Hogwarts", "Gryffindor", "Slytherin", "Hufflepuff", "Ravenclaw", "Quidditch",
    "Muggle", "Dementor", "Death Eater", "Auror", "Gringotts", "Hogsmeade", "Azkaban",
    "Diagon Alley", "Firebolt", "Nimbus", "Nimbus Two Thousand", "Snitch", "Bludger",
    "Quaffle", "Patronus", "Pensieve", "Horcrux", "Expelliarmus", "Lumos", "Accio",
    "Stupefy", "Crucio", "Avada Kedavra", "Floo", "Polyjuice", "Butterbeer",
    "Professor", "Sir", "Madam", "Mum", "Dad", "Gran", "Merlin", "Hallows",
}

# ======================================================================================
# Settings for the automatic grouping
# ======================================================================================

# Titles kept with a name, and the gender they imply (None = says nothing about gender).
TITLES = {
    "Mr.": "male", "Mr": "male", "Uncle": "male", "Lord": "male", "Sir": "male",
    "Mrs.": "female", "Mrs": "female", "Miss": "female", "Ms.": "female",
    "Madam": "female", "Madame": "female", "Aunt": "female", "Lady": "female",
    "Professor": None, "Headmaster": "male", "Headmistress": "female", "Dr.": None,
}

PRONOUNS = {
    "he": "male", "him": "male", "his": "male", "himself": "male",
    "she": "female", "her": "female", "hers": "female", "herself": "female",
}

# How many votes a gendered title (Mr., Mrs., ...) is worth for the titled form.
TITLE_VOTES = 5

# Gender votes: how many words after a name are searched for the first he/she.
VOTE_WINDOW = 25

# A short name joins the most mentioned matching character only if that character is
# mentioned at least this many times more than the second one. Otherwise: ambiguous.
DOMINANCE = 3


# ======================================================================================
# Small helpers (no spaCy needed)
# ======================================================================================

def clean(text):
    """Tidy a name as found: straight quotes, no possessive 's, no line-break leftovers
    ("/n", "\\n") or trailing punctuation, single spaces."""
    text = re.sub(r"(/n|\\n)+", " ", text.replace("’", "'"))
    text = text.strip(" '\".,;:!?")
    text = re.sub(r"'s?$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def split_title(variant):
    """'Professor McGonagall' -> ('Professor', 'McGonagall'); 'Harry' -> (None, 'Harry')."""
    first, _, rest = variant.partition(" ")
    if first in TITLES and rest:
        return first, rest
    return None, variant


def looks_like_name(variant):
    """Starts with a capital, contains letters, and is not on the NOT_PERSONS list."""
    _, bare = split_title(variant)
    if not re.match(r"[A-Z]", bare) or not re.search(r"[a-z]", bare):
        return False
    singular = bare[:-1] if bare.endswith("s") else bare
    return bare not in NOT_PERSONS and singular not in NOT_PERSONS


# ======================================================================================
# Step 1-2: finding names and gender votes with spaCy
# ======================================================================================

def find_names(chapters):
    """
    Run spaCy NER over all chapters.

    Returns
    -------
    counts : Counter     variant -> how often spaCy found it
    votes  : dict        variant -> Counter({"female": n, "male": n})
    """
    import spacy

    # Only the parts needed for names are switched on: much faster than a full parse.
    nlp = spacy.load(SPACY_MODEL, disable=["parser", "lemmatizer", "attribute_ruler", "tagger"])

    counts, votes = Counter(), defaultdict(Counter)
    for number, chapter in enumerate(chapters, 1):
        # Split into paragraphs; also on literal "/n" leftovers, if the text has them.
        paragraphs = [p for p in re.split(r"\n\s*\n|(?:/n){2,}", chapter["text"]) if p.strip()]
        for doc in nlp.pipe(paragraphs, batch_size=64):
            people = [e for e in doc.ents if e.label_ == "PERSON"]
            person_starts = {e.start for e in people}

            for ent in people:
                # Keep a title right before the name: "Mrs." + "Weasley".
                text = ent.text
                if ent.start > 0 and doc[ent.start - 1].text in TITLES:
                    text = f"{doc[ent.start - 1].text} {text}"
                variant = clean(text)
                if not looks_like_name(variant):
                    continue
                counts[variant] += 1

                # Gender vote: the first pronoun in the next VOTE_WINDOW words, unless
                # another name comes first (then the pronoun is probably about them).
                for tok in doc[ent.end:min(ent.end + VOTE_WINDOW, len(doc))]:
                    if tok.i in person_starts:
                        break
                    gender = PRONOUNS.get(tok.lower_)
                    if gender:
                        votes[variant][gender] += 1
                        break
        print(f"  names: chapter {number}/{len(chapters)}", end="\r", flush=True)
    print()
    n_votes = sum(sum(v.values()) for v in votes.values())
    print(f"  {len(counts):,} different names, {sum(counts.values()):,} name mentions, "
          f"{n_votes:,} gender votes from pronouns")
    if n_votes == 0:
        print("  WARNING: no pronoun votes at all. Check that data/interim/chapters.csv contains "
              "normal text (run step 1 again with the current 1_chapters.py).")
    return counts, votes


# ======================================================================================
# Step 3-5: grouping variants into characters
# ======================================================================================

def group_characters(counts, votes, aliases=ALIASES, min_count=MIN_NAME_COUNT,
                     max_characters=MAX_CHARACTERS, overrides=GENDER_OVERRIDES):
    """
    Turn variant counts and gender votes into a character list.

    Returns
    -------
    characters : list of dict  (character, gender, variants, found, gender_share),
                 most mentioned first
    report     : dict variant -> (what happened, character or "")
    """
    report = {}
    alias_of = {v: name for name, variants in aliases.items() for v in variants}

    # Title votes: a gendered title counts as a few votes for the titled form ("Mrs.
    # Weasley" -> female). Only a few, so a character's own pronoun votes always weigh more.
    votes = {v: Counter(c) for v, c in votes.items()}
    for variant in counts:
        title, _ = split_title(variant)
        if title and TITLES[title]:
            votes.setdefault(variant, Counter())[TITLES[title]] += TITLE_VOTES

    members = defaultdict(list)  # character -> its variants

    # Aliases first: they always win.
    for variant in counts:
        if variant in alias_of:
            members[alias_of[variant]].append(variant)
            report[variant] = ("alias", alias_of[variant])
    for name in aliases:  # the canonical name itself belongs to the character too
        if name in counts and name not in report:
            members[name].append(name)
            report[name] = ("alias", name)

    # The rest: a person's name, and frequent enough?
    rest = []
    for variant, n in counts.items():
        if variant in report:
            continue
        if not looks_like_name(variant):
            report[variant] = ("not a person", "")
        elif variant.endswith("s") and variant[:-1] in counts:
            report[variant] = ("family (plural)", "")  # "the Weasleys", "the Dursleys"
        elif n < min_count:
            report[variant] = ("too rare", "")
        else:
            rest.append(variant)

    # Full names (two or more words, without the title) start characters, most found first.
    words = {v: split_title(v)[1].split() for v in rest}
    full = sorted([v for v in rest if len(words[v]) >= 2], key=counts.get, reverse=True)
    for variant in full:
        # "Harry James Potter" joins "Harry Potter" (same first and last word).
        match = next((c for c in members if len(c.split()) >= 2 and c.split()[0] == words[variant][0]
                      and c.split()[-1] == words[variant][-1]), None)
        name = match or variant
        members[name].append(variant)
        report[variant] = ("kept" if name == variant else "merged", name)

    def total(name):
        return sum(counts.get(v, 0) for v in members[name])

    # Every alias name is a possible target, even if spaCy never found it written out
    # in full: "Harry" then still joins "Harry Potter".
    for name in aliases:
        members.setdefault(name, [])

    # Short and titled names join the full name that contains them.
    short = sorted([v for v in rest if v not in report], key=counts.get, reverse=True)
    for variant in short:
        bare_words = set(words[variant])
        candidates = [c for c in members if bare_words <= set(c.split())]
        title, _ = split_title(variant)
        if title and TITLES[title]:
            # "Mrs. X" can only be a woman called X: merge only into a character whose own
            # pronoun votes say female. "Mr. Lovegood" therefore never becomes Luna.
            candidates = [c for c in candidates if gender_of(c, members, votes)[0] == TITLES[title]]
        if not candidates:
            members[variant].append(variant)
            report[variant] = ("kept", variant)
            continue
        ranked = sorted(candidates, key=total, reverse=True)
        if len(ranked) == 1 or total(ranked[0]) >= DOMINANCE * total(ranked[1]):
            members[ranked[0]].append(variant)
            report[variant] = ("merged", ranked[0])
        else:
            report[variant] = ("ambiguous", " / ".join(ranked[:4]))

    # Keep the most mentioned characters.
    ranked = sorted([c for c in members if total(c) > 0], key=total, reverse=True)
    characters = []
    for name in ranked:
        if len(characters) >= max_characters:
            for v in members[name]:
                report[v] = ("not in the top", name)
            continue
        gender, share = gender_of(name, members, votes)
        if name in overrides:
            gender = overrides[name]
        if gender is None:  # no votes at all: cannot be used for a gender comparison
            for v in members[name]:
                report[v] = ("no gender votes", name)
            continue
        variants = sorted(set(members[name]) | {name}, key=lambda v: (-len(v), v))
        characters.append({"character": name, "gender": gender, "variants": variants,
                           "found": total(name), "gender_share": round(share, 2)})
    return characters, report


def gender_of(name, members, votes):
    """Majority gender of a character from its variants' votes -> (gender, share)."""
    tally = Counter()
    for v in members.get(name, [name]):
        tally.update(votes.get(v, {}))
    if not tally:
        return None, 0.0
    gender, n = tally.most_common(1)[0]
    return gender, n / sum(tally.values())


def remove_duplicates(characters):
    """A variant may belong to one character only (step 3 checks this): keep it for the
    most mentioned character and drop it from the others."""
    seen = set()
    for c in characters:  # most mentioned first
        c["variants"] = [v for v in c["variants"] if v not in seen]
        seen.update(c["variants"])
    return characters


# ======================================================================================
# Main
# ======================================================================================

def main():
    csv.field_size_limit(sys.maxsize)
    with open(CHAPTERS_CSV, encoding="utf-8") as f:
        chapters = list(csv.DictReader(f))

    print("Finding names with spaCy ...")
    counts, votes = find_names(chapters)
    characters, report = group_characters(counts, votes)
    characters = remove_duplicates(characters)

    CHARACTERS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(CHARACTERS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["character", "gender", "group", "variants", "found", "gender_share"])
        for c in characters:
            writer.writerow([c["character"], c["gender"], "character", ";".join(c["variants"]),
                             c["found"], c["gender_share"]])

    CHARACTER_CANDIDATES_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(CHARACTER_CANDIDATES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["variant", "found", "female_votes", "male_votes", "result", "character"])
        for variant, n in counts.most_common():
            result, name = report.get(variant, ("not a person", ""))
            v = votes.get(variant, {})
            writer.writerow([variant, n, v.get("female", 0), v.get("male", 0), result, name])

    women = sum(1 for c in characters if c["gender"] == "female")
    unsure = [c["character"] for c in characters if c["gender_share"] < 0.7]
    print(f"Wrote {len(characters)} characters ({women} female, {len(characters) - women} male) "
          f"to {CHARACTERS_CSV}")
    print(f"Every name found and what happened to it: {CHARACTER_CANDIDATES_CSV}")
    if unsure:
        print("Check the gender of (less than 70% of votes agree):", ", ".join(unsure))
    missing = [name for name in LEAVE_OUT if name not in {c["character"] for c in characters}]
    if missing:
        print(f"Note: LEAVE_OUT in config.py names {missing}, which are not in the list.")
    dropped = Counter({name: counts[v] for v, (result, name) in report.items()
                       if result == "no gender votes"})
    if dropped:
        top = ", ".join(name for name, _ in dropped.most_common(8))
        print(f"Left out for lack of gender votes (add to GENDER_OVERRIDES to keep): {top}")


if __name__ == "__main__":
    main()