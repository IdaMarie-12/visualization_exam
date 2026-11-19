""" Find the characters and write the character list. """

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (CHAPTERS_CSV, CHARACTER_CANDIDATES_CSV, CHARACTERS_CSV, LEAVE_OUT, MAX_CHARACTERS, MIN_NAME_COUNT, SPACY_MODEL)

#--------------------------------
# Lists
#--------------------------------
ALIASES = {
    "Harry Potter": ["The Boy Who Lived", "The Chosen One", "Harry James Potter", "Potter"],
    "Lord Voldemort": ["Voldemort", "You-Know-Who", "He-Who-Must-Not-Be-Named", "the Dark Lord", "Tom Riddle", "Riddle"],
    "Albus Dumbledore": ["Albus Percival Wulfric Brian Dumbledore", "The Headmaster"],
    "Sirius Black": ["Padfoot", "Snuffles", "the Grim", "Black"],
    "Peter Pettigrew": ["Wormtail"],
    "Remus Lupin": ["Moony"],
    "James Potter": ["Prongs"],
    "Lily Potter": ["Lily Evans"],
    "Rubeus Hagrid": ["Keeper of Keys and Grounds"],
    "Alostor Moody": ["Mad-Eye Moody", "Mad-Eye"],
    "Hermione Granger": ["Granger", "Miss Granger", "Hermione Jean Granger"],
    "Ron Weasly": ["Ronald", "Ronald Bilius Weasly", "Ronnie"],
    "Ginny Weasly": ["Ginevra"],
    "Neville Longbottom": ["Longbottom"],
    "Draco Malfoy": ["Malfoy"],
    "Molly Weasly": ["Mrs. Weasly"],
    "Arthur Weasly": ["Mr. Weasly"],
    "Petunia Dursley": ["Mrs. Dursley"],
    "Vernon Dursley": ["Mr. Dursley"],
    "Lucius Malfoy": ["Mr. Malfoy"],
    "Narcissa Malfoy": ["Mrs. Malfoy"],
    "Nymphadora Tonks": ["Tonks", "Dora"],
    "Poppy Pomfrey": ["Madam Pomfrey", "Nurse Pomfrey"],
    "Pomona Sprout": ["Pomona"],
    "Olympe Maxime": ["Madam Maxime"],
    "Fenrir Grayback": ["The Werewolf"],
}

GENDER_OVERRIDES = {}

NOT_PERSONS = {
    "Hogwarts", "Gryffindor", "Slytherin", "Hufflepuff", "Ravenclaw", "Quidditch",
    "Muggle", "Dementor", "Death Eater", "Auror", "Gringotts", "Hogsmeade", "Azkaban",
    "Diagon Alley", "Firebolt", "Nimbus", "Nimbus Two Thousand", "Snitch", "Bludger",
    "Quaffle", "Patronus", "Pensieve", "Horcrux", "Expelliarmus", "Lumos", "Accio",
    "Stupefy", "Crucio", "Avada Kedavra", "Floo", "Polyjuice", "Butterbeer",
    "Professor", "Madam", "Mum", "Dad", "Gran", "Merlin", "Hallows", "Hedwig", "Crookshanks", "Fawkes", "Buckbeak", "Thestral", "Boggart", "Dementor",
    "Basilisk", "Acromantula", "Dragon", "Goblin",
    "House Elf", "Giant", "Centaur", "Vampire", "Werewolf", "Ghost", "Troll", "Pixie", "Niffler", "Grindylow", "Kneazle", "Chimaera", "Hippogriff", "Mermaid", "Kelpie", "Sphinx", "Banshee",
}

#--------------------------------
# Settings for the automatic grouping of name variants
#--------------------------------
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

DIMINANCE = 3

#--------------------------------
# Small helpers
#--------------------------------
def clean(text):
    """ Tidy a name as found. """
    text = text.replace("’", "'").strip(" '\"")
    text = re.sub(r"'s?$", "", text)
    return re.sub(r"\s+", " ", text).strip()

def split_title(variant):
    """ Professor McGonagall -> (Professor, McGonagall). """
    first, _, rest = variant.partition(" ")
    if first in TITLES and rest:
        return first, rest
    return None, variant

