""" Configuration file for the visualization project. """

from pathlib import Path

#--------------------------------
# Root folder
#--------------------------------
ROOT = Path(__file__).resolve().parent

#--------------------------------
# Data folders
#--------------------------------
RAW_DIR = ROOT / "data" / "raw"
INTERIM_DIR = ROOT / "data" / "interim"
PROCESSED_DIR = ROOT / "data" / "processed"

# Hand made inputs
RESOURCES_DIR = ROOT / "resources"
LEXICON_DIR = RESOURCES_DIR / "lexicon"
CHARACTER_CSV = RESOURCES_DIR / "characters.csv"

#--------------------------------
# Files produced by each pipeline step
#--------------------------------
# 1_chapters.py
CHAPTERS_DIR = INTERIM_DIR / "chapters"
CHAPTERS_CSV = INTERIM_DIR / "chapters.csv"

# 2_characters.py
CHARACTERS_CSV = RESOURCES_DIR / "characters.csv"
CHARACTER_CANDIDATES_CSV = INTERIM_DIR / "character_candidates.csv"

# 3_mentions.py
MENTIONS_CSV = PROCESSED_DIR / "mentions.csv"
COOCCURRENCES_CSV = PROCESSED_DIR / "cooccurrences.csv"

# 4_extract.py
DESCRIPTIONS_CSV = INTERIM_DIR / "descriptions.csv"

# 5_aggregate.py
WORD_COUNTS_CSV = PROCESSED_DIR / "word_counts.csv"
DISTINCTIVE_WORDS_CSV = PROCESSED_DIR / "distinctive_words.csv"
THEMES_CSV = PROCESSED_DIR / "themes.csv"
PROFILES_CSV = PROCESSED_DIR / "character_profiles.csv"
CHARACTER_TOTALS_CSV = PROCESSED_DIR / "character_totals.csv"

# validation.py
VALIDATION_CSV = INTERIM_DIR / "validation_sample.csv"

#--------------------------------
# Settings
#--------------------------------
SPACY_MODEL = "en_core_web_sm"
PRONOUN_WINDOW = 1
USE_LINKED_PRONOUNS = True
LEAVE_OUT = ["Harry Potter", "Hermione Granger"]
MAX_CHARACTERS = 100
MIN_NAME_COUNT = 5
MIN_CHARACTER_COUNT = 20
MAX_CHARACTER_COUNT = 100
PROFILE_TOP_WORDS = 15
MIN_PROFILE_MENTIONS = 30
VALIDATION_SAMPLE_SIZE = 70
RANDOM_SEED = 42
MIN_WORD_COUNT = 5
