""" Extract how characters are described. """

import argparse
import bisect
import csv
import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (CHAPTERS_CSV, CHARACTERS_MENTIONS_CSV, CHARACTERS_CSV, DESCRIPTIONS_CSV, PRONOUN_WINDOW, SPACEY_MODEL)

PRONOUNS = {
    "he": "male", "him": "male", "his": "male", "himself": "male",
    "she": "female", "her": "female", "hers": "female", "herself": "female",
}
LINKING_VERBS = {"be", "look", "seem", "become", "grow", "appear", "sound", "feel", "get", "remain", "turn", "go"}
VALID_WORD = re.compile(r"[a-z]+(?:[- ][a-z]+)*")
FIELDS = ["book", "chapter", "character", "gender", "group", "kind", "voice", "relation", "word", "sentence"]
MENTION_FIELDS = ["book", "chapter", "character", "gender", "group", "kind", "voice", "mentions"]

#--------------------------------
# Small helpers
#--------------------------------
def quote_positions(text):
    """ Character positions of every double quote in paragraph. """
    return [i for i, ch in enumerate(text) if ch == '"']

def in_dialogue(char_index, quotes):
    """ True if the characer at char_index lies between an opening and closing quote. """
    return bisect.bisect_left(quotes, char_index) % 2 == 1

class PronounLinker:
    """ Remember the most recently named character of each gender. """
    def __init__(self, window):
        self.window = window
        self.reset()

    def reset(self):
        self.last = {}

    def saw_name(self, row, sentence_number):
        self.last[row["gender"]] = (row, sentence_number)

    def link(self, gender, sentence_number):
        if gender not in self.last:
            return None
        row, seen_in = self.last[gender]

        return row if sentence_number - seen_in <= self.window else None

#--------------------------------
# Finding mentions
#--------------------------------
def load_characters():
    """ Return a dict: name variant -> that characters row from character.csv. """
    with open(CHARACTERS_CSV, encoding = "utf-8") as f:
        row = list(csv.DictReader(f))

    return {v.strip(): row for row in rows for v in row["variants"].split(";")}

def build_matcher(nlp, variants):
    """ Return a spaCy matcher that finds any name variant in a parsed text. """
    from spacy.matcher import PhraseMatcher

    matcher = PhraseMatcher(nlp.vocab, attr = "ORTH")
    for variant in variants:
        matcher.add(variant, [nlp.make_doc(variant)])

    return matcher

def find_mentions(doc, matcher, variants, linker, sentence_number):
    """ Yield every character mention in a parsed paragraph, in reading order. """
    from spacy.util import filter_spans

    spans = filter_spans([doc[start:end] for _, start, end in matcher(doc)])
    span_at = {span.start: span for span in spans}

    for offset, sent in enumerate(doc.sents):
        number = sentence_number + offset
        skip_until = -1
        for tok in sent:
            if tok.i < skip_until:
                continue
        
            if tok.i in span_at:
                span = span_at[tok.i]
                row = variants[span.text]
                linker.saw_namke(row, number)
                skip_until = span.end
                yield span.root, row["character"], row["gender"], ro["group"], "name"
                continue

            gender = PRONOUNS.get(tok.lower_)
            if gender:
                row = linker.link(gender, number)
                if row:
                    yield tok, row["character"], gender, row["group"], "linked"
                else:
                    yield tok, f"pronoun({gender})", gender, "pronoun", "pronoun"

#--------------------------------
# Following the links from a mention to its describing words
#--------------------------------
def adjectives_of(noun):
    """ Adjectives directly attached to a noun: "bushy hair" -> [bushy]. """
    return [c for c in noun.children if c.dep_ == "amod" and c.pos_ == "ADJ"]

def describe_noun(noun):
    """ For a noun that names the character ("a brilliant witch", "the greasy git"): yield the noun itself and the adjectives on it. """
    yield "noun", noun.lemma_.lower()
    for adj in adjectives_of(noun):
        yield "modifier", adj.lemma_.lower()

