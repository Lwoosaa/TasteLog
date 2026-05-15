import json
import zipfile
import glob
import os
import pandas as pd
from pathlib import Path


def load_spotify_zip(zip_path: str) -> pd.DataFrame:
    """Reads all Streaming_History_Audio_*.json files from a ZIP archive."""
    records = []
    with zipfile.ZipFile(zip_path) as z:
        json_files = [
            f for f in z.namelist()
            if "Streaming_History_Audio" in f and f.endswith(".json")
        ]
        for json_file in sorted(json_files):
            with z.open(json_file) as f:
                data = json.load(f)
                records.extend(data)
    return _parse_records(records)


def load_spotify_folder(folder_path: str) -> pd.DataFrame:
    """Reads all Streaming_History_Audio_*.json files from a folder."""
    records = []
    pattern = os.path.join(folder_path, "**", "Streaming_History_Audio_*.json")
    files = glob.glob(pattern, recursive=True)
    for file in sorted(files):
        with open(file, encoding="utf-8") as f:
            records.extend(json.load(f))
    return _parse_records(records)


def _parse_records(records: list) -> pd.DataFrame:
    """Converts raw Spotify history records into a clean DataFrame."""
    df = pd.DataFrame(records)

    # Keep only music tracks — drops podcasts and videos.
    df = df[df["master_metadata_track_name"].notna()].copy()

    df = df.rename(columns={
        "ts": "played_at",
        "master_metadata_track_name": "track",
        "master_metadata_album_artist_name": "artist",
        "master_metadata_album_album_name": "album",
        "ms_played": "ms_played",
        "spotify_track_uri": "track_uri",
        "reason_start": "reason_start",
        "reason_end": "reason_end",
        "shuffle": "shuffle",
        "skipped": "skipped",
        "platform": "platform",
    })

    # Convert timestamps to Istanbul timezone.
    df["played_at"] = pd.to_datetime(df["played_at"], utc=True)
    df["played_at"] = df["played_at"].dt.tz_convert("Europe/Istanbul")
    df["date"] = df["played_at"].dt.date
    df["year"] = df["played_at"].dt.year
    df["month"] = df["played_at"].dt.month
    df["year_month"] = df["played_at"].dt.to_period("M").astype(str)
    df["hour"] = df["played_at"].dt.hour
    df["day_of_week"] = df["played_at"].dt.day_name()

    df["minutes_played"] = (df["ms_played"] / 60000).round(2)

    # Drop plays shorter than 30 seconds — these are considered skips.
    df = df[df["ms_played"] >= 30000].copy()

    cols = [
        "played_at", "date", "year", "month", "year_month", "hour", "day_of_week",
        "track", "artist", "album", "track_uri",
        "ms_played", "minutes_played",
        "shuffle", "skipped", "platform",
        "reason_start", "reason_end",
    ]
    df = df[[c for c in cols if c in df.columns]]
    df = df.sort_values("played_at").reset_index(drop=True)

    return df
