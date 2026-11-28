"""Build data/army.db from the scraped Wahapedia JSON in data/raw/.

Run offline whenever the raw data changes (the Dockerfile also runs it during the image build):
    cd backend && python build_db.py

Tables:
    units          one row per datasheet, used by the army builder (points, faction, keywords)
    unit_limits    copies allowed per datasheet name for each battle size (core rules 25.03)
    chunks         text passages for the Servitor to retrieve (datasheets, detachments, rules)
    chunk_vectors  sqlite-vec index of chunk embeddings; chunk_id = chunks.id
    meta           build info, including which embedding model was used
"""

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import sqlite_vec
from sentence_transformers import SentenceTransformer

DATA_DIR = Path(__file__).with_name("data")
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "army.db"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
CHUNK_WORDS = 180  # MiniLM truncates at 256 word pieces, roughly 190 words
CHUNK_OVERLAP = 30

# "YOUR UNIT COSTS 5 models 115 10 models 230": first tier only, smallest size first
COST_BLOCK = re.compile(r"YOUR (?:UNIT|1ST[A-Z0-9 ]*UNITS?) COSTS?\s+(.*?)(?=YOUR |KEYWORDS:|$)")
SIZE_COST = re.compile(r"(\d+) models? (\d+)")
KEYWORDS = re.compile(r"KEYWORDS: (.*?) FACTION KEYWORDS:")
# a row of the Select Battle Size table: "STRIKE FORCE 2000 3 4 3" (name, points, DP, enhancements, unit limit)
BATTLE_SIZE_ROW = re.compile(r"([A-Z][A-Z ]+?) (\d{3,4}) (\d+) (\d+) (\d+)")

