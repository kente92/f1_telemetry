"""
app_streamlit.py — F1 App : Résultats + Télémétrie + Prédictions
=================================================================
Version Streamlit Community Cloud.
Lance avec :  streamlit run app_streamlit.py
"""

import warnings
import datetime
warnings.filterwarnings("ignore")

import tempfile
import joblib
import requests
import streamlit as st
import fastf1
import fastf1.plotting
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
from sklearn.preprocessing import StandardScaler

# Détection automatique du dossier de cache
# VPS : /var/cache/f1 (persistant) — Streamlit Cloud / autre : tempfile (éphémère)
def _get_cache_dir() -> str:
    vps_cache = "/var/cache/f1"
    try:
        import os
        os.makedirs(vps_cache, exist_ok=True)
        # Vérifie qu'on peut écrire dedans
        test_file = os.path.join(vps_cache, ".write_test")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return vps_cache
    except Exception:
        return tempfile.gettempdir()

_CACHE_DIR = _get_cache_dir()
fastf1.Cache.enable_cache(_CACHE_DIR)

MODELS_DIR = Path(__file__).parent / "models"

@st.cache_resource
def load_prediction_model(with_grid: bool):
    fname = "f1_model_with_grid.joblib" if with_grid else "f1_model_no_grid.joblib"
    path  = MODELS_DIR / fname
    if not path.exists():
        return None
    return joblib.load(path)

