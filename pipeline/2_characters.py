""" Find the characters and write the character list. """

import csv
from encodings.aliases import aliases
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (CHAPTERS_CSV, CHARACTER_CANDIDATES_CSV, CHARACTERS_CSV, LEAVE_OUT, MAX_CHARACTERS, MIN_NAME_COUNT, SPACY_MODEL)

#--------------------------------
# Human knowledge for spaCy
#--------------------------------
ALIASES = {
    # Trio
    "Harry Potter": ["the Boy Who Lived", "Potter"],
    "Ron Weasley": ["Ronald", "Ron"],
    "Hermione Granger": ["Granger", "Miss Granger"],

    # Weasley family
    "Molly Weasley": ["Mrs. Weasley"],
    "Arthur Weasley": ["Mr. Weasley"],
    "Ginny Weasley": ["Ginevra"],
    "Fred Weasley": ["Fred"],
    "George Weasley": ["George"],
    "Bill Weasley": ["Bill"],

    # Dursley family
    "Petunia Dursley": ["Aunt Petunia", "Mrs. Dursley"],
    "Vernon Dursley": ["Uncle Vernon", "Mr. Dursley"],
    "Dudley Dursley": ["Dudley"],

    # Students
    "Neville Longbottom": ["Neville", "Longbottom"],
    "Draco Malfoy": ["Malfoy"],
    "Vincent Crabbe": ["Crabbe"],
    "Gregory Goyle": ["Goyle"],
    "Fleur Delacour": ["Fleur"],
    "Lavender Brown": ["Lavender"],
    "Parvati Patil": ["Parvati"],

    # Hogwarts staff
    "Albus Dumbledore": ["Dumbledore", "Professor Dumbledore", "Headmaster Dumbledore", "Albus"],
    "Poppy Pomfrey": ["Madam Pomfrey"],
    "Alastor Moody": ["Mad-Eye", "Mad-Eye Moody"],
    "Rubeus Hagrid": ["Hagrid", "Rubeus"],
    "Severus Snape": ["Snape", "Professor Snape"],
    "Minerva McGonagall": ["McGonagall", "Professor McGonagall", "Minerva"],
    "Sybill Trelawney": ["Trelawney", "Professor Trelawney", "Sybill"],
    "Filius Flitwick": ["Flitwick", "Professor Flitwick"],
    "Pomona Sprout": ["Sprout", "Professor Sprout"],
    "Horace Slughorn": ["Slughorn", "Professor Slughorn"],
    "Quirinus Quirrell": ["Quirrell", "Professor Quirrell"],
    "Argus Filch": ["Filch", "Mr. Filch"],

    # Allies
    "Sirius Black": ["Padfoot", "Snuffles", "Black"],
    "Remus Lupin": ["Moony"],
    "James Potter": ["Prongs"],
    "Lily Potter": ["Lily Evans"],
    "Nymphadora Tonks": ["Tonks", "Nymphadora"],
    "Aberforth Dumbledore": ["Aberforth"],
    "Garrick Ollivander": ["Ollivander", "Mr. Ollivander"],
    "Arabella Figg": ["Mrs. Figg", "Figg"],

    # Villains
    "Lord Voldemort": ["Voldemort", "You-Know-Who", "He-Who-Must-Not-Be-Named", "the Dark Lord", "Tom Riddle", "Riddle"],
    "Peter Pettigrew": ["Wormtail", "Scabbers"],
    "Lucius Malfoy": ["Mr. Malfoy"],
    "Narcissa Malfoy": ["Mrs. Malfoy"],
    "Dolores Umbridge": ["Umbridge", "Professor Umbridge", "Dolores"],
    "Bellatrix Lestrange": ["Bellatrix", "Lestrange"],
    "Fenrir Greyback": ["Greyback"],
    "Igor Karkaroff": ["Karkaroff", "Professor Karkaroff"],

    # Other
    "Olympe Maxime": ["Madame Maxime"],
    "Mundungus Fletcher": ["Mundungus", "Fletcher"],
    "Cornelius Fudge": ["Minister Fudge", "Fudge"],
    "Barty Crouch": ["Barty Crouch Sr.", "Mr. Crouch"],
    "Rufus Scrimgeour": ["Minister Scrimgeour", "Scrimgeour"],

}

_FEMALE = [
    # Trio
    "Hermione Granger",

    # Weasley family
    "Molly Weasley", "Ginny Weasley",

    # Dursley family
    "Petunia Dursley",

    # Students
    "Fleur Delacour", "Lavender Brown", "Parvati Patil",

    # Hogwarts staff
    "Poppy Pomfrey", "Minerva McGonagall", "Sybill Trelawney", "Pomona Sprout",

    # Allies
    "Lily Potter", "Nymphadora Tonks", "Arabella Figg",

    # Villains
    "Narcissa Malfoy", "Dolores Umbridge", "Bellatrix Lestrange",

    # Other
    "Olympe Maxime",

    # Wrong in the pronoun vote (not in ALIASES)
    "Alicia Spinnet", "Auntie Muriel", "Bertha Jorkins", "Hannah Abbott", "Angelina Johnson",
]
GENDER_OVERRIDES = {name: "male" for name in ALIASES}
GENDER_OVERRIDES.update({name: "female" for name in _FEMALE})

