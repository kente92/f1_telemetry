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
from imblearn.over_sampling import RandomOverSampler
from sklearn.svm import SVC
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
                         "constructorStandingPosition", "constructorWins",
                         "rainfall"]
FEATURE_COLS_NO_GRID = ["driverPoints", "driverStandingPosition",
                         "driverWins", "constructorPoints",
                         "constructorStandingPosition", "constructorWins",
                         "rainfall"]
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


def make_lap_by_lap_chart(session, driver1: str, driver2: str) -> go.Figure:
    """
    Comparaison des temps au tour (LapTime en secondes) tout au long de la course.
    Met en évidence les arrêts aux stands.
    """
    laps = session.laps
    d1_laps = laps.pick_driver(driver1)[["LapNumber", "LapTime", "PitOutTime"]].copy()
    d2_laps = laps.pick_driver(driver2)[["LapNumber", "LapTime", "PitOutTime"]].copy()

    # Convertit LapTime en secondes
    d1_laps["LapTime_s"] = d1_laps["LapTime"].dt.total_seconds()
    d2_laps["LapTime_s"] = d2_laps["LapTime"].dt.total_seconds()

    # Couleurs équipes
    try:
        c1 = fastf1.plotting.get_driver_color(driver1, session)
    except Exception:
        c1 = "#e8002d"
    try:
        c2 = fastf1.plotting.get_driver_color(driver2, session)
    except Exception:
        c2 = "#00d2ff"

    fig = go.Figure()

    # Lignes de temps au tour
    fig.add_trace(go.Scatter(
        x=d1_laps["LapNumber"], y=d1_laps["LapTime_s"],
        name=driver1, line=dict(color=c1, width=2),
        hovertemplate=f"<b>{driver1}</b> — Tour %{{x}}<br>Chrono: %{{y:.3f}}s<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=d2_laps["LapNumber"], y=d2_laps["LapTime_s"],
        name=driver2, line=dict(color=c2, width=2, dash="dot"),
        hovertemplate=f"<b>{driver2}</b> — Tour %{{x}}<br>Chrono: %{{y:.3f}}s<extra></extra>",
    ))

    # Marqueurs arrêts aux stands (tours avec PitOutTime non nul)
    pit1 = d1_laps[d1_laps["PitOutTime"].notna()]
    pit2 = d2_laps[d2_laps["PitOutTime"].notna()]
    if not pit1.empty:
        fig.add_trace(go.Scatter(
            x=pit1["LapNumber"], y=pit1["LapTime_s"],
            mode="markers", name=f"{driver1} — Arrêt",
            marker=dict(color=c1, size=10, symbol="triangle-up", line=dict(color="white", width=1)),
            hovertemplate=f"<b>{driver1}</b> — Arrêt T%{{x}}<extra></extra>",
        ))
    if not pit2.empty:
        fig.add_trace(go.Scatter(
            x=pit2["LapNumber"], y=pit2["LapTime_s"],
            mode="markers", name=f"{driver2} — Arrêt",
            marker=dict(color=c2, size=10, symbol="triangle-up", line=dict(color="white", width=1)),
            hovertemplate=f"<b>{driver2}</b> — Arrêt T%{{x}}<extra></extra>",
        ))

    fig.update_layout(
        title=dict(text="CHRONOS TOUR PAR TOUR",
                   font=dict(family="Barlow Condensed", size=12, color="#e8002d")),
        height=340, paper_bgcolor=PLOT_BG, plot_bgcolor=PLOT_BG,
        font=dict(family="Barlow Condensed", color=FONT_COLOR),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    font=dict(size=11, color="#ccc"), bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=60, r=30, t=40, b=40),
        hovermode="x unified",
        xaxis=dict(gridcolor=GRID_COLOR, zeroline=False, title="Tour",
                   title_font=dict(color="#888", size=10), tickfont=dict(color=FONT_COLOR)),
        yaxis=dict(gridcolor=GRID_COLOR, zeroline=False, title="Temps (s)",
                   title_font=dict(color="#888", size=10), tickfont=dict(color=FONT_COLOR)),
    )
    return fig


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

