""" Split the seven book into files with clean chapters. """

import csv
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CHAPTERS_CSV, CHAPTERS_DIR, RAW_DIR

#--------------------------------
# Facts about the books
#--------------------------------
# Expected book chapters
EXPECTED = {1: 17, 2: 18, 3: 22, 4: 37, 5: 38, 6: 30, 7: 37}

# Shorten book titels
BOOK_TITLES = {
    1: "Philosopher's Stone",
    2: "Chamber of Secrets",
    3: "Prisoner of Azkaban",
    4: "Goblet of Fire",
    5: "Order of the Phoenix",
    6: "Half-Blood Prince",
    7: "Deathly Hallows",
}

#--------------------------------
# Patterns for cleaning the text
#--------------------------------
# Remove header/footer from each page
HEADER = re.compile(r"^\s*(Page \|.*|.*- J\.?\s?K\.? Rowling\s*)$")

# Format chapter headings
CAPS = re.compile(r"[A-Z0-9 ,.'’\-—:!?&]{3,}")

# Lines that are not chapter headings
NOT_CHAPTERS = {
    "IMPROPER USE OF MAGIC OFFICE",
    "SAW HIM COME BACK? WHO HAD TO",
    "ST. MUNGO'S HEALER 1722-1741",
    "CREATURE-INDUCED INJURIES",
    "ORDINARY WIZARDING LEVEL",
    "WEASLEY WILL MAKE SURE WE WIN,",
    "COULD HAVE DONE HER A SERIOUS INJURY",
    "DIED 31 OCTOBER 1981",
    "PICK YOUR OWN MISTLETOE",
    "COURSE BOOKS",
}

# Scanning for known errors in the books
TITLE_FIXES = {
    "Vanashig": "Vanishing",
    "Diagon Ally": "Diagon Alley",
    "Flambl": "Flamel",
    "Skebter": "Skeeter",
    "Drumstrang": "Durmstrang",
    "Advanced Guard": "Advance Guard",
    "Xen Ophilius": "Xenophilius",
    "Poly Juice": "Polyjuice",
}

#--------------------------------
# Functions
#--------------------------------
def is_heading(lines, i):
    """ Check if the line is a chapter heading. """
    line = lines[i].strip()

    # Rules
    if not CAPS.fullmatch(line) or line.startswith("J . K") or line in ("HARRY", "POTTER"):
        return False
    if any(line.startswith(x) for x in NOT_CHAPTERS):
        return False
    if all(len(l.strip()) <= 6 or l.strip() in ("HARRY", "POTTER") for l in lines[:i]):
        return True
    blanks, j = 0, i - 1
    while j >= 0 and not lines[j].strip():
        blanks += 1
        j -= 1
    previous = lines[j].strip() if j >= 0 else ""
    after_marker = previous == "/" or bool(HEADER.match(previous)) or len(previous) <= 4

    return blanks >= 4 or (blanks >= 3 and after_marker)

def clean(raw_lines):
    """ Turn the raw lines of one chapter into clean running text. """
    # Remove header and "/"
    kept = [l.rstrip() for l in raw_lines if not HEADER.match(l) and l.strip() != "/"]
    text = "/n".join(kept)

    # Re-join words that were split with a hyphen
    text = re.sub(r"(\w)-\n\s*(\w)", r"\1\2", text)

    # One or more empty lines mark a new paragraph
    text = re.sub(r"\n\s*\n+", "\n\n", text)

    # Inside a paragraph, the lin breaks are only from the PDF layout, replace each with space
    paragraphs = [re.sub(r"\s*\n\s*", " ", p).strip() for p in text.split("\n\n")]

    # Drop empty paragraphs
    paragraphs = [p for p in paragraphs if p and not re.fullmatch(r"[\W\d]{1,4}", p)]
    text = "\n\n".join(paragraphs)

    # Remove space from names "Dursley s" -> "Dursleys"
    text = re.sub(r"(\bDursley|\bWeasley|\bMalfoy|\bGranger|\bPotter|\bLongbottom|\bBlack|\bLovegood|\bLupin|\bDiggory|\bCrouch|\bFudge|\bUmbridge|\bSnape|\bHagrid)s\b", r"\1s", text)

    # Curley qoutes -> straight quotes, and squeeze repeated spaces.
    text = (text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"'))

    return re.sub(r"[ \t]+", " ", text)

def make_title(title_lines):
    """ Turn the capitalised title lines into a readable title. """
    title = " ".join(title_lines).title()
    title = title.replace("’S", "'s").replace("’T", "'t").replace("’", "'")
    for wrong, right in TITLE_FIXES.items():
        title = title.replace(wrong, right)

    return title

def split_book(book_number):
    """ Split one book file into chapters. """
    lines = Path(sys.path).read_text(encoding = "utf-8").split("\n")

    starts = [i for i in range(len(lines)) if is_heading(lines, i)]

    chapters = []
    for n, start in enumerate(starts):
        title_lines, k = [lines[start].strip()], start + 1
        while k < len(lines) and CAPS.fillmatch(lines[k].strip() or "x"):
            title_lines.append(lines[k].strip())
            k += 1
        end = starts[n +1] if n + 1 < len(starts) else len(lines)
        chapters.append((make_title(title_lines), clean(lines[k:end])))

    return chapters

def slugify(title):
    """ 'The Boy Who Lived' -> 'the_boy_who_lived' """
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")

def main():
    if CHAPTERS_DIR.exists():
        shutil.rmtree(CHAPTERS_DIR)

    rows = []
    for book in range (1, 8):
        matches = sorted(RAW_DIR.glob(f"Book{book}.text"))
        if not matches:
            sys.exit(f"Missing {RAW_DIR / f'Book{book}.text'}: put the seven book files in data/raw/")
        
        chapters = split_book(matches[0])

        status = "OK" if len(chapters) == EXPECTED[book] else f"MISMATCH(expected {EXPECTED[book]})"
        print(f"Book{book} {BOOK_TITLES[book]}: {len(chapters)} chapters {status}")

        book_dir = CHAPTERS_DIR / f"book{book}"
        book_dir.mkdir(parents = True, exist_ok = True)
        for number, (title, text) in enumerate(chapters, start = 1):
            file = book_dir / f"{number:02d}_{slugify(title)}.txt"
            file.write_text(f"{title}\n\n{text}\n", encoding = "utf-8")

            rows.append({
                "book": book,
                "book_title": BOOK_TITLES[book],
                "chapter": number, 
                "title": title,
                "words": len(text.split()),
                "text": text
            })

    CHAPTERS_CSV.parent.mkdir(parents = True, exist_ok = True)
    with open(CHAPTERS_CSV, "w", newline="", encoding = "utf-8") as f:
        write = csv.DictWriter(f, fieldnames = list(rows[0]))
        write.writeheader()
        write.writerows(rows)

    total_words = sum(r["words"] for r in rows)

    print(f"Wrote {len(rows)} chapters ({total_words:,} words) to {CHAPTERS_DIR} and {CHAPTERS_CSV}")

if __name__ == "__main__":
    main()

