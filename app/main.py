import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.spotify_parser import load_spotify_zip
from src.letterboxd_parser import load_letterboxd_zip
from src.database import (
    build_database,
    top_artists_by_month,
    top_tracks_by_month,
    listening_by_hour,
    monthly_overview,
    available_months,
    DB_PATH,
)

st.set_page_config(
    page_title="musicboxd",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stSelectbox label { font-weight: 500; }
</style>
""", unsafe_allow_html=True)


# --- Sidebar ---
with st.sidebar:
    st.title("musicboxd")
    st.caption("Spotify × Letterboxd")
    st.divider()

    st.subheader("Veri yükle")
    spotify_zip = st.file_uploader("Spotify ZIP", type="zip", key="spotify")
    letterboxd_zip = st.file_uploader("Letterboxd ZIP", type="zip", key="letterboxd")

    if spotify_zip:
        with st.spinner("Veriler işleniyor..."):
            import tempfile, os
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

    if DB_PATH.exists():
        st.divider()
        months = available_months()
        selected_month = st.selectbox("Ay seç", options=months, index=len(months) - 1)
    else:
        st.info("Başlamak için Spotify ZIP'ini yükle.")
        st.stop()


# --- Ana sayfa ---
st.title(f"🎵 {selected_month}")

top_artists = top_artists_by_month(selected_month)
top_tracks  = top_tracks_by_month(selected_month)
monthly     = monthly_overview()
this_month  = monthly[monthly["year_month"] == selected_month].iloc[0]

# Metrik kartları
col1, col2, col3, col4 = st.columns(4)
col1.metric("Toplam dinleme", f"{int(this_month['total_plays']):,}")
col2.metric("Dinleme süresi", f"{int(this_month['total_minutes'] / 60)} saat")
col3.metric("Farklı sanatçı", f"{int(this_month['unique_artists'])}")
col4.metric("Farklı şarkı",   f"{int(this_month['unique_tracks'])}")

st.divider()

left, right = st.columns(2)

with left:
    st.subheader("En çok dinlenen sanatçılar")
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
    hourly = listening_by_hour(selected_month)
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
    st.subheader("Aylık dinleme trendi")
    fig4 = px.line(
        monthly, x="year_month", y="total_minutes",
        labels={"year_month": "Ay", "total_minutes": "Toplam dakika"},
        markers=True,
    )
    # Seçili ayı işaretle (add_vline string eksende çalışmaz, scatter kullanıyoruz)
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

# Letterboxd bölümü
try:
    import sqlite3
    con = sqlite3.connect(DB_PATH)
    watches_exist = pd.read_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='watches'", con
    )
    con.close()
    if not watches_exist.empty:
        st.divider()
        st.subheader("🎬 Bu ay izlenen filmler")
        con2 = sqlite3.connect(DB_PATH)
        watches_this_month = pd.read_sql_query(
            "SELECT name, year, rating, watched_date FROM watches WHERE year_month = ? ORDER BY watched_date",
            con2, params=(selected_month,),
        )
        con2.close()
        if not watches_this_month.empty:
            st.dataframe(watches_this_month, use_container_width=True, hide_index=True)
        else:
            st.caption("Bu ay izlenen film kaydı yok.")
except Exception:
    pass