@st.cache_data(show_spinner=False)
def load_circuits_races_df() -> pd.DataFrame:
    """
    Charge circuits + races depuis Jolpica pour la dataviz mondiale.
    Retourne un DataFrame avec lat/lng/name/year/date.
    """
    try:
        rows = []
        # Circuits
        r = requests.get(f"{JOLPICA_BASE}/circuits.json?limit=100", timeout=10)
        circuits_raw = r.json()["MRData"]["CircuitTable"]["Circuits"]
        circ_map = {c["circuitId"]: {
            "name_circuit": c["circuitName"],
            "lat": float(c["Location"]["lat"]),
            "lng": float(c["Location"]["long"]),
            "country": c["Location"]["country"],
            "location": c["Location"]["locality"],
        } for c in circuits_raw}

        # Races — on pagine par décennie pour rester léger
        for decade_start in range(1950, 2030, 10):
            for yr in range(decade_start, min(decade_start + 10, datetime.date.today().year + 1)):
                try:
                    r2 = requests.get(f"{JOLPICA_BASE}/{yr}/races.json?limit=30", timeout=8)
                    races_raw = r2.json()["MRData"]["RaceTable"]["Races"]
                    for race in races_raw:
                        cid = race["Circuit"]["circuitId"]
                        ci  = circ_map.get(cid, {})
                        rows.append({
                            "year":         int(race["season"]),
                            "round":        int(race["round"]),
                            "race_name":    race["raceName"],
                            "date":         race["date"],
                            "name_circuit": ci.get("name_circuit", cid),
                            "lat":          ci.get("lat", 0.0),
                            "lng":          ci.get("lng", 0.0),
                            "country":      ci.get("country", ""),
                            "location":     ci.get("location", ""),
                        })
                except Exception:
                    pass
        return pd.DataFrame(rows)
    except Exception as e:
        return pd.DataFrame()


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


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_weather_forecast(circuit_name: str) -> float:
    """
    Récupère la probabilité de pluie (0.0 ou 1.0) via Open-Meteo.
    Utilise les coordonnées du circuit stockées dans CIRCUIT_COORDS.
    Retourne 0.0 (sec) si pas de données.
    """
    coords = CIRCUIT_COORDS.get(circuit_name)
    if not coords:
        return 0.0
    try:
        lat, lon = coords
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon,
                    "daily": "precipitation_probability_max",
                    "forecast_days": 3, "timezone": "auto"},
            timeout=8,
        )
        data = r.json()
        proba = data["daily"]["precipitation_probability_max"][0]
        return 1.0 if proba >= 50 else 0.0
    except Exception:
        return 0.0


