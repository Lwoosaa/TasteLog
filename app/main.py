import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import sys
import tempfile
import os
import calendar
from datetime import date, timedelta
from pathlib import Path

# Add the project root to sys.path so `src.*` imports work when running
# from app/ via `streamlit run app/main.py`.
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.spotify_parser import load_spotify_zip
from src.letterboxd_parser import load_letterboxd_zip
from src.tmdb import init_cache_table, enrich_df
from src.database import (
    build_database,
    overview_by_range,
    top_artists_by_range,
    top_tracks_by_range,
    listening_by_hour_range,
    all_artists_by_range,
    all_albums_by_range,
    all_tracks_by_range,
    diary_by_range,
    watched_list_by_range,
    monthly_trend,
    available_months,
    available_date_range,
    DB_PATH,
)

st.set_page_config(
    page_title="TasteLog",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

SETTINGS_PATH = Path(__file__).parent.parent / "settings.json"


def load_settings() -> dict:
    if SETTINGS_PATH.exists():
        import json
        return json.loads(SETTINGS_PATH.read_text())
    return {}


# Minimal CSS — only touches label weight to make sidebar controls easier to scan.
st.markdown("""
<style>
    .stSelectbox label { font-weight: 500; }
    .stRadio label { font-weight: 500; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("TasteLog")
    st.caption("Spotify × Letterboxd")
    st.divider()

    # File uploaders — Streamlit keeps uploaded bytes in memory until the session ends.
    # We write them to a temp file so the parsers (which expect a file path) can read them,
    # then delete the temp file immediately after parsing is done.
    st.subheader("Veri yükle")
    spotify_zip = st.file_uploader("Spotify ZIP", type="zip", key="spotify")
    letterboxd_zip = st.file_uploader("Letterboxd ZIP", type="zip", key="letterboxd")

    if spotify_zip:
        with st.spinner("Veriler işleniyor..."):
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_s:
                tmp_s.write(spotify_zip.read())
                tmp_spotify = tmp_s.name
            lb_data = None
            if letterboxd_zip:
                with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_l:
                    tmp_l.write(letterboxd_zip.read())
                    tmp_letterboxd = tmp_l.name
                lb_data = load_letterboxd_zip(tmp_letterboxd)
                os.unlink(tmp_letterboxd)
            spotify_df = load_spotify_zip(tmp_spotify)
            os.unlink(tmp_spotify)
            build_database(spotify_df, lb_data)
            st.success(f"{len(spotify_df):,} kayıt yüklendi")

    # Stop early if no database exists yet — nothing to show on the main page.
    if not DB_PATH.exists():
        st.info("Başlamak için Spotify ZIP'ini yükle.")
        st.stop()

    # tmdb_cache table must exist before any film section tries to read it.
    init_cache_table()

    st.divider()

    # API key is read from settings.json — not entered via UI to keep the sidebar clean.
    tmdb_api_key = load_settings().get("tmdb_api_key", "")

    st.divider()

    # Period selector — all four modes resolve to a (date_from, date_to) pair
    # so every downstream query uses the same interface regardless of mode.
    period_type = st.radio(
        "Dönem",
        ["Aylık", "Haftalık", "Yıllık", "Özel"],
        horizontal=True,
    )

    months = available_months()
    min_date_str, max_date_str = available_date_range()
    min_date = date.fromisoformat(min_date_str)
    max_date = date.fromisoformat(max_date_str)

    if period_type == "Aylık":
        selected_month = st.selectbox("Ay seç", options=months, index=len(months) - 1)
        year, month_num = map(int, selected_month.split("-"))
        date_from = date(year, month_num, 1)
        # monthrange returns (weekday_of_first_day, number_of_days), so [1] gives the last day.
        date_to = date(year, month_num, calendar.monthrange(year, month_num)[1])
        period_label = date_from.strftime("%B %Y")

    elif period_type == "Haftalık":
        selected_date = st.date_input(
            "Haftadan bir gün seç",
            value=max_date,
            min_value=min_date,
            max_value=max_date,
        )
        # weekday() returns 0 for Monday, so subtracting it snaps to the week's Monday.
        week_start = selected_date - timedelta(days=selected_date.weekday())
        week_end = week_start + timedelta(days=6)
        # Clamp to data boundaries so we don't query outside the available range.
        date_from = max(week_start, min_date)
        date_to = min(week_end, max_date)
        period_label = f"{date_from.strftime('%d %b')} – {date_to.strftime('%d %b %Y')}"

    elif period_type == "Yıllık":
        years = sorted(set(m[:4] for m in months))
        selected_year = st.selectbox("Yıl seç", options=years, index=len(years) - 1)
        date_from = date(int(selected_year), 1, 1)
        date_to = date(int(selected_year), 12, 31)
        period_label = selected_year

    else:  # Özel
        date_from = st.date_input("Başlangıç", value=min_date, min_value=min_date, max_value=max_date)
        date_to = st.date_input("Bitiş", value=max_date, min_value=min_date, max_value=max_date)
        period_label = f"{date_from.strftime('%d %b %Y')} – {date_to.strftime('%d %b %Y')}"

    # Convert to strings once here — SQLite date comparisons expect ISO format strings.
    date_from_str = str(date_from)
    date_to_str = str(date_to)


# ── Main page ─────────────────────────────────────────────────────────────────

st.title(f"🎵 {period_label}")

overview = overview_by_range(date_from_str, date_to_str)

# Guard against periods with no data (e.g. a week before the user started using Spotify).
if overview.empty or int(overview.iloc[0]["total_plays"]) == 0:
    st.warning("Bu dönemde dinleme kaydı bulunamadı.")
    st.stop()

row = overview.iloc[0]

# ── Metric cards ──────────────────────────────────────────────────────────────

col1, col2, col3, col4 = st.columns(4)
col1.metric("Toplam dinleme", f"{int(row['total_plays']):,}")
col2.metric("Dinleme süresi", f"{int(row['total_minutes'] / 60)} saat")
col3.metric("Farklı sanatçı", f"{int(row['unique_artists'])}")
col4.metric("Farklı şarkı",   f"{int(row['unique_tracks'])}")

st.divider()

# ── Top 10 charts ─────────────────────────────────────────────────────────────
# Horizontal bars work better than vertical when artist/track names are long.
# Color encodes minutes so a bar with fewer plays but longer listening time stands out.

left, right = st.columns(2)

with left:
    st.subheader("En çok dinlenen sanatçılar")
    top_artists = top_artists_by_range(date_from_str, date_to_str)
    if not top_artists.empty:
        fig = px.bar(
            top_artists, x="plays", y="artist", orientation="h",
            color="minutes", color_continuous_scale="Teal",
            labels={"plays": "Dinleme", "artist": "", "minutes": "Dakika"},
        )
        fig.update_layout(
            yaxis={"categoryorder": "total ascending"},
            coloraxis_showscale=False,
            margin=dict(l=0, r=0, t=0, b=0), height=350,
        )
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("En çok dinlenen şarkılar")
    top_tracks = top_tracks_by_range(date_from_str, date_to_str)
    if not top_tracks.empty:
        fig2 = px.bar(
            top_tracks, x="plays", y="track", orientation="h",
            color="plays", color_continuous_scale="Purples",
            labels={"plays": "Dinleme", "track": ""},
        )
        fig2.update_layout(
            yaxis={"categoryorder": "total ascending"},
            coloraxis_showscale=False,
            margin=dict(l=0, r=0, t=0, b=0), height=350,
        )
        st.plotly_chart(fig2, use_container_width=True)

st.divider()

left2, right2 = st.columns(2)

with left2:
    st.subheader("Günün hangi saatinde dinliyorsun?")
    hourly = listening_by_hour_range(date_from_str, date_to_str)
    if not hourly.empty:
        fig3 = px.bar(
            hourly, x="hour", y="plays",
            labels={"hour": "Saat", "plays": "Dinleme"},
            color="plays", color_continuous_scale="Blues",
        )
        fig3.update_layout(
            coloraxis_showscale=False,
            margin=dict(l=0, r=0, t=0, b=0), height=280,
        )
        st.plotly_chart(fig3, use_container_width=True)

with right2:
    # The trend chart always shows the full history (not just the selected period)
    # to give context. In monthly mode, the selected month gets a coral dot on top.
    # add_vline doesn't work on string x-axes, so we use add_scatter instead.
    st.subheader("Aylık dinleme trendi")
    monthly = monthly_trend()
    fig4 = px.line(
        monthly, x="year_month", y="total_minutes",
        labels={"year_month": "Ay", "total_minutes": "Toplam dakika"},
        markers=True,
    )
    if period_type == "Aylık":
        selected_row = monthly[monthly["year_month"] == selected_month]
        if not selected_row.empty:
            fig4.add_scatter(
                x=selected_row["year_month"],
                y=selected_row["total_minutes"],
                mode="markers",
                marker=dict(color="coral", size=14, symbol="circle"),
                name="seçili ay",
            )
    fig4.update_layout(
        showlegend=False,
        margin=dict(l=0, r=0, t=0, b=0), height=280,
    )
    st.plotly_chart(fig4, use_container_width=True)


# ── Letterboxd section ────────────────────────────────────────────────────────
# Wrapped in try/except because Letterboxd data is optional — if the user only
# uploaded Spotify, the tables won't exist and we skip this section silently.

try:
    con = sqlite3.connect(DB_PATH)
    tables = pd.read_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('diary','watched_list')", con
    )["name"].tolist()
    con.close()

    if tables:
        st.divider()
        st.subheader("🎬 Filmler")

        # Two tabs: diary entries (rich data) vs the full watched list (date only).
        film_tab1, film_tab2 = st.tabs(["📔 Diary", "👁 Tüm İzlenenler"])

        with film_tab1:
            if "diary" in tables:
                diary_df = diary_by_range(date_from_str, date_to_str)
                if not diary_df.empty:
                    diary_df = diary_df.rename(columns={
                        "name": "Film", "year": "Yıl", "rating": "Puan",
                        "rewatch": "Tekrar", "watched_date": "İzleme Tarihi",
                    })
                    if tmdb_api_key:
                        with st.spinner("TMDB verisi yükleniyor..."):
                            enrich_df(diary_df, tmdb_api_key, "Film", "Yıl")
                    st.dataframe(diary_df, use_container_width=True, hide_index=True)
                else:
                    st.caption("Bu dönemde diary kaydı yok.")
            else:
                st.caption("Diary verisi yüklenmemiş.")

        with film_tab2:
            if "watched_list" in tables:
                watched_df = watched_list_by_range(date_from_str, date_to_str)
                if not watched_df.empty:
                    # Convert the 0/1 flag to a checkmark so it's readable at a glance.
                    watched_df["in_diary"] = watched_df["in_diary"].map({1: "✓", 0: ""})
                    watched_df = watched_df.rename(columns={
                        "name": "Film", "year": "Yıl",
                        "date": "Tarih", "in_diary": "Diary'de",
                    })
                    if tmdb_api_key:
                        with st.spinner("TMDB verisi yükleniyor..."):
                            enrich_df(watched_df, tmdb_api_key, "Film", "Yıl")
                    st.dataframe(watched_df, use_container_width=True, hide_index=True)
                else:
                    st.caption("Bu dönemde izleme kaydı yok.")
            else:
                st.caption("Watched verisi yüklenmemiş.")
except Exception:
    pass


# ── Full rankings ─────────────────────────────────────────────────────────────
# Three tabs with unlimited results in a scrollable table — lets the user dig
# deeper than the top-10 charts above without cluttering the main view.

st.divider()
st.subheader("Sıralamalar")
st.caption(f"{period_label} dönemi — tüm kayıtlar")

rank_tab1, rank_tab2, rank_tab3 = st.tabs(["🎤 Sanatçılar", "💿 Albümler", "🎵 Şarkılar"])

with rank_tab1:
    df_artists = all_artists_by_range(date_from_str, date_to_str)
    if not df_artists.empty:
        df_artists.insert(0, "#", range(1, len(df_artists) + 1))
        df_artists = df_artists.rename(columns={
            "artist": "Sanatçı", "plays": "Dinleme",
            "minutes": "Dakika", "unique_tracks": "Farklı şarkı",
        })
        st.dataframe(df_artists, use_container_width=True, hide_index=True, height=500)

with rank_tab2:
    df_albums = all_albums_by_range(date_from_str, date_to_str)
    if not df_albums.empty:
        df_albums.insert(0, "#", range(1, len(df_albums) + 1))
        df_albums = df_albums.rename(columns={
            "album": "Albüm", "artist": "Sanatçı",
            "plays": "Dinleme", "minutes": "Dakika", "unique_tracks": "Farklı şarkı",
        })
        st.dataframe(df_albums, use_container_width=True, hide_index=True, height=500)

with rank_tab3:
    df_tracks = all_tracks_by_range(date_from_str, date_to_str)
    if not df_tracks.empty:
        df_tracks.insert(0, "#", range(1, len(df_tracks) + 1))
        df_tracks = df_tracks.rename(columns={
            "track": "Şarkı", "artist": "Sanatçı",
            "album": "Albüm", "plays": "Dinleme", "minutes": "Dakika",
        })
        st.dataframe(df_tracks, use_container_width=True, hide_index=True, height=500)