st.set_page_config(
    page_title="F1 App", page_icon="🏎️",
    layout="wide", initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;900&family=Barlow:wght@300;400;500&display=swap');
  html, body, [class*="css"] { font-family: 'Barlow', sans-serif; background-color: #0a0a0f; color: #e8e8e8; }
  .main { background-color: #0a0a0f; }
  .block-container { padding-top: 2rem; padding-bottom: 2rem; }
  .f1-header { font-family: 'Barlow Condensed', sans-serif; font-weight: 900; font-size: 3.2rem; letter-spacing: 0.05em; text-transform: uppercase; background: linear-gradient(90deg, #e8002d 0%, #ff6b6b 50%, #ffffff 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; margin-bottom: 0; line-height: 1; }
  .f1-sub { font-family: 'Barlow Condensed', sans-serif; font-weight: 400; font-size: 1rem; letter-spacing: 0.25em; text-transform: uppercase; color: #666; margin-top: 0.2rem; margin-bottom: 2rem; }
  .section-title { font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 0.85rem; letter-spacing: 0.2em; text-transform: uppercase; color: #e8002d; margin: 1.5rem 0 0.8rem 0; padding-bottom: 0.4rem; border-bottom: 1px solid #1e1e2e; }
  .podium-card { background: #13131a; border-radius: 8px; padding: 1.2rem 1.5rem; border-left: 4px solid var(--color); margin-bottom: 0.8rem; }
  .podium-name { font-family: 'Barlow Condensed', sans-serif; font-weight: 900; font-size: 1.6rem; text-transform: uppercase; color: var(--color); letter-spacing: 0.05em; }
  .podium-meta { font-size: 0.75rem; color: #666; letter-spacing: 0.1em; text-transform: uppercase; margin-top: 0.2rem; }
  .podium-time { font-family: 'Barlow Condensed', sans-serif; font-size: 1.4rem; font-weight: 700; color: #ffffff; margin-top: 0.4rem; }
  section[data-testid="stSidebar"] { background-color: #0d0d14 !important; border-right: 1px solid #1e1e2e; }
  .stButton > button { background: #e8002d !important; color: white !important; border: none !important; font-family: 'Barlow Condensed', sans-serif !important; font-weight: 700 !important; font-size: 1rem !important; letter-spacing: 0.1em !important; text-transform: uppercase !important; padding: 0.6rem 2rem !important; border-radius: 4px !important; width: 100%; }
  .stButton > button:hover { background: #ff1a3e !important; }
  .stMultiSelect > div > div { background-color: #13131a !important; border-color: #2a2a3a !important; }
  .stSelectbox > div > div { background-color: #13131a !important; border-color: #2a2a3a !important; }
</style>
""", unsafe_allow_html=True)

PLOT_BG    = "#0a0a0f"
GRID_COLOR = "#1e1e2e"
FONT_COLOR = "#888888"

CIRCUITS = [
    "Bahrain", "Saudi Arabia", "Australia", "Japan", "China",
    "Miami", "Emilia Romagna", "Monaco", "Canada", "Spain",
    "Austria", "Great Britain", "Hungary", "Belgium", "Netherlands",
    "Italy", "Azerbaijan", "Singapore", "United States", "Mexico",
    "Brazil", "Las Vegas", "Qatar", "Abu Dhabi",
]
YEARS = list(range(datetime.date.today().year, 2017, -1))

JOLPICA_BASE = "https://api.jolpi.ca/ergast/f1"
FEATURE_COLS_GRID    = ["grid", "driverPoints", "driverStandingPosition",
                         "driverWins", "constructorPoints",
                         "constructorStandingPosition", "constructorWins"]
FEATURE_COLS_NO_GRID = ["driverPoints", "driverStandingPosition",
                         "driverWins", "constructorPoints",
                         "constructorStandingPosition", "constructorWins"]
CIRCUITS_PRED = {
    "Bahrain": "bahrain", "Saudi Arabia": "jeddah", "Australia": "albert_park",
    "Japan": "suzuka", "China": "shanghai", "Miami": "miami",
    "Emilia Romagna": "imola", "Monaco": "monaco", "Canada": "villeneuve",
    "Spain": "catalunya", "Austria": "red_bull_ring", "Great Britain": "silverstone",
    "Hungary": "hungaroring", "Belgium": "spa", "Netherlands": "zandvoort",
    "Italy": "monza", "Azerbaijan": "baku", "Singapore": "marina_bay",
    "United States": "americas", "Mexico": "rodriguez", "Brazil": "interlagos",
    "Las Vegas": "vegas", "Qatar": "losail", "Abu Dhabi": "yas_marina",
}


# ─── TÉLÉMÉTRIE — fonctions ───────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def load_session(year: int, circuit: str):
    try:
        session = fastf1.get_session(year, circuit, "R")
        session.load(laps=True, telemetry=True, weather=False, messages=False)
        return session
    except Exception as e:
        st.error(f"Erreur chargement session : {e}")
        return None


@st.cache_data(show_spinner=False)
def get_race_results(year: int, circuit: str) -> pd.DataFrame:
    try:
        session = load_session(year, circuit)
        if session is None:
            return pd.DataFrame()
        cols = ["DriverNumber", "Abbreviation", "FullName", "TeamName",
                "GridPosition", "Position", "Status", "Points",
                "Time", "FastestLap", "FastestLapTime", "FastestLapRank"]
        available = [c for c in cols if c in session.results.columns]
        results = session.results[available].copy()
        results = results.sort_values("Position")
        return results
    except Exception:
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def get_fastest_lap_telemetry(year: int, circuit: str, driver: str) -> dict | None:
    try:
        session = load_session(year, circuit)
        if session is None:
            return None
        lap = session.laps.pick_driver(driver).pick_fastest()
        if lap is None or (hasattr(lap, 'empty') and lap.empty):
            return None
        tel = lap.get_telemetry().add_distance()
        try:
            color = fastf1.plotting.get_driver_color(driver, session)
        except Exception:
            color = None
        return {"driver": driver, "lap_time": lap["LapTime"], "telemetry": tel, "color": color}
    except Exception:
        return None


def format_laptime(td) -> str:
    try:
        total_s = td.total_seconds()
        return f"{int(total_s // 60)}:{total_s % 60:06.3f}"
    except Exception:
        return "N/A"


def make_telemetry_charts(telem_data: dict) -> list:
    channels = [
        ("Speed", "VITESSE (km/h)", 300),
        ("Brake", "FREIN (%)",       180),
        ("nGear", "RAPPORT",         160),
    ]
    figures = []
    for channel, title, height in channels:
        fig = go.Figure()
        for abbr, data in telem_data.items():
            t = data["telemetry"]
            if channel not in t.columns:
                continue
            c = data["color"] or "#e8002d"
            y = t["Brake"].astype(float) * 100 if channel == "Brake" else t[channel]
            fig.add_trace(go.Scatter(
                x=t["Distance"], y=y, name=abbr,
                line=dict(color=c, width=1.8),
                hovertemplate=f"<b>{abbr}</b> — %{{y:.1f}}<extra></extra>",
            ))
        fig.update_layout(
            title=dict(text=title, font=dict(family="Barlow Condensed", size=12, color="#e8002d")),
            height=height, paper_bgcolor=PLOT_BG, plot_bgcolor=PLOT_BG,
            font=dict(family="Barlow Condensed", color=FONT_COLOR),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        font=dict(size=11, color="#ccc"), bgcolor="rgba(0,0,0,0)"),
            margin=dict(l=60, r=30, t=40, b=30),
            hovermode="x unified",
            xaxis=dict(gridcolor=GRID_COLOR, zeroline=False, tickfont=dict(color=FONT_COLOR)),
            yaxis=dict(gridcolor=GRID_COLOR, zeroline=False, tickfont=dict(color=FONT_COLOR)),
        )
        figures.append(fig)
    return figures


def make_track_map_comparison(data1: dict, data2: dict, label1: str, label2: str):
    t1 = data1["telemetry"]
    t2 = data2["telemetry"]
    c1 = data1["color"] or "#e8002d"
    c2 = data2["color"] or "#00d2ff"
    if "X" not in t1.columns or "Y" not in t1.columns:
        return None
    dist_max = min(t1["Distance"].max(), t2["Distance"].max())
    m1 = t1["Distance"] <= dist_max
    m2 = t2["Distance"] <= dist_max
    x_ref = t1.loc[m1, "X"].values
    y_ref = t1.loc[m1, "Y"].values
    dist1 = t1.loc[m1, "Distance"].values
    spd1  = t1.loc[m1, "Speed"].values
    spd2  = np.interp(dist1, t2.loc[m2, "Distance"].values, t2.loc[m2, "Speed"].values)
    delta = spd1 - spd2
    dmax  = float(abs(delta).max()) or 1.0
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x_ref, y=y_ref, mode="lines",
                             line=dict(color="#2a2a3a", width=8),
                             hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(
        x=x_ref, y=y_ref, mode="markers",
        marker=dict(
            color=delta,
            colorscale=[[0.0, c2], [0.5, "#1e1e2e"], [1.0, c1]],
            size=4, cmin=-dmax, cmax=dmax,
            colorbar=dict(title=dict(text="Δ km/h", font=dict(color="#888", size=9)),
                          tickfont=dict(color="#888", size=8), thickness=10, len=0.7, x=1.02),
            showscale=True,
        ),
        name="Δ vitesse",
        hovertemplate="Δ %{marker.color:.1f} km/h<extra></extra>",
    ))
    fig.update_layout(
        height=400, paper_bgcolor=PLOT_BG, plot_bgcolor=PLOT_BG,
        font=dict(family="Barlow Condensed", color=FONT_COLOR),
        margin=dict(l=10, r=60, t=50, b=10),
        xaxis=dict(visible=False, scaleanchor="y", scaleratio=1),
        yaxis=dict(visible=False),
        title=dict(text=f"CARTE — {label1} (rouge/couleur) vs {label2} (bleu/couleur)",
                   font=dict(family="Barlow Condensed", size=12, color="#e8002d")),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    font=dict(size=11, color="#ccc"), bgcolor="rgba(0,0,0,0)"),
    )
    return fig


# ─── PRÉDICTION — fonctions ───────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_standings(year: int, round_num: int):
    prev = round_num - 1
    drv_rows, cst_rows = [], []
    if prev == 0:
        return pd.DataFrame(), pd.DataFrame()
    try:
        r = requests.get(f"{JOLPICA_BASE}/{year}/{prev}/driverStandings.json", timeout=10)
        data = r.json()["MRData"]["StandingsTable"]["StandingsLists"]
        if data:
            for s in data[0]["DriverStandings"]:
                drv_rows.append({
                    "driverId": s["Driver"]["driverId"],
                    "driverName": f"{s['Driver']['givenName']} {s['Driver']['familyName']}",
                    "constructorId": s["Constructors"][0]["constructorId"],
                    "constructorName": s["Constructors"][0]["name"],
                    "driverPoints": float(s["points"]),
                    "driverStandingPosition": int(s["position"]),
                    "driverWins": int(s["wins"]),
                })
    except Exception as e:
        st.warning(f"Standings pilotes indisponibles : {e}")
    try:
        r = requests.get(f"{JOLPICA_BASE}/{year}/{prev}/constructorStandings.json", timeout=10)
        data = r.json()["MRData"]["StandingsTable"]["StandingsLists"]
        if data:
            for s in data[0]["ConstructorStandings"]:
                cst_rows.append({
                    "constructorId": s["Constructor"]["constructorId"],
                    "constructorPoints": float(s["points"]),
                    "constructorStandingPosition": int(s["position"]),
                    "constructorWins": int(s["wins"]),
                })
    except Exception as e:
        st.warning(f"Standings écuries indisponibles : {e}")
    return pd.DataFrame(drv_rows), pd.DataFrame(cst_rows)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_qualifying_grid(year: int, round_num: int) -> dict:
    try:
        r = requests.get(f"{JOLPICA_BASE}/{year}/{round_num}/qualifying.json", timeout=10)
        data = r.json()["MRData"]["RaceTable"]["Races"]
        if not data:
            return {}
        return {res["Driver"]["driverId"]: int(res["position"])
                for res in data[0].get("QualifyingResults", [])}
    except Exception:
        return {}


def build_prediction_df(drv_df, cst_df, grid, use_grid, round_num) -> pd.DataFrame:
    if drv_df.empty:
        return pd.DataFrame()
    rows = []
    for _, drv in drv_df.iterrows():
        did = drv["driverId"]
        cst = cst_df[cst_df["constructorId"] == drv["constructorId"]]
        c_pts  = float(cst.iloc[0]["constructorPoints"])           if not cst.empty else 0.0
        c_pos  = float(cst.iloc[0]["constructorStandingPosition"]) if not cst.empty else 10.0
        c_wins = float(cst.iloc[0]["constructorWins"])             if not cst.empty else 0.0
        row = {
            "driverId": did, "driverName": drv["driverName"],
            "constructorName": drv["constructorName"],
            "driverPoints": float(drv["driverPoints"]) if round_num > 1 else 0.0,
            "driverStandingPosition": float(drv["driverStandingPosition"]) if round_num > 1 else 20.0,
            "driverWins": float(drv["driverWins"]) if round_num > 1 else 0.0,
            "constructorPoints": c_pts if round_num > 1 else 0.0,
            "constructorStandingPosition": c_pos if round_num > 1 else 10.0,
            "constructorWins": c_wins if round_num > 1 else 0.0,
        }
        if use_grid:
            row["grid"] = grid.get(did, 20)
        rows.append(row)
    return pd.DataFrame(rows)


def run_prediction(df_features, bundle, use_grid) -> pd.DataFrame:
    feat_cols = FEATURE_COLS_GRID if use_grid else FEATURE_COLS_NO_GRID
    X_sc = bundle["scaler"].transform(df_features[feat_cols].values)
    proba_rf  = bundle["rf"].predict_proba(X_sc)[:, 1]
    proba_dt  = bundle["dt"].predict_proba(X_sc)[:, 1]
    proba_avg = (proba_rf + proba_dt) / 2
    df = df_features[["driverName", "constructorName"]].copy()
    df["proba_rf"] = proba_rf
    df["proba_dt"] = proba_dt
    df["proba_avg"] = proba_avg
    if use_grid:
        df["grid"] = df_features["grid"].values
    df["position"] = df["proba_avg"].rank(ascending=False, method="first").astype(int)
    return df.sort_values("position").reset_index(drop=True)


def render_pred_card(row, rank, color) -> str:
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    pct = f"{row['proba_avg']*100:.1f}%"
    grid_txt = f" · Grille P{int(row['grid'])}" if "grid" in row else ""
    return f"""<div style="background:#13131a;border-left:4px solid {color};border-radius:8px;padding:1rem 1.2rem;margin-bottom:0.6rem;">
        <div style="font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:1.5rem;color:{color};">{medals.get(rank,f"#{rank}")} {row['driverName'].upper()}</div>
        <div style="font-size:0.75rem;color:#666;text-transform:uppercase;margin-top:0.2rem;">{row['constructorName']}{grid_txt}</div>
        <div style="font-family:'Barlow Condensed',sans-serif;font-size:1.8rem;font-weight:700;color:#fff;margin-top:0.4rem;">{pct} <span style="font-size:0.8rem;color:#555;font-weight:400">prob. podium</span></div>
    </div>"""


def render_full_ranking(df, top_highlight, color) -> str:
    html = ""
    for _, row in df.iterrows():
        pos   = int(row["position"])
        is_hl = pos <= top_highlight
        bg    = "#1a1a24" if is_hl else "#0f0f16"
        left  = color    if is_hl else "#2a2a3a"
        pct   = f"{row['proba_avg']*100:.1f}%"
        bar_w = int(row["proba_avg"] * 120)
        g_txt = f"P{int(row['grid'])}" if "grid" in row else ""
        html += f"""<div style="display:flex;align-items:center;gap:0.8rem;background:{bg};border-left:3px solid {left};border-radius:4px;padding:0.5rem 0.8rem;margin-bottom:0.3rem;">
            <div style="font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:1.1rem;color:{'#fff' if is_hl else '#666'};min-width:2rem;text-align:right;">{pos}</div>
            <div style="flex:1;"><div style="font-family:'Barlow Condensed',sans-serif;font-weight:600;font-size:0.95rem;color:{'#fff' if is_hl else '#aaa'};">{row['driverName']}</div>
            <div style="font-size:0.7rem;color:#555;text-transform:uppercase;">{row['constructorName']} {"· Grille "+g_txt if g_txt else ""}</div></div>
            <div style="text-align:right;min-width:3.5rem;"><div style="font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:1rem;color:{color if is_hl else '#555'};">{pct}</div>
            <div style="background:#1e1e2e;border-radius:2px;height:3px;margin-top:2px;"><div style="background:{color if is_hl else '#333'};width:{bar_w}px;max-width:100%;height:3px;border-radius:2px;"></div></div></div>
        </div>"""
    return html


# ─── LAYOUT ───────────────────────────────────────────────────────────────────

st.markdown('<div class="f1-header">F1 App</div>', unsafe_allow_html=True)
st.markdown('<div class="f1-sub">Résultats · Télémétrie · Prédictions</div>', unsafe_allow_html=True)

tab_race, tab_pred = st.tabs(["🏎️  Course & Télémétrie", "🔮  Prédictions"])


# ─── ONGLET 1 — COURSE & TÉLÉMÉTRIE ──────────────────────────────────────────

with tab_race:

    with st.sidebar:
        st.markdown("""<div style='font-family:Barlow Condensed,sans-serif;font-weight:900;font-size:1.5rem;color:#e8002d;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:1.5rem;'>⬡ Course</div>""", unsafe_allow_html=True)
        st.markdown('<p style="font-size:0.8rem;color:#aaa;text-transform:uppercase;letter-spacing:0.1em;">Saison</p>', unsafe_allow_html=True)
        sel_year = st.selectbox("Saison", YEARS, label_visibility="collapsed", format_func=lambda y: f"Saison {y}", key="race_year")
        st.markdown('<p style="font-size:0.8rem;color:#aaa;text-transform:uppercase;letter-spacing:0.1em;">Grand Prix</p>', unsafe_allow_html=True)
        sel_circuit = st.selectbox("Circuit", CIRCUITS, label_visibility="collapsed", key="race_circuit")
        st.markdown("<br>", unsafe_allow_html=True)
        load_btn = st.button("🏁  Charger la course", use_container_width=True, key="load_btn")
        st.markdown("""<div style='margin-top:2rem;padding-top:1rem;border-top:1px solid #1e1e2e;font-size:0.7rem;color:#444;line-height:1.6;'>Données : FastF1 · Jolpica API<br>Cache : {_CACHE_DIR}</div>""", unsafe_allow_html=True)

    if not load_btn and "session_loaded" not in st.session_state:
        st.markdown("""<div style='text-align:center;padding:5rem 2rem;font-family:Barlow Condensed,sans-serif;'><div style='font-size:5rem;margin-bottom:1rem;'>🏎️</div><div style='font-size:1.2rem;letter-spacing:0.15em;text-transform:uppercase;color:#444;'>Sélectionnez une saison et un Grand Prix<br>puis cliquez sur Charger</div></div>""", unsafe_allow_html=True)
        st.stop()

    if load_btn:
        st.session_state["session_loaded"] = True
        st.session_state["active_year"]    = sel_year
        st.session_state["active_circuit"] = sel_circuit

    year    = st.session_state.get("active_year", sel_year)
    circuit = st.session_state.get("active_circuit", sel_circuit)

    # Vérifie si la session est déjà en cache
    _cache_key = f"{year}_{circuit}"
    _already_cached = st.session_state.get("cached_session_key") == _cache_key

    if not _already_cached:
        st.markdown(f"""
        <div style="background:#13131a; border-left:4px solid #e8002d; border-radius:8px;
                    padding:1.5rem 2rem; margin-bottom:1.5rem;">
            <div style="font-family:'Barlow Condensed',sans-serif; font-weight:900;
                        font-size:1.4rem; color:#e8002d; letter-spacing:0.05em;
                        text-transform:uppercase;">
                ⏳ Téléchargement des données en cours
            </div>
            <div style="font-size:0.9rem; color:#aaa; margin-top:0.5rem; line-height:1.6;">
                Récupération de la télémétrie de <b>{circuit} {year}</b> depuis les serveurs F1.<br>
                Cette opération peut prendre <b>30 à 60 secondes</b> lors du premier chargement.<br>
                <span style="color:#666; font-size:0.8rem;">
                    Les prochains chargements de cette course seront instantanés (cache actif).
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with st.spinner("Téléchargement des données, merci de patienter…"):
        session = load_session(year, circuit)

    if session is not None:
        st.session_state["cached_session_key"] = _cache_key

    if session is None:
        st.error("Session indisponible. Essayez une autre course.")
        st.stop()

    # Résultats
    results_df = get_race_results(year, circuit)

    if not results_df.empty:
        # Podium
        st.markdown('<div class="section-title">🏆 Podium</div>', unsafe_allow_html=True)
        podium_colors = ["#FFD700", "#C0C0C0", "#CD7F32"]
        pcols = st.columns(3)
        for i in range(min(3, len(results_df))):
            row = results_df.iloc[i]
            try:
                color = fastf1.plotting.get_driver_color(row["Abbreviation"], session)
            except Exception:
                color = podium_colors[i]
            lt = format_laptime(row["FastestLapTime"]) if "FastestLapTime" in row and pd.notna(row["FastestLapTime"]) else "N/A"
            fastest_icon = " ⚡" if "FastestLapRank" in row and row["FastestLapRank"] == 1 else ""
            medals = ["🥇", "🥈", "🥉"]
            with pcols[i]:
                st.markdown(f"""<div class="podium-card" style="--color:{color}">
                    <div style="font-size:1.8rem">{medals[i]}</div>
                    <div class="podium-name">{row['Abbreviation']}</div>
                    <div class="podium-meta">{row['FullName']} · {row['TeamName']}</div>
                    <div class="podium-time">Meilleur tour : {lt}{fastest_icon}</div>
                </div>""", unsafe_allow_html=True)

        # Tableau
        st.markdown('<div class="section-title">📋 Résultats complets</div>', unsafe_allow_html=True)
        disp = results_df[["Position", "Abbreviation", "FullName", "TeamName", "GridPosition", "Status", "Points"]].copy()
        if "FastestLapTime" in results_df.columns:
            disp["FastestLapTime"] = results_df["FastestLapTime"].apply(lambda x: format_laptime(x) if pd.notna(x) else "—")
        disp.columns = ["Pos", "Abrév.", "Pilote", "Écurie", "Grille", "Statut", "Pts"] + (["Meilleur Tour"] if "FastestLapTime" in results_df.columns else [])
        for c in ["Pos", "Grille"]:
            disp[c] = disp[c].fillna("—").apply(lambda x: str(int(float(x))) if x != "—" else "—")
        st.dataframe(disp, use_container_width=True, hide_index=True)

    # Télémétrie
    st.markdown('<div class="section-title">📈 Télémétrie — Meilleur tour par pilote</div>', unsafe_allow_html=True)

    all_drivers = sorted(session.laps["Driver"].unique().tolist())

    selected_drivers = st.multiselect(
        "Pilotes affichés",
        options=all_drivers,
        default=all_drivers,
        key="telem_drivers",
    )

    if selected_drivers:
        telem_data = {}
        prog = st.progress(0, text="Chargement télémétrie…")
        for i, drv in enumerate(selected_drivers):
            data = get_fastest_lap_telemetry(year, circuit, drv)
            if data is not None:
                telem_data[drv] = data
            prog.progress((i + 1) / len(selected_drivers),
                          text=f"Chargement {drv}… ({i+1}/{len(selected_drivers)})")
        prog.empty()

        if telem_data:
            for fig in make_telemetry_charts(telem_data):
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.warning("Aucune télémétrie disponible.")
    else:
        st.info("Sélectionnez au moins un pilote.")

    # Carte circuit
    st.markdown('<div class="section-title">🗺️ Carte du circuit — Delta vitesse</div>', unsafe_allow_html=True)
    mc1, mc2 = st.columns(2)
    with mc1:
        map_d1 = st.selectbox("Pilote 1 (carte)", all_drivers, key="map_d1", index=0)
    with mc2:
        map_d2 = st.selectbox("Pilote 2 (carte)", all_drivers, key="map_d2",
                              index=min(1, len(all_drivers) - 1))

    if map_d1 != map_d2:
        with st.spinner("Génération de la carte…"):
            md1 = get_fastest_lap_telemetry(year, circuit, map_d1)
            md2 = get_fastest_lap_telemetry(year, circuit, map_d2)
        if md1 and md2 and "X" in md1["telemetry"].columns:
            fig_map = make_track_map_comparison(md1, md2, map_d1, map_d2)
            if fig_map:
                st.plotly_chart(fig_map, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("Données GPS indisponibles pour cette course.")
    else:
        st.info("Sélectionnez deux pilotes différents pour la carte.")


# ─── ONGLET 2 — PRÉDICTIONS ───────────────────────────────────────────────────

with tab_pred:

    st.markdown('<div class="section-title">Paramètres de la course</div>', unsafe_allow_html=True)
    pc1, pc2, pc3 = st.columns(3)
    with pc1:
        pred_year = st.selectbox("Saison", YEARS, key="pred_year", format_func=lambda y: f"Saison {y}")
    with pc2:
        pred_circuit_name = st.selectbox("Grand Prix", list(CIRCUITS_PRED.keys()), key="pred_circuit")
    with pc3:
        pred_round = st.number_input("Numéro de manche", min_value=1, max_value=24, value=1, step=1, key="pred_round")

    st.markdown('<div class="section-title">Grille de départ</div>', unsafe_allow_html=True)
    use_grid = st.checkbox("Tenir compte des positions de départ (après qualifications)", key="use_grid", value=False)
    grid_data = {}

    if use_grid:
        grid_source = st.radio("Source", ["🌐 Récupérer via Jolpica", "✏️ Saisie manuelle"],
                               key="grid_source", horizontal=True, label_visibility="collapsed")
        if grid_source == "🌐 Récupérer via Jolpica":
            if st.button("Récupérer la grille", key="fetch_grid_btn"):
                with st.spinner("Récupération qualifications…"):
                    grid_data = fetch_qualifying_grid(pred_year, pred_round)
                if grid_data:
                    st.success(f"✅ {len(grid_data)} pilotes récupérés")
                    st.session_state["grid_data"] = grid_data
                else:
                    st.warning("Qualifications pas encore disponibles.")
            grid_data = st.session_state.get("grid_data", {})
        else:
            with st.spinner("Récupération pilotes…"):
                drv_df_m, _ = fetch_standings(pred_year, pred_round)
            if not drv_df_m.empty:
                cols_g = st.columns(4)
                for i, (_, dr) in enumerate(drv_df_m.iterrows()):
                    with cols_g[i % 4]:
                        pos = st.number_input(dr["driverName"], min_value=0, max_value=20,
                                              value=0, step=1, key=f"gm_{dr['driverId']}")
                        if pos > 0:
                            grid_data[dr["driverId"]] = pos

    st.markdown("<br>", unsafe_allow_html=True)
    predict_btn = st.button("🔮  Prédire", use_container_width=True, key="predict_btn")

    if not predict_btn:
        st.markdown("""<div style='text-align:center;padding:4rem 2rem;font-family:Barlow Condensed,sans-serif;'><div style='font-size:4rem;margin-bottom:1rem;'>🔮</div><div style='font-size:1.1rem;letter-spacing:0.15em;text-transform:uppercase;color:#444;'>Configurez la course et cliquez sur Prédire</div></div>""", unsafe_allow_html=True)
    else:
        bundle = load_prediction_model(with_grid=use_grid)
        if bundle is None:
            st.error("❌ Modèle introuvable. Vérifiez que les fichiers .joblib sont dans models/")
            st.stop()

        with st.spinner("Récupération standings…"):
            drv_df, cst_df = fetch_standings(pred_year, pred_round)

        df_feat = build_prediction_df(drv_df, cst_df, grid_data, use_grid, pred_round)
        if df_feat.empty:
            st.error("Données indisponibles pour cette course.")
            st.stop()

        df_pred_result = run_prediction(df_feat, bundle, use_grid)
        grid_note = " (avec grille)" if use_grid else " (sans grille)"
        st.markdown(f"""<div style='font-family:Barlow Condensed;font-size:0.8rem;letter-spacing:0.15em;text-transform:uppercase;color:#666;margin-bottom:1.5rem;'>{pred_circuit_name} · {pred_year} · Manche {pred_round}{grid_note}</div>""", unsafe_allow_html=True)

        for top_n, title, color in [(1, "Vainqueur prédit", "#e8002d"),
                                     (3, "Podium prédit", "#ff6b35"),
                                     (6, "Top 6 prédit", "#00d2ff")]:
            st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
            top_df = df_pred_result[df_pred_result["position"] <= top_n]
            cols_t = st.columns(min(top_n, 3))
            for i, (_, row) in enumerate(top_df.iterrows()):
                with cols_t[i % len(cols_t)]:
                    st.markdown(render_pred_card(row, int(row["position"]), color), unsafe_allow_html=True)

        st.markdown('<div class="section-title">Classement complet</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="max-width:600px;">{render_full_ranking(df_pred_result, 6, "#e8002d")}</div>', unsafe_allow_html=True)

        st.markdown('<div class="section-title">Probabilités RF vs DT</div>', unsafe_allow_html=True)
        fig_p = go.Figure()
        fig_p.add_trace(go.Bar(x=df_pred_result["driverName"], y=df_pred_result["proba_rf"]*100,
                               name="Random Forest", marker_color="#e8002d", opacity=0.85))
        fig_p.add_trace(go.Bar(x=df_pred_result["driverName"], y=df_pred_result["proba_dt"]*100,
                               name="Decision Tree", marker_color="#00d2ff", opacity=0.85))
        fig_p.update_layout(
            height=320, barmode="group", paper_bgcolor=PLOT_BG, plot_bgcolor=PLOT_BG,
            font=dict(family="Barlow Condensed", color=FONT_COLOR),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        font=dict(color="#ccc"), bgcolor="rgba(0,0,0,0)"),
            margin=dict(l=40, r=20, t=40, b=80),
            xaxis=dict(tickangle=-45, gridcolor=GRID_COLOR, tickfont=dict(color="#888", size=9)),
            yaxis=dict(gridcolor=GRID_COLOR, title="P(podium) %", title_font=dict(color="#888", size=10)),
        )
        st.plotly_chart(fig_p, use_container_width=True, config={"displayModeBar": False})
