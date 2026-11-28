"""Read-only access to data/army.db (built by build_db.py)."""

import json
import sqlite3
from functools import cache
from pathlib import Path

import sqlite_vec

DB_PATH = Path(__file__).with_name("data") / "army.db"


@cache
def connect():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"{DB_PATH} not found; run `python build_db.py` in backend/ first")
    # one shared read-only connection; NiceGUI handlers and FastAPI sync routes run on different threads
    db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    return db


def load_units():
    """Return every buildable unit as a dict, sorted by faction and name."""
    rows = connect().execute("SELECT * FROM units ORDER BY faction, name").fetchall()
    return [{**row, "sizes": {int(size): points for size, points in json.loads(row["sizes"]).items()},
             "keywords": json.loads(row["keywords"])} for row in rows]


def load_unit_limits():
    """Return {battle size points: copies allowed per datasheet name}."""
    return dict(connect().execute("SELECT points, unit_limit FROM unit_limits").fetchall())


@cache
def embedding_model():
    # imported lazily: loading torch takes seconds and only the Servitor needs it
    from sentence_transformers import SentenceTransformer
    name = connect().execute("SELECT value FROM meta WHERE key = 'embedding_model'").fetchone()[0]
    return SentenceTransformer(name, device="cpu")


def search(query, faction=None, kinds=None, limit=8):
    """Return the chunks closest to query, optionally limited to one faction (core rules always included)."""
    vector = embedding_model().encode(query, normalize_embeddings=True)
    sql = "SELECT chunk_id, distance FROM chunk_vectors WHERE embedding MATCH ? AND k = ?"
    params = [sqlite_vec.serialize_float32(vector), limit]
    if faction:
        sql += " AND faction IN (?, '')"
        params.append(faction)
    if kinds:
        sql += f" AND kind IN ({', '.join('?' * len(kinds))})"
        params.extend(kinds)
    db = connect()
    matches = db.execute(sql, params).fetchall()
    results = []
    for match in matches:
        chunk = db.execute("SELECT * FROM chunks WHERE id = ?", (match["chunk_id"],)).fetchone()
        results.append({**chunk, "distance": match["distance"]})
    return results