def looks_like_name(variant):
    """ Starts with a capital, contains letters, and is not on the NOT_PERSONS list. """
    _, bare = split_title(variant)
    if not re.match(r"[A-Z]", bare) or not re.search(r"[a-z]", bare):
        return False
    singular = bare[:-1] if bare.endswith("s") else bare
    return bare not in NOT_PERSONS and singular not in NOT_PERSONS

#--------------------------------
# Finding names and gender votes with Spacy
#--------------------------------
def find_names(chapters):
    """ Find all names in the chapters, and count them. """
    import spacy

    nlp = spacy.load(SPACY_MODEL), disable = ["parser", "lemmatizer", "attribute_ruler", "tagget"]
    nlp.add_pipe("sentencizer")

    counts, votes = Counter(), defaultdict(Counter)
    for number, chapter in enumerate(chapters, 1):
        paragraphs = [p for p in chapter["text"].split("\n\n") if p.strip()]
        for doc in nlp.pipe(paragraphs, batch_size = 64):
            sents = list(doc.sents)
            sent_index = {s.start: i for i, s in enumerate(sents)}
            people = [e for e in doc.ents if e.label_ == "PERSON"]
            person_starts = {e.start for e in people}

            for ent in people:
                text = ent.text
                if ent.start > 0 and doc[ent.start - 1].text in TITLES:
                    text = f"{doc[ent.start - 1].text} {text}"
                variant = clean(text)
                if not looks_like_name(variant):
                    continue
                counts[variant] += 1

                i = sent_index[ent.sent.start]
                end = sents[min(i + 1, len(sents) -1)].end
                for tok in doc[ent.start:end]:
                    if tok.i in person_starts:
                        break
                    gender = PRONOUNS.get(tok.lower_)
                    if gender:
                        votes[variant][gender] += 1
                        break

    print()
    return counts, votes

#--------------------------------
# Grouping name variants into characters
#--------------------------------
def group_characters(counts, votes, aliases=ALIASES, min_count=MIN_NAME_COUNT, max_characters=MAX_CHARACTERS, overrides=GENDER_OVERRIDES):
    """ Turn variant counts and gender votes into a character list. """
    report = {}
    alias_of = {v: name for name, variants in aliases.items() for v in variants}

    votes = {v: Counter(c) for v, c in votes.items()}
    for variant, n in counts.items():
        title, _ = split_title(variant)
        if title and TITLES[title]:
            votes.setdefault(variant, Counter())[TITLES[title]] += n

    members = defaultdict(list)

    for variant in counts:
        if variant in alias_of:
            members[alias_of[variant]].append(variant)
            report[variant] = ("alias", alias_of[variant])
    for name in aliases:  
        if name in counts and name not in report:
            members[name].append(name)
            report[name] = ("alias", name)

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

    words = {v: split_title(v)[1].split() for v in rest}
    full = sorted([v for v in rest if len(words[v]) >= 2], key=counts.get, reverse=True)
    for variant in full:
        match = next((c for c in members if len(c.split()) >= 2 and c.split()[0] == words[variant][0]
                      and c.split()[-1] == words[variant][-1]), None)
        name = match or variant
        members[name].append(variant)
        report[variant] = ("kept" if name == variant else "merged", name)

    def total(name):
        return sum(counts.get(v, 0) for v in members[name])

    for name in aliases:
        members.setdefault(name, [])

    short = sorted([v for v in rest if v not in report], key=counts.get, reverse=True)
    for variant in short:
        bare_words = set(words[variant])
        candidates = [c for c in members if bare_words <= set(c.split())]
        title, _ = split_title(variant)
        if title and TITLES[title]:  
            candidates = [c for c in candidates if gender_of(c, members, votes)[0] in (TITLES[title], None)]
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
        if gender is None:  
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
    """A variant may belong to one character only -> remove duplicates from the less mentioned characters."""
    seen = set()
    for c in characters:  # most mentioned first
        c["variants"] = [v for v in c["variants"] if v not in seen]
        seen.update(c["variants"])
    return characters

#--------------------------------
# Main
#--------------------------------
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


if __name__ == "__main__":
    main()
