import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "musicboxd.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(DB_PATH)


def build_database(spotify_df: pd.DataFrame, letterboxd: dict = None):
    """Tüm tabloları oluşturur ve veriyi yazar."""
    con = get_connection()

    # --- Spotify tabloları ---
    spotify_df.to_sql("plays", con, if_exists="replace", index=False)

    # Sanatçı istatistikleri
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

    # Aylık istatistikler
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

    # --- Letterboxd tabloları ---
    if letterboxd and "diary" in letterboxd:
        letterboxd["diary"].to_sql("watches", con, if_exists="replace", index=False)

    con.commit()
    con.close()
    print(f"Veritabanı oluşturuldu: {DB_PATH}")


# --- Sorgu fonksiyonları ---

def query(sql: str, params=()) -> pd.DataFrame:
    con = get_connection()
    df = pd.read_sql_query(sql, con, params=params)
    con.close()
    return df


def top_artists_by_month(year_month: str, limit: int = 10) -> pd.DataFrame:
    return query(
        """
        SELECT artist, COUNT(*) as plays, SUM(minutes_played) as minutes
        FROM plays
        WHERE year_month = ?
        GROUP BY artist
        ORDER BY plays DESC
        LIMIT ?
        """,
        (year_month, limit),
    )


def top_tracks_by_month(year_month: str, limit: int = 10) -> pd.DataFrame:
    return query(
        """
        SELECT track, artist, COUNT(*) as plays, SUM(minutes_played) as minutes
        FROM plays
        WHERE year_month = ?
        GROUP BY track, artist
        ORDER BY plays DESC
        LIMIT ?
        """,
        (year_month, limit),
    )


def listening_by_hour(year_month: str = None) -> pd.DataFrame:
    where = "WHERE year_month = ?" if year_month else ""
    params = (year_month,) if year_month else ()
    return query(
        f"""
        SELECT hour, COUNT(*) as plays
        FROM plays
        {where}
        GROUP BY hour
        ORDER BY hour
        """,
        params,
    )


def monthly_overview() -> pd.DataFrame:
    return query("SELECT * FROM monthly_stats ORDER BY year_month")


def films_on_date(date: str) -> pd.DataFrame:
    return query(
        "SELECT * FROM watches WHERE date = ?",
        (date,),
    )


def music_on_date(date: str) -> pd.DataFrame:
    return query(
        """
        SELECT track, artist, COUNT(*) as plays, SUM(minutes_played) as minutes
        FROM plays
        WHERE date = ?
        GROUP BY track, artist
        ORDER BY plays DESC
        """,
        (date,),
    )


def available_months() -> list[str]:
    df = query("SELECT DISTINCT year_month FROM plays ORDER BY year_month")
    return df["year_month"].tolist()
