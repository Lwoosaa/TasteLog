"""
Fills in missing keywords for films that timed out during fetch_popular.py.
Run from the project root:
    python scripts/fill_missing_keywords.py
"""

import sys
import json
import time
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.database import get_connection

API_KEY   = "8b07a445be44564ab9eefccc5183c685"
TMDB_BASE = "https://api.themoviedb.org/3"


def get_missing() -> list[tuple]:
    # Films where keywords column is NULL (timeout) but tmdb_id is known.
    con = get_connection()
    rows = con.execute(
        "SELECT name, year, tmdb_id FROM tmdb_cache WHERE keywords IS NULL AND tmdb_id IS NOT NULL"
    ).fetchall()
    con.close()
    return rows


def fill():
    missing = get_missing()
    print(f"{len(missing)} films with missing keywords.")

    if not missing:
        print("Nothing to do.")
        return

    con = get_connection()
    for i, (name, year, tmdb_id) in enumerate(missing, 1):
        try:
            r = requests.get(
                f"{TMDB_BASE}/movie/{tmdb_id}/keywords",
                params={"api_key": API_KEY},
                timeout=15,
            )
            r.raise_for_status()
            keywords = [k["name"] for k in r.json().get("keywords", [])]
            con.execute(
                "UPDATE tmdb_cache SET keywords = ? WHERE name = ? AND year = ?",
                (json.dumps(keywords), name, year),
            )
            if i % 50 == 0:
                con.commit()
                print(f"  {i}/{len(missing)} done", end="\r")
            time.sleep(0.1)
        except Exception as e:
            print(f"\n  Skipped {name} ({year}): {e}")
            time.sleep(3)

    con.commit()
    con.close()
    print(f"\nDone. {len(missing)} films updated.")


if __name__ == "__main__":
    fill()
