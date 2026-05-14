"""
One-time script to pre-populate tmdb_cache with the top 5000 most popular films
including genre IDs and keywords for each film.

Run from the project root:
    python scripts/fetch_popular.py

Phase 1 — 250 discover pages  (~30s)
Phase 2 — keywords for 5000 films via /movie/{id}?append_to_response=keywords (~8 min)

After this, enrich_df() in tmdb.py will find almost all films in cache
without making any API calls.
"""

import sys
import json
import time
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.database import get_connection
from src.tmdb import init_cache_table, save_genre_map

API_KEY    = "8b07a445be44564ab9eefccc5183c685"
TMDB_BASE  = "https://api.themoviedb.org/3"
TOTAL_PAGES = 250  # 250 × 20 = 5000 films


def get(url, params={}):
    params["api_key"] = API_KEY
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


# ── Phase 0: genre map ────────────────────────────────────────────────────────

def fetch_genre_map():
    print("Fetching genre map...")
    data = get(f"{TMDB_BASE}/genre/movie/list", {"language": "en-US"})
    save_genre_map(data["genres"])
    print(f"  {len(data['genres'])} genres saved.")


# ── Phase 1: discover pages ───────────────────────────────────────────────────

def fetch_discover_pages() -> list[dict]:
    # Returns a list of {id, title, year, vote_average, vote_count, release_date, genre_ids}
    all_movies = []
    print(f"\nPhase 1 — fetching {TOTAL_PAGES} discover pages...")

    for page in range(1, TOTAL_PAGES + 1):
        try:
            data = get(f"{TMDB_BASE}/discover/movie", {
                "sort_by": "popularity.desc",
                "page": page,
                "language": "en-US",
            })
            for m in data.get("results", []):
                if not m.get("title") or not m.get("release_date"):
                    continue
                all_movies.append({
                    "id":           m["id"],
                    "name":         m["title"],
                    "year":         int(m["release_date"][:4]),
                    "vote_average": m.get("vote_average"),
                    "vote_count":   m.get("vote_count"),
                    "release_date": m.get("release_date"),
                    "genre_ids":    m.get("genre_ids", []),
                })
            print(f"  Page {page}/{TOTAL_PAGES} — {len(all_movies)} films", end="\r")
            time.sleep(0.1)
        except Exception as e:
            print(f"\n  Error on page {page}: {e} — retrying in 5s")
            time.sleep(5)

    print(f"\n  Done. {len(all_movies)} films collected.")
    return all_movies


def save_basic_metadata(movies: list[dict]):
    # Saves everything except keywords (filled in phase 2).
    con = get_connection()
    con.executemany(
        """
        INSERT OR IGNORE INTO tmdb_cache
            (name, year, tmdb_id, vote_average, vote_count, release_date, genre_ids)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (m["name"], m["year"], m["id"], m["vote_average"],
             m["vote_count"], m["release_date"], json.dumps(m["genre_ids"]))
            for m in movies
        ],
    )
    con.commit()
    con.close()


# ── Phase 2: keywords ─────────────────────────────────────────────────────────

def fetch_all_keywords(movies: list[dict]):
    print(f"\nPhase 2 — fetching keywords for {len(movies)} films...")
    con = get_connection()

    for i, m in enumerate(movies, 1):
        try:
            data = get(f"{TMDB_BASE}/movie/{m['id']}/keywords")
            keywords = [k["name"] for k in data.get("keywords", [])]
            con.execute(
                "UPDATE tmdb_cache SET keywords = ? WHERE name = ? AND year = ?",
                (json.dumps(keywords), m["name"], m["year"]),
            )
            # Commit in batches of 100 to avoid holding a long transaction.
            if i % 100 == 0:
                con.commit()
                print(f"  {i}/{len(movies)} keywords fetched", end="\r")
            time.sleep(0.08)
        except Exception as e:
            print(f"\n  Error for {m['name']} ({m['year']}): {e}")
            time.sleep(3)

    con.commit()
    con.close()
    print(f"\n  Done. Keywords saved for {len(movies)} films.")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_cache_table()
    fetch_genre_map()
    movies = fetch_discover_pages()
    save_basic_metadata(movies)
    fetch_all_keywords(movies)
    print("\nAll done. tmdb_cache is ready.")
