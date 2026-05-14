import sqlite3
import pandas as pd
from pathlib import Path

# DB file lives two levels up from src/, next to the app/ folder.
DB_PATH = Path(__file__).parent.parent / "db" / "musicboxd.db"


def get_connection() -> sqlite3.Connection:
    # Creates the db/ directory on first run so the user never has to do it manually.
    DB_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(DB_PATH)


def build_database(spotify_df: pd.DataFrame, letterboxd: dict = None):
    # We use if_exists="replace" so re-uploading a ZIP always gives a clean slate
    # instead of appending duplicates to existing tables.
    con = get_connection()

    # Raw play-by-play records — every filtered listen becomes one row.
    spotify_df.to_sql("plays", con, if_exists="replace", index=False)

    # Pre-aggregated artist stats so the rankings page doesn't re-scan the full plays table.
    artist_stats = (
        spotify_df.groupby("artist")
        .agg(
            total_plays=("track", "count"),
            total_minutes=("minutes_played", "sum"),
            unique_tracks=("track", "nunique"),
        )
        .reset_index()
    )
    artist_stats.to_sql("artist_stats", con, if_exists="replace", index=False)

    # Monthly rollup used by the trend chart — cheaper than grouping plays on every render.
    monthly = (
        spotify_df.groupby("year_month")
        .agg(
            total_plays=("track", "count"),
            total_minutes=("minutes_played", "sum"),
            unique_artists=("artist", "nunique"),
            unique_tracks=("track", "nunique"),
        )
        .reset_index()
    )
    monthly.to_sql("monthly_stats", con, if_exists="replace", index=False)

    # Letterboxd data is optional — the app works fine with only Spotify.
    # diary and watched_list are kept as separate tables because they carry
    # different fields: diary has rating/rewatch, watched_list only has a date.
    if letterboxd:
        if "diary" in letterboxd:
            letterboxd["diary"].to_sql("diary", con, if_exists="replace", index=False)
        if "watched" in letterboxd:
            letterboxd["watched"].to_sql("watched_list", con, if_exists="replace", index=False)

    con.commit()
    con.close()


# Single helper so every query function opens and closes the connection the same way.
def query(sql: str, params=()) -> pd.DataFrame:
    con = get_connection()
    df = pd.read_sql_query(sql, con, params=params)
    con.close()
    return df


# --- Range-based query functions ---
# All queries accept ISO date strings (YYYY-MM-DD) so the caller can pass
# any period — week, month, year, or custom — without the DB layer caring.

def available_date_range() -> tuple[str, str]:
    # Used to clamp the sidebar date pickers to dates that actually exist in the data.
    df = query("SELECT MIN(date) as min_date, MAX(date) as max_date FROM plays")
    return df["min_date"].iloc[0], df["max_date"].iloc[0]


def overview_by_range(date_from: str, date_to: str) -> pd.DataFrame:
    # Four headline numbers shown in the metric cards at the top of the page.
    return query(
        """
        SELECT COUNT(*) as total_plays,
               ROUND(SUM(minutes_played)) as total_minutes,
               COUNT(DISTINCT artist) as unique_artists,
               COUNT(DISTINCT track) as unique_tracks
        FROM plays
        WHERE date >= ? AND date <= ?
        """,
        (date_from, date_to),
    )


def top_artists_by_range(date_from: str, date_to: str, limit: int = 10) -> pd.DataFrame:
    # Play count is the primary sort key; minutes is included so the bar chart
    # can encode it as color without a second query.
    return query(
        """
        SELECT artist, COUNT(*) as plays, ROUND(SUM(minutes_played)) as minutes
        FROM plays
        WHERE date >= ? AND date <= ?
        GROUP BY artist
        ORDER BY plays DESC
        LIMIT ?
        """,
        (date_from, date_to, limit),
    )


def top_tracks_by_range(date_from: str, date_to: str, limit: int = 10) -> pd.DataFrame:
    # GROUP BY track + artist together to avoid collisions when two artists
    # have songs with the same title.
    return query(
        """
        SELECT track, artist, COUNT(*) as plays, ROUND(SUM(minutes_played)) as minutes
        FROM plays
        WHERE date >= ? AND date <= ?
        GROUP BY track, artist
        ORDER BY plays DESC
        LIMIT ?
        """,
        (date_from, date_to, limit),
    )


