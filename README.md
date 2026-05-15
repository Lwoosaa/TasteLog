# TasteLog 🎵🎬

A personal analytics tool that combines your Spotify listening history with your Letterboxd film diary.

## Features

**Music**
- Weekly / monthly / yearly / custom date range selection
- Top 10 most played artists and tracks (bar charts)
- Listening distribution by hour of day
- All-time monthly listening trend
- Full artist, album and track rankings (unlimited, scrollable)

**Films**
- Letterboxd Diary — watch date, rating, rewatch flag
- All Watched — includes films not logged in the diary
- TMDB enrichment: user score, vote count, release date, genres, keywords

## Setup

```bash
git clone https://github.com/Lwoosaa/TasteLog.git
cd TasteLog
```

Get a free TMDB API key at [themoviedb.org](https://www.themoviedb.org/settings/api) and add it to `settings.json`:

```json
{
  "tmdb_api_key": "your_key_here"
}
```

Optionally pre-populate the TMDB cache with the top 5000 popular films (recommended — speeds up the film section significantly):

```bash
python scripts/fetch_popular.py
```

If any keywords were missed due to timeouts, run:

```bash
python scripts/fill_missing_keywords.py
```

## Running

```bash
streamlit run app/main.py
```

Go to `http://localhost:8501`, upload your Spotify and Letterboxd ZIP files from the sidebar.

## Data sources

**Spotify:** Account → Privacy → Download your data → Extended streaming history
**Letterboxd:** Profile → Settings → Import & Export → Export your data

## Project structure

```
TasteLog/
├── app/
│   └── main.py                   # Streamlit app
├── src/
│   ├── spotify_parser.py         # Spotify JSON → DataFrame
│   ├── letterboxd_parser.py      # Letterboxd CSV → DataFrame
│   ├── database.py               # SQLite queries (range-based)
│   └── tmdb.py                   # TMDB API client + SQLite cache
├── scripts/
│   ├── fetch_popular.py          # Pre-populate cache with top 5000 films
│   └── fill_missing_keywords.py  # Retry failed keyword fetches
├── data/raw/                     # Raw data files (.gitignore)
├── db/                           # SQLite database (.gitignore)
└── settings.json                 # API keys (.gitignore)
```

## Notes

- Plays shorter than 30 seconds are filtered out (counted as skips)
- All timestamps are converted to Europe/Istanbul timezone
- TMDB data is cached in SQLite — each film is fetched from the API only once
- `add_vline` doesn't work on string x-axes in Plotly; `add_scatter` is used instead

## Planned features

- Film × music correlation (what were you listening to when you watched a film?)
- Music genre × film genre / keyword correlation
- Spotify API integration for real-time data and audio features
- FastAPI + React web app