def find_descriptions(tok):
    """ Yield (relation, word) pairs for one mention. """
    for child in tok.children:
        if child.dep_ == "appos" and child.pos_ == "NOUN":
            yield from describe_noun(child)
    if tok.dep_ == "appos" and tok.head.pos_ == "NOUN":
        yield from describe_noun(tok.head)

    for adj in adjectives_of(tok):
        yield "modifier", adj.lemma_.lower()

    role_tok = tok
    while role_tok.dep_ == "conj" and role_tok.head is not role_tok:
        role_tok = role_tok.head
    dep, head = role_tok.dep_, role_tok.head

    if dep == "poss":
        if head.pos_ not in ("NOUN", "PROPN"):
            return
        thing = head.lemma_.lower()
        yield "possession", thing

        for adj in adjectives_of(head):
            yield "feature", f"{adj.lemma_.lower()} {thing}"

        if head.dep_ == "nsubj" and head.head.lemma_ in LINKING_VERBS:
            for child in head.head.children:
                if child.dep_ == "acomp" and child.pos_ == "ADJ":
                    yield "feature", f"{child.lemma_.lower()} {thing}"
        return

    if dep in ("nsubj", "nsubjpass"):
        verb = head

        if verb.lemma_ in LINKING_VERBS:
            for child in verb.children:
                if child.dep_ in ("acomp", "attr") and child.pos_ == "ADJ":
                    yield "modifier", child.lemma_.lower()
                    for other in child.conjuncts:  # "clever and bossy" -> bossy too
                        if other.pos_ == "ADJ":
                            yield "modifier", other.lemma_.lower()
                if child.dep_ == "attr" and child.pos_ == "NOUN":
                    yield from describe_noun(child)

        if verb.pos_ == "VERB" and verb.lemma_ != "be":
            yield ("patient" if dep == "nsubjpass" else "agent"), verb.lemma_.lower()

            for adv in verb.children:
                if adv.dep_ == "advmod" and adv.text.lower().endswith("ly") and len(adv.text) > 4:
                    yield "manner", adv.lemma_.lower()
        return

    if dep == "dobj" and head.pos_ == "VERB":
        yield "patient", head.lemma_.lower()

#--------------------------------
# Main
#--------------------------------
def main():
    import spacy

    parser = argparse.ArgumentParser(description = "Extract character descriptions with spaCy. ")
    parser.add_argument("--books", nargs="*", type = int, help = "only process these books, e.g. --books 1 (default: all)")
    parser.add_argument("--model", default = SPACY_MODEL, help = "spaCy model name")
    args = parser.parse_args()

    try:
        nlp = spacy.load(args.model, disable = ["ner"])
    except OSError:
        sys.exit(f"spaCy model {args.model} not found. Run 'python -m spacy download {args.model}'")

    variants = load_characters()
    matcher = build_matcher(nlp, variants)
    linker = PronounLinker(PRONOUN_WINDOW)

    csv.field_size_limit(sys.maxsize)
    with open(CHAPTERS_CSV, encoding = "utf-8") as f:
        chapters = list(csv.DictReader(f))
    if args.books:
        chapters = [c for c in chapters if int(c["book"]) in args.books]

    DESCRIPTIONS_CSV.parent.mkdir(parents = True, exist_ok = True)
    CHARACTER_MENTIONS_CSV.parent.mkdir(parents = True, exist_ok = True)
    mention_counts = Counter()
    started = time.time()
    rows_written = 0

    with open(DESCRIPTIONS_CSV, "w", newline = "", encoding = "utf-8") as f:
        writer = csv.DictWriter(f, fieldnames = FIELDS)
        writer.writeheader()

        for chatper in chapters:
            linker.reset()
            sentence_number = 0
            paragraphs = [p for p in chapter["text"].split("\n\n") if p.strip()]
            for doc in nlp.pipe(paragraphs, batch_size = 64):
                quotes = quote_positions(doc.text)
                mentions = find_mentions(doc, matcher, variants, linker, sentence_number)
                for tok, character, gender, group, kind in mentions:
                    voice = "dialogue" if in_dialogue(tok.idx, quotes) else "narration"
                    mention_counts[(chapter["book"], chapter["chapter"], character, gender, group, kind, voice)] += 1
                    for relation, word in find_descriptions(tok):
                        if not VALID_WORD.fullmatch(word):
                            continue
                        writer.writerow({
                            "book": chapter["book"],
                            "chapter": chapter["chapter"],
                            "character": character, 
                            "gender": gender,
                            "group": group,
                            "kind": kind,
                            "voice": voice,
                            "relation": relation,
                            "word": word,
                            "sentence": tok.sent.text.strip(),
                        })
                        rows_written += 1
                sentence_number += len(list(doc.sents))

            minutes = (time.time() - started) / 60
            print(f"Book {chapter['book']} ch {int(chapter['chapter']):>2}  "f"{chapter['title'][:40]:40}  {rows_written:>7,} rows  {minutes:5.1f} min", flush=True)

    with open(CHARACTER_MENTIONS_CSV, "w", newline = "", encoding = "utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(MENTION_FIELDS)
        for key, n in sorted(mention_counts.items()):
            writer.writerow([*key, n])

    print(f"Done. Wrote {rows_written:,} rows to {DESCRIPTIONS_CSV}")
    print(f"Wrote mention counts to {CHARACTER_MENTIONS_CSV}")

if __name__ == "__main__":
    main()