def top_albums_by_range(date_from: str, date_to: str, limit: int = 10) -> pd.DataFrame:
    # Spotify's extended history includes album name per play, so no API call needed.
    # NULL/empty album values are filtered out — they appear for local files or podcasts.
    return query(
        """
        SELECT album, artist, COUNT(*) as plays, ROUND(SUM(minutes_played)) as minutes
        FROM plays
        WHERE date >= ? AND date <= ?
          AND album IS NOT NULL AND album != ''
        GROUP BY album, artist
        ORDER BY plays DESC
        LIMIT ?
        """,
        (date_from, date_to, limit),
    )


def listening_by_hour_range(date_from: str, date_to: str) -> pd.DataFrame:
    # Hour values (0–23) come from the Istanbul-timezone timestamp set during parsing.
    return query(
        """
        SELECT hour, COUNT(*) as plays
        FROM plays
        WHERE date >= ? AND date <= ?
        GROUP BY hour
        ORDER BY hour
        """,
        (date_from, date_to),
    )


def all_artists_by_range(date_from: str, date_to: str) -> pd.DataFrame:
    # Full ranking without a LIMIT — the rankings section shows every artist
    # in a scrollable table so the user can explore beyond the top 10.
    return query(
        """
        SELECT artist,
               COUNT(*) as plays,
               ROUND(SUM(minutes_played)) as minutes,
               COUNT(DISTINCT track) as unique_tracks
        FROM plays
        WHERE date >= ? AND date <= ?
        GROUP BY artist
        ORDER BY plays DESC
        """,
        (date_from, date_to),
    )


def all_albums_by_range(date_from: str, date_to: str) -> pd.DataFrame:
    return query(
        """
        SELECT album, artist,
               COUNT(*) as plays,
               ROUND(SUM(minutes_played)) as minutes,
               COUNT(DISTINCT track) as unique_tracks
        FROM plays
        WHERE date >= ? AND date <= ?
          AND album IS NOT NULL AND album != ''
        GROUP BY album, artist
        ORDER BY plays DESC
        """,
        (date_from, date_to),
    )


def all_tracks_by_range(date_from: str, date_to: str) -> pd.DataFrame:
    return query(
        """
        SELECT track, artist, album,
               COUNT(*) as plays,
               ROUND(SUM(minutes_played)) as minutes
        FROM plays
        WHERE date >= ? AND date <= ?
        GROUP BY track, artist
        ORDER BY plays DESC
        """,
        (date_from, date_to),
    )


def diary_by_range(date_from: str, date_to: str) -> pd.DataFrame:
    # Filters on watched_date (actual watch day), not the diary entry date,
    # so the period selector stays consistent with how Spotify data is filtered.
    # date() cast is needed because pandas stores datetimes as ISO strings in SQLite.
    return query(
        """
        SELECT name, year, rating, rewatch, watched_date
        FROM diary
        WHERE date(watched_date) >= ? AND date(watched_date) <= ?
        ORDER BY watched_date
        """,
        (date_from, date_to),
    )


def watched_list_by_range(date_from: str, date_to: str) -> pd.DataFrame:
    # LEFT JOIN against diary so we can flag which films have a detailed diary entry.
    # Case-insensitive name match handles minor capitalisation differences between
    # the two Letterboxd export files.
    return query(
        """
        SELECT w.name, w.year, w.date,
               CASE WHEN d.name IS NOT NULL THEN 1 ELSE 0 END as in_diary
        FROM watched_list w
        LEFT JOIN diary d ON lower(w.name) = lower(d.name) AND w.year = d.year
        WHERE w.date >= ? AND w.date <= ?
        ORDER BY w.date
        """,
        (date_from, date_to),
    )


def monthly_trend() -> pd.DataFrame:
    # Always returns the full history so the trend chart shows all-time context
    # regardless of which period is currently selected.
    return query("SELECT * FROM monthly_stats ORDER BY year_month")


# --- Backwards compatibility ---

def available_months() -> list[str]:
    df = query("SELECT DISTINCT year_month FROM plays ORDER BY year_month")
    return df["year_month"].tolist()


def monthly_overview() -> pd.DataFrame:
    return monthly_trend()