NOT_PERSONS = {
    # Hogwarts
    "Hogwarts", "Gryffindor", "Hufflepuff", "Ravenclaw", "Slytherin", "Quidditch",

    # Locations
    "Gringotts", "Diagon Alley", "Hogsmeade", "Privet Drive", "Godric's Hollow", "Azkaban", "Burrow",

    # Objects
    "Firebolt", "Nimbus", "Nimbus two thousand", "Invisibility Cloak", "Elder Wand", "Resurrection Stone", "Philosopher's Stone", "Bludger", "Snitch", "Golden Snitch", "Horcrux", "Horcruxes", "Deathly Hallows", "Marauder's Map", "Marauders' Map", "Time-Turner", "Pensieve", "Sorting Hat", "Floo", "Polyjuice", "Butterbeer", "Cloak", "Prophet", "Daily Prophet", "Quibbler", "Map",

    # Spells
    "Patronus", "Avada Kedavra", "Crucio", "Imperio", "Expelliarmus", "Stupefy", "Sectumsempra", "Obliviate", "Rictusempra", "Petrificus Totalus", "Accio", "Alohomora", "Expecto Patronum", "Lumos", "Nox",

    # Creatures
    "Fang", "Norbert", "Aragog", "Norris", "Mrs. Norris", "Crookshanks", "Hedwig", "Buckbeat", "Fawkes", "Thestral", "Dobby", "Winky", "Kreacher", "Nagini", "Grawp", "Fluffy", "Basilisk", "Acromantula", "Hippogriff", "Grindylow", "Dementor", "Dementors", 

    # Other
    "Madam", "Mum", "Dad", "Muggle", "Muggles", "Professor", "Sir", "Gran", "Merlin", "Yeh", "Uncle", "Aunt", "Mark", "Dark Mark", "Don", "Blimey", "Keeper", "Seeker", "Chaser", "Beater", "Captain", "Prefect", "Head Boy", "Head Girl", "Headmaster", "Headmistress", "Minister of Magic", "Durmstrang", "Beauxbatons", "Death",
}

#--------------------------------
# Settings
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

TITLE_VOTES = 5
VOTE_WINDOW = 25
DOMINANCE = 3

#--------------------------------
# Small helpers
#--------------------------------
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

    _, bare = split_title(variant)
    if not re.match(r"[A-Z]", bare) or not re.search(r"[a-z]", bare):
        return False
    if "," in bare or " and " in bare:  # "Harry, Ron" = two people, not one name
        return False

    words = bare.split()
    if any(w[0].islower() for w in words[1:] if w not in ("of", "the", "de")):
        return False

    return bare not in NOT_PERSONS and singular not in NOT_PERSONS

#--------------------------------
# Find the names and gender votes
#--------------------------------
def find_names(chapters):
    """
    Run spaCy NER over all chapters.

    Returns
    -------
    counts : Counter     variant -> how often spaCy found it
    votes  : dict        variant -> Counter({"female": n, "male": n})
    """
    import spacy

    nlp = spacy.load(SPACY_MODEL, disable=["parser", "lemmatizer", "attribute_ruler", "tagger"])

    counts, votes = Counter(), defaultdict(Counter)
    for number, chapter in enumerate(chapters, 1):
        paragraphs = [p for p in re.split(r"\n\s*\n|(?:/n){2,}", chapter["text"]) if p.strip()]
        for doc in nlp.pipe(paragraphs, batch_size=64):
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

#--------------------------------
# Grouping variants into characters
#--------------------------------
def group_characters(counts, votes, aliases=ALIASES, min_count=MIN_NAME_COUNT, max_characters=MAX_CHARACTERS, overrides=GENDER_OVERRIDES):
    """ Turn variant counts and gender votes into a character list. """
    report = {}
    alias_of = {v: name for name, variants in aliases.items() for v in variants}

    votes = {v: Counter(c) for v, c in votes.items()}
    for variant in counts:
        title, _ = split_title(variant)
        if title and TITLES[title]:
            votes.setdefault(variant, Counter())[TITLES[title]] += TITLE_VOTES

    members = defaultdict(list)  

    for name, variants in aliases.items():
        for variant in [name] + variants:
            if variant not in members[name]:
                members[name].append(variant)
            report[variant] = ("alias", name)

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

    ranked = sorted([c for c in members if total(c) > 0 or c in aliases], key=total, reverse=True)
    characters = []
    for name in ranked:
        if len(characters) >= max_characters and name not in aliases:
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
    """A variant may belong to one character only (step 3 checks this): keep it for the
    most mentioned character and drop it from the others."""
    seen = set()
    for c in characters:
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
    dropped = Counter({name: counts[v] for v, (result, name) in report.items()
                       if result == "no gender votes"})
    if dropped:
        top = ", ".join(name for name, _ in dropped.most_common(8))
        print(f"Left out for lack of gender votes (add to GENDER_OVERRIDES to keep): {top}")


if __name__ == "__main__":
    main()