SCHEMA = f"""
CREATE TABLE units (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    faction TEXT NOT NULL,
    points INTEGER NOT NULL,   -- cost of the smallest unit size
    sizes TEXT NOT NULL,       -- JSON: {{"5": 115, "10": 230}}
    keywords TEXT NOT NULL,    -- JSON list
    source TEXT NOT NULL
);
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,        -- datasheet, detachment, enhancement, stratagem, faction_page, rule
    faction TEXT,              -- NULL for core rules
    name TEXT NOT NULL,
    unit_id TEXT REFERENCES units(id),
    source TEXT NOT NULL,
    text TEXT NOT NULL
);
CREATE VIRTUAL TABLE chunk_vectors USING vec0(
    chunk_id INTEGER PRIMARY KEY,
    embedding FLOAT[{EMBEDDING_DIM}] distance_metric=cosine,
    faction TEXT,              -- '' for core rules
    kind TEXT
);
CREATE TABLE unit_limits (
    points INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    unit_limit INTEGER NOT NULL  -- doubled for BATTLELINE / DEDICATED TRANSPORT; EPIC HERO is always 1
);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def parse_points(text):
    """Return {model count: points} for the first cost tier, or None."""
    # the scraped text repeats headings ("YOUR UNIT COSTS YOUR UNIT COSTS ..."), so skip empty ones
    for block in COST_BLOCK.finditer(text):
        sizes = {int(models): int(points) for models, points in SIZE_COST.findall(block.group(1))}
        if sizes:
            return sizes
    return None


def parse_keywords(record):
    # older spider output has no "keywords" field, so fall back to the datasheet text
    if "keywords" in record:
        return record["keywords"].get("keywords", [])
    match = KEYWORDS.search(record["text"])
    return [word.strip() for word in match.group(1).split(";")] if match else []


def parse_unit_limits(text):
    """Return [(points, battle size name, unit limit)] from the Select Battle Size rule text."""
    table = text.split("Unit Limit*", 1)[1].split("*", 1)[0]
    return [(int(points), name.title(), int(unit_limit))
            for name, points, _, _, unit_limit in BATTLE_SIZE_ROW.findall(table)]


def split_words(text):
    """Split long text into overlapping windows small enough for the embedding model."""
    words = text.split()
    if len(words) <= CHUNK_WORDS:
        return [text]
    step = CHUNK_WORDS - CHUNK_OVERLAP
    return [" ".join(words[start:start + CHUNK_WORDS]) for start in range(0, len(words) - CHUNK_OVERLAP, step)]


def datasheet_text(text):
    # every datasheet ends with the same list of core stratagem names; it adds noise to retrieval
    return text.split(" STRATAGEMS ", 1)[0]


def read_raw():
    """Return (units, chunks, unit limits) built from every JSON file in data/raw/."""
    units, chunks, unit_limits, seen_text = [], [], [], set()

    def add_chunks(kind, faction, name, source, text, unit_id=None):
        for part in split_words(text):
            if part in seen_text:  # tooltips repeat the core rules on every faction page
                continue
            seen_text.add(part)
            chunks.append((kind, faction, name, unit_id, source, part))

    for path in sorted(RAW_DIR.glob("*.json")):
        for record in json.loads(path.read_text()):
            if "heading" in record:  # core rules file
                if record["heading"].startswith("Select Battle Size"):
                    unit_limits = parse_unit_limits(record["text"])
                add_chunks("rule", None, record["heading"], record["source"], record["text"])
                continue
            faction = record.get("chapter_context") or record["faction"]
            kind = record["kind"]
            if kind == "datasheet":
                sizes = parse_points(record["text"])
                unit_id = path.stem + "/" + record["source"].rstrip("/").rsplit("/", 1)[-1]
                if sizes:
                    units.append((unit_id, record["name"], faction, min(sizes.values()), json.dumps(sizes),
                                  json.dumps(parse_keywords(record)), record["source"]))
                else:
                    print(f"  no points found, not buildable: {record['name']} ({path.name})")
                    unit_id = None
                add_chunks("datasheet", faction, record["name"], record["source"],
                           datasheet_text(record["text"]), unit_id)
            elif kind == "detachment":
                name = record["detachment"]
                if record.get("detachment_rule"):
                    add_chunks("detachment", faction, name, record["source"], record["detachment_rule"]["text"])
                for item in record.get("enhancements", []):
                    add_chunks("enhancement", faction, f"{name}: {item['name']}", record["source"], item["text"])
                for item in record.get("stratagems", []):
                    add_chunks("stratagem", faction, f"{name}: {item['name']}", record["source"],
                               f"{item['name']} {item['cost']} {item['text']}")
            elif kind == "faction_page":
                add_chunks("faction_page", faction, faction, record["source"], record["text"])
            elif kind == "tooltip":
                add_chunks("rule", None, record["name"], record["source"], record["text"])
    return units, chunks, unit_limits


def build():
    print(f"Reading {RAW_DIR}")
    units, chunks, unit_limits = read_raw()
    if not unit_limits:
        raise SystemExit("Select Battle Size table not found in the core rules; unit limits can't be set")
    print(f"  {len(units)} units, {len(chunks)} chunks, unit limits {unit_limits}")

    print(f"Embedding with {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME, device="cpu")
    # prefix each passage with its name so short chunks still say what they are about
    embeddings = model.encode([f"{name}: {text}" for _, _, name, _, _, text in chunks],
                              batch_size=64, normalize_embeddings=True, show_progress_bar=True)

    tmp_path = DB_PATH.with_suffix(".db.tmp")
    tmp_path.unlink(missing_ok=True)
    db = sqlite3.connect(tmp_path)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    db.executescript(SCHEMA)
    db.executemany("INSERT INTO units VALUES (?, ?, ?, ?, ?, ?, ?)", units)
    db.executemany("INSERT INTO unit_limits VALUES (?, ?, ?)", unit_limits)
    db.executemany("INSERT INTO chunks (kind, faction, name, unit_id, source, text) VALUES (?, ?, ?, ?, ?, ?)",
                   chunks)
    db.executemany("INSERT INTO chunk_vectors (chunk_id, embedding, faction, kind) VALUES (?, ?, ?, ?)",
                   # vec0 filter columns can't hold NULL, so core rules get '' as their faction
                   [(chunk_id, sqlite_vec.serialize_float32(vector), chunk[1] or "", chunk[0])
                    for chunk_id, (chunk, vector) in enumerate(zip(chunks, embeddings), start=1)])
    db.executemany("INSERT INTO meta VALUES (?, ?)", [
        ("embedding_model", MODEL_NAME),
        ("built_at", datetime.now(timezone.utc).isoformat(timespec="seconds")),
    ])
    db.commit()
    db.execute("VACUUM")
    db.close()
    tmp_path.replace(DB_PATH)  # swap in only after a complete build
    print(f"Wrote {DB_PATH} ({DB_PATH.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    build()
