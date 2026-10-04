import json
import sqlite3
from pathlib import Path
from rfp_intelligence.schemas import Evidence


class Store:
    """SQLite is the authority for active generations and source evidence."""
    def __init__(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "manifest.sqlite"
        with self.connection() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS files (
              bid TEXT, file TEXT, fingerprint TEXT, version TEXT, generation TEXT,
              warnings TEXT, PRIMARY KEY(bid,file));
            CREATE TABLE IF NOT EXISTS chunks (
              id TEXT, generation TEXT, bid TEXT, file TEXT, data TEXT,
              PRIMARY KEY(id,generation));
            """)

    def connection(self):
        return sqlite3.connect(self.path, timeout=60)

    def manifests(self, bid: str) -> dict:
        with self.connection() as db:
            rows = db.execute("SELECT file,fingerprint,version,generation,warnings FROM files WHERE bid=?", (bid,)).fetchall()
        return {r[0]: dict(zip(["fingerprint", "version", "generation", "warnings"], r[1:])) for r in rows}

    def activate(self, bid, file, fingerprint, version, generation, evidence, warnings):
        with self.connection() as db:
            db.executemany("INSERT OR REPLACE INTO chunks VALUES (?,?,?,?,?)",
                           [(e.id, generation, bid, file, e.model_dump_json()) for e in evidence])
            db.execute("INSERT OR REPLACE INTO files VALUES (?,?,?,?,?,?)",
                       (bid, file, fingerprint, version, generation, json.dumps(warnings)))
            db.execute("DELETE FROM chunks WHERE bid=? AND file=? AND generation<>?", (bid, file, generation))

    def remove(self, bid, file):
        with self.connection() as db:
            db.execute("DELETE FROM files WHERE bid=? AND file=?", (bid, file))
            db.execute("DELETE FROM chunks WHERE bid=? AND file=?", (bid, file))

    def evidence(self, bids=None) -> list[Evidence]:
        with self.connection() as db:
            rows = db.execute("SELECT c.data FROM chunks c JOIN files f ON c.bid=f.bid AND c.file=f.file AND c.generation=f.generation").fetchall()
        return [e for row in rows if (e := Evidence.model_validate_json(row[0])) and (not bids or e.bid_id in bids)]

    def active_generations(self) -> list[str]:
        with self.connection() as db:
            return [row[0] for row in db.execute("SELECT DISTINCT generation FROM files")]

    def warnings(self, bids) -> list[str]:
        with self.connection() as db:
            rows = db.execute("SELECT bid,warnings FROM files").fetchall()
        return [w for bid, raw in rows if not bids or bid in bids for w in json.loads(raw)]
