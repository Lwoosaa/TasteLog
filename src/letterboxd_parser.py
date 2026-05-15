import zipfile
import pandas as pd
from io import StringIO


def load_letterboxd_zip(zip_path: str) -> dict[str, pd.DataFrame]:
    """Reads diary.csv, watched.csv and ratings.csv from a Letterboxd export ZIP."""
    results = {}
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        for target in ["diary.csv", "watched.csv", "ratings.csv"]:
            match = next((n for n in names if n.endswith(target) and "deleted" not in n and "orphaned" not in n), None)
            if match:
                with z.open(match) as f:
                    results[target.replace(".csv", "")] = pd.read_csv(f)
    return _parse_letterboxd(results)


def load_letterboxd_folder(folder_path: str) -> dict[str, pd.DataFrame]:
    """Reads diary.csv, watched.csv and ratings.csv from a folder."""
    import os
    results = {}
    for target in ["diary.csv", "watched.csv", "ratings.csv"]:
        path = os.path.join(folder_path, target)
        if os.path.exists(path):
            results[target.replace(".csv", "")] = pd.read_csv(path)
    return _parse_letterboxd(results)


def _parse_letterboxd(raw: dict) -> dict[str, pd.DataFrame]:
    """Cleans and normalises raw Letterboxd CSV data."""
    out = {}

    if "diary" in raw:
        df = raw["diary"].copy()
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]
        df["watched_date"] = pd.to_datetime(df["watched_date"], errors="coerce")
        df["date"] = df["watched_date"].dt.date
        df["year"] = df["watched_date"].dt.year
        df["month"] = df["watched_date"].dt.month
        df["year_month"] = df["watched_date"].dt.to_period("M").astype(str)
        df["rating"] = pd.to_numeric(df.get("rating", None), errors="coerce")
        df = df.dropna(subset=["watched_date"]).sort_values("watched_date").reset_index(drop=True)
        out["diary"] = df

    if "watched" in raw:
        df = raw["watched"].copy()
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        out["watched"] = df

    return out