CIRCUIT_COORDS = {
    "Bahrain":        (26.0325, 50.5106),
    "Saudi Arabia":   (21.6319, 39.1044),
    "Australia":      (-37.8497, 144.968),
    "Japan":          (34.8431, 136.541),
    "China":          (31.3389, 121.220),
    "Miami":          (25.9581, -80.2389),
    "Emilia Romagna": (44.3439, 11.7167),
    "Monaco":         (43.7347, 7.42056),
    "Canada":         (45.5000, -73.5228),
    "Spain":          (41.5700, 2.26111),
    "Austria":        (47.2197, 14.7647),
    "Great Britain":  (52.0786, -1.01694),
    "Hungary":        (47.5789, 19.2486),
    "Belgium":        (50.4372, 5.97139),
    "Netherlands":    (52.3888, 4.54092),
    "Italy":          (45.6156, 9.28111),
    "Azerbaijan":     (40.3725, 49.8533),
    "Singapore":      (1.29139, 103.864),
    "United States":  (30.1328, -97.6411),
    "Mexico":         (19.4042, -99.0907),
    "Brazil":         (-23.7036, -46.6997),
    "Las Vegas":      (36.1147, -115.173),
    "Qatar":          (25.4900, 51.4542),
    "Abu Dhabi":      (24.4672, 54.6031),
}


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
    # Garde seulement les colonnes disponibles (rainfall peut manquer)
    available = [f for f in feat_cols if f in df_features.columns]
    X_sc = bundle["scaler"].transform(df_features[available].values)
    proba_rf  = bundle["rf"].predict_proba(X_sc)[:, 1]
    proba_dt  = bundle["dt"].predict_proba(X_sc)[:, 1]
    # SVC si présent dans le bundle
    if "svc" in bundle and bundle["svc"] is not None:
        proba_svc = bundle["svc"].predict_proba(X_sc)[:, 1]
        proba_avg = (proba_rf + proba_dt + proba_svc) / 3
    else:
        proba_svc = None
        proba_avg = (proba_rf + proba_dt) / 2
    df = df_features[["driverName", "constructorName"]].copy()
    df["proba_rf"]  = proba_rf
    df["proba_dt"]  = proba_dt
    if proba_svc is not None:
        df["proba_svc"] = proba_svc
    df["proba_avg"] = proba_avg
    if use_grid:
        df["grid"] = df_features["grid"].values
    if "rainfall" in df_features.columns:
        df["rainfall"] = df_features["rainfall"].values
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

    # ── Chronos tour par tour ──────────────────────────────────────────────
    st.markdown('<div class="section-title">⏱️ Chronos tour par tour</div>',
                unsafe_allow_html=True)
    st.caption("Les triangles ▲ indiquent les tours de sortie des stands.")

    lbl_col1, lbl_col2 = st.columns(2)
    with lbl_col1:
        lap_d1 = st.selectbox("Pilote 1 (chronos)", all_drivers, key="lap_d1", index=0)
    with lbl_col2:
        lap_d2 = st.selectbox("Pilote 2 (chronos)", all_drivers, key="lap_d2",
                              index=min(1, len(all_drivers) - 1))

    if lap_d1 != lap_d2:
        fig_laps = make_lap_by_lap_chart(session, lap_d1, lap_d2)
        st.plotly_chart(fig_laps, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("Sélectionnez deux pilotes différents.")

    # ── Carte mondiale des circuits ────────────────────────────────────────
    st.markdown('<div class="section-title">🌍 Carte mondiale des circuits F1</div>',
                unsafe_allow_html=True)

    with st.spinner("Chargement de l'historique des circuits…"):
        df_circ = load_circuits_races_df()

    if not df_circ.empty:
        df_circ["date"] = pd.to_datetime(df_circ["date"], errors="coerce")
        df_circ["day"]   = df_circ["date"].dt.day
        df_circ["month"] = df_circ["date"].dt.month

        year_min_circ = int(df_circ["year"].min())
        year_max_circ = int(df_circ["year"].max())

        map_col_a, map_col_b = st.columns([3, 1])
        with map_col_a:
            yr_range = st.slider(
                "Plage d'années", min_value=year_min_circ, max_value=year_max_circ,
                value=(year_min_circ, year_max_circ), key="circ_years",
            )
        with map_col_b:
            projection = st.selectbox(
                "Projection", ["natural earth", "mercator", "orthographic",
                               "equirectangular", "robinson", "mollweide"],
                key="circ_proj",
            )

        df_map = df_circ[(df_circ["year"] >= yr_range[0]) & (df_circ["year"] <= yr_range[1])]

        fig_geo = go.Figure(go.Scattergeo(
            lat=df_map["lat"], lon=df_map["lng"],
            text=df_map["race_name"] + " " + df_map["year"].astype(str),
            customdata=df_map[["country", "location", "year"]].values,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "%{customdata[1]}, %{customdata[0]}<extra></extra>"
            ),
            mode="markers",
            marker=dict(
                size=5, color=df_map["year"],
                colorscale=[[0, "#1a0a00"], [0.5, "#e8002d"], [1, "#00d2ff"]],
                colorbar=dict(title="Année", tickfont=dict(color="#888", size=9),
                              thickness=10, len=0.6),
                showscale=True,
            ),
        ))
        fig_geo.update_layout(
            height=520,
            paper_bgcolor=PLOT_BG,
            geo=dict(
                projection_type=projection,
                showland=True, landcolor="#1a1a2e",
                showocean=True, oceancolor="#0a0a0f",
                showcountries=True, countrycolor="#2a2a3a",
                showframe=False, bgcolor=PLOT_BG,
            ),
            font=dict(family="Barlow Condensed", color=FONT_COLOR),
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig_geo, use_container_width=True, config={"displayModeBar": False})
        st.caption(
            f"**{len(df_map):,}** Grands Prix entre {yr_range[0]} et {yr_range[1]} "
            f"sur **{df_map['name_circuit'].nunique()}** circuits différents."
        )

        # ── Course le jour de ton anniversaire ────────────────────────────
        st.markdown('<div class="section-title">🎂 Course le jour de ton anniversaire</div>',
                    unsafe_allow_html=True)

        bday = st.date_input(
            "Ton jour de naissance",
            value=datetime.date(1990, 6, 15),
            min_value=datetime.date(1950, 1, 1),
            max_value=datetime.date.today(),
            key="bday_input",
        )

        bday_races = df_circ[
            (df_circ["day"] == bday.day) & (df_circ["month"] == bday.month)
        ].sort_values("year")

        if bday_races.empty:
            st.info(f"Aucune course n'a eu lieu le {bday.day}/{bday.month} dans l'histoire de la F1.")
        else:
            st.success(
                f"**{len(bday_races)}** course(s) ont eu lieu un {bday.day}/{bday.month} "
                f"entre {int(bday_races['year'].min())} et {int(bday_races['year'].max())} !"
            )

            # Tableau
            disp_bday = bday_races[["year", "race_name", "name_circuit", "location", "country", "date"]].copy()
            disp_bday.columns = ["Année", "Grand Prix", "Circuit", "Ville", "Pays", "Date"]
            st.dataframe(disp_bday, use_container_width=True, hide_index=True)

            # Carte des courses du jour d'anniversaire
            fig_bday = go.Figure(go.Scattergeo(
                lat=bday_races["lat"], lon=bday_races["lng"],
                text=bday_races["race_name"] + " " + bday_races["year"].astype(str),
                hovertemplate="<b>%{text}</b><extra></extra>",
                mode="markers+text",
                textposition="top center",
                textfont=dict(color="#e8002d", size=9, family="Barlow Condensed"),
                marker=dict(size=10, color="#e8002d",
                            line=dict(color="white", width=1)),
            ))
            fig_bday.update_layout(
                height=380, paper_bgcolor=PLOT_BG,
                geo=dict(
                    projection_type="natural earth",
                    showland=True, landcolor="#1a1a2e",
                    showocean=True, oceancolor="#0a0a0f",
                    showcountries=True, countrycolor="#2a2a3a",
                    showframe=False, bgcolor=PLOT_BG,
                ),
                font=dict(family="Barlow Condensed", color=FONT_COLOR),
                margin=dict(l=0, r=0, t=10, b=0),
            )
            st.plotly_chart(fig_bday, use_container_width=True, config={"displayModeBar": False})
    else:
        st.warning("Données circuits indisponibles.")


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

    # Météo
    st.markdown('<div class="section-title">🌦️ Météo</div>', unsafe_allow_html=True)
    use_weather = st.checkbox("Récupérer la météo prévue (pluie/sec)", key="use_weather", value=True)
    rainfall = 0.0
    if use_weather:
        wc1, wc2 = st.columns([2, 1])
        with wc1:
            if st.button("🌦️ Récupérer la météo", key="fetch_weather_btn"):
                with st.spinner("Récupération météo…"):
                    rainfall = fetch_weather_forecast(pred_circuit_name)
                st.session_state["rainfall"] = rainfall
                if rainfall == 1.0:
                    st.warning("⛈️ Pluie probable — le modèle en tient compte.")
                else:
                    st.success("☀️ Temps sec prévu.")
        with wc2:
            rainfall = st.session_state.get("rainfall", 0.0)
            manual_rain = st.checkbox("Forcer pluie", value=(rainfall == 1.0), key="manual_rain")
            if manual_rain:
                rainfall = 1.0
                st.session_state["rainfall"] = 1.0

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

        # Ajoute rainfall aux features
        _rainfall = st.session_state.get("rainfall", 0.0) if use_weather else 0.0
        df_feat = build_prediction_df(drv_df, cst_df, grid_data, use_grid, pred_round)
        if not df_feat.empty:
            df_feat["rainfall"] = _rainfall
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
        if "proba_svc" in df_pred_result.columns:
            fig_p.add_trace(go.Bar(x=df_pred_result["driverName"], y=df_pred_result["proba_svc"]*100,
                                   name="SVC", marker_color="#00ff88", opacity=0.85))
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
