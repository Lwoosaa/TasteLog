import json
import requests
from src.database import get_connection

TMDB_BASE = "https://api.themoviedb.org/3"


def init_cache_table():
    # Creates tables if they don't exist. Uses IF NOT EXISTS so re-uploading
    # Spotify/Letterboxd data never wipes the TMDB cache.
    con = get_connection()
    con.execute("""
        CREATE TABLE IF NOT EXISTS tmdb_cache (
            name         TEXT,
            year         INTEGER,
            tmdb_id      INTEGER,
            vote_average REAL,
            vote_count   INTEGER,
            release_date TEXT,
            genre_ids    TEXT,
            keywords     TEXT,
            PRIMARY KEY (name, year)
        )
    """)
    # genre_map stores ID → name so we never need to call /genre/movie/list again.
    con.execute("""
        CREATE TABLE IF NOT EXISTS genre_map (
            id   INTEGER PRIMARY KEY,
            name TEXT
        )
    """)
    # Safely add new columns to existing tables from older schema versions.
    for col, coltype in [
        ("tmdb_id", "INTEGER"),
        ("genre_ids", "TEXT"),
        ("keywords", "TEXT"),
    ]:
        try:
            con.execute(f"ALTER TABLE tmdb_cache ADD COLUMN {col} {coltype}")
        except Exception:
            pass  # column already exists
    con.commit()
    con.close()


def save_genre_map(genres: list[dict]):
    # genres = [{"id": 18, "name": "Drama"}, ...]
    con = get_connection()
    con.executemany(
        "INSERT OR IGNORE INTO genre_map (id, name) VALUES (?, ?)",
        [(g["id"], g["name"]) for g in genres],
    )
    con.commit()
    con.close()


def genre_ids_to_names(genre_ids_json: str) -> str:
    # Converts a stored JSON array of IDs to a comma-separated name string.
    if not genre_ids_json:
        return ""
    ids = json.loads(genre_ids_json)
    if not ids:
        return ""
    placeholders = ",".join("?" * len(ids))
    con = get_connection()
    rows = con.execute(
        f"SELECT name FROM genre_map WHERE id IN ({placeholders})", ids
    ).fetchall()
    con.close()
    return ", ".join(r[0] for r in rows)


def _search_api(name: str, year: int, api_key: str) -> dict | None:
    # Returns the top TMDB search result for a given title + year.
    r = requests.get(
        f"{TMDB_BASE}/search/movie",
        params={"query": name, "year": year, "api_key": api_key, "language": "en-US"},
        timeout=10,
    )
    r.raise_for_status()
    results = r.json().get("results", [])
    return results[0] if results else None


def _fetch_details(tmdb_id: int, api_key: str) -> dict:
    # append_to_response=keywords fetches keywords in the same request,
    # saving one extra API call per film.
    r = requests.get(
        f"{TMDB_BASE}/movie/{tmdb_id}",
        params={"api_key": api_key, "append_to_response": "keywords", "language": "en-US"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def _read_cache(name: str, year: int) -> dict | None:
    con = get_connection()
    cur = con.execute(
        """
        SELECT vote_average, vote_count, release_date, genre_ids, keywords
        FROM tmdb_cache WHERE name = ? AND year = ?
        """,
        (name, year),
    )
    row = cur.fetchone()
    con.close()
    if row:
        return {
            "vote_average": row[0],
            "vote_count":   row[1],
            "release_date": row[2],
            "genre_ids":    row[3],
            "keywords":     row[4],
        }
    return None


def _write_cache(name, year, tmdb_id, vote_average, vote_count, release_date, genre_ids, keywords):
    con = get_connection()
    con.execute(
        """
        INSERT OR REPLACE INTO tmdb_cache
            (name, year, tmdb_id, vote_average, vote_count, release_date, genre_ids, keywords)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (name, year, tmdb_id, vote_average, vote_count, release_date,
         json.dumps(genre_ids) if genre_ids is not None else None,
         json.dumps(keywords)  if keywords  is not None else None),
    )
    con.commit()
    con.close()


def get_movie_data(name: str, year: int, api_key: str) -> dict | None:
    # Cache-first: avoids API calls for films already stored locally.
    cached = _read_cache(name, year)
    if cached:
        return cached

    # Search → details (2 API calls for uncached films).
    result = _search_api(name, year, api_key)
    if not result:
        _write_cache(name, year, None, None, None, None, None, None)
        return None

    tmdb_id = result["id"]
    details = _fetch_details(tmdb_id, api_key)

    genre_ids = [g["id"] for g in details.get("genres", [])]
    keywords  = [k["name"] for k in details.get("keywords", {}).get("keywords", [])]

    _write_cache(
        name, year, tmdb_id,
        details.get("vote_average"),
        details.get("vote_count"),
        details.get("release_date"),
        genre_ids,
        keywords,
    )
    return _read_cache(name, year)


def enrich_df(df, api_key: str, name_col: str, year_col: str) -> None:
    # Mutates df in-place, appending TMDB Puan, Oy Sayısı, Yayın Tarihi, Tür, Keywords.
    ratings, votes, releases, genres, kws = [], [], [], [], []

    for _, row in df.iterrows():
        data = get_movie_data(str(row[name_col]), int(row[year_col]), api_key)
        if data:
            ratings.append(data.get("vote_average"))
            votes.append(data.get("vote_count"))
            releases.append(data.get("release_date"))
            genres.append(genre_ids_to_names(data.get("genre_ids")))
            raw_kw = data.get("keywords")
            kws.append(", ".join(json.loads(raw_kw)) if raw_kw else "")
        else:
            ratings.append(None)
            votes.append(None)
            releases.append(None)
            genres.append("")
            kws.append("")

    df["TMDB Puan"]    = ratings
    df["Oy Sayısı"]    = votes
    df["Yayın Tarihi"] = releases
    df["Tür"]          = genres
    df["Keywords"]     = kws
