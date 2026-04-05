"""
app.py — Comparateur de télémétrie F1
======================================
Lance avec :  streamlit run app.py
"""

import warnings
import datetime
warnings.filterwarnings("ignore")

import streamlit as st
import fastf1
import fastf1.plotting
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path

# ── Cache fastf1 ───────────────────────────────────────────────────────────────
CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))

# ── Config page ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="F1 Telemetry",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;900&family=Barlow:wght@300;400;500&display=swap');

  html, body, [class*="css"] {
    font-family: 'Barlow', sans-serif;
    background-color: #0a0a0f;
    color: #e8e8e8;
  }
  .main { background-color: #0a0a0f; }
  .block-container { padding-top: 2rem; padding-bottom: 2rem; }

  /* Header */
  .f1-header {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900;
    font-size: 3.2rem;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    background: linear-gradient(90deg, #e8002d 0%, #ff6b6b 50%, #ffffff 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 0;
    line-height: 1;
  }
  .f1-sub {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 400;
    font-size: 1rem;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    color: #666;
    margin-top: 0.2rem;
    margin-bottom: 2rem;
  }

  /* Cards pilotes */
  .driver-card {
    background: #13131a;
    border-radius: 8px;
    padding: 1.2rem 1.5rem;
    border-left: 4px solid var(--color);
    margin-bottom: 1rem;
  }
  .driver-name {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 700;
    font-size: 1.4rem;
    text-transform: uppercase;
    color: var(--color);
    letter-spacing: 0.05em;
  }
  .driver-meta {
    font-size: 0.8rem;
    color: #666;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  /* Metric cards */
  .metric-row {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }
  .metric-card {
    background: #13131a;
    border-radius: 6px;
    padding: 1rem 1.4rem;
    flex: 1;
    border-top: 2px solid #e8002d;
  }
  .metric-label {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    color: #666;
    margin-bottom: 0.3rem;
  }
  .metric-value {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 700;
    font-size: 1.6rem;
    color: #ffffff;
  }
  .metric-delta {
    font-size: 0.75rem;
    color: #888;
    margin-top: 0.1rem;
  }

  /* Sidebar */
  section[data-testid="stSidebar"] {
    background-color: #0d0d14 !important;
    border-right: 1px solid #1e1e2e;
  }
  section[data-testid="stSidebar"] .stSelectbox label,
  section[data-testid="stSidebar"] .stMarkdown p {
    color: #aaa !important;
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  /* Divider */
  .section-title {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 600;
    font-size: 0.85rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #e8002d;
    margin: 1.5rem 0 0.8rem 0;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid #1e1e2e;
  }

  /* Buttons */
  .stButton > button {
    background: #e8002d !important;
    color: white !important;
    border: none !important;
    font-family: 'Barlow Condensed', sans-serif !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    padding: 0.6rem 2rem !important;
    border-radius: 4px !important;
    width: 100%;
  }
  .stButton > button:hover {
    background: #ff1a3e !important;
    transform: translateY(-1px);
  }

  /* Spinner */
  .stSpinner > div { border-top-color: #e8002d !important; }

  /* Selectbox */
  .stSelectbox > div > div {
    background-color: #13131a !important;
    border-color: #2a2a3a !important;
    color: #e8e8e8 !important;
  }
</style>
""", unsafe_allow_html=True)


# ── Données statiques ──────────────────────────────────────────────────────────

CIRCUITS = [
    "Bahrain", "Saudi Arabia", "Australia", "Japan", "China",
    "Miami", "Emilia Romagna", "Monaco", "Canada", "Spain",
    "Austria", "Great Britain", "Hungary", "Belgium", "Netherlands",
    "Italy", "Azerbaijan", "Singapore", "United States", "Mexico",
    "Brazil", "Las Vegas", "Qatar", "Abu Dhabi",
]

YEARS = list(range(datetime.date.today().year, 2017, -1))

# Couleurs équipes fastf1 (fallback si non dispo)
DRIVER_COLORS = {
    "default_1": "#e8002d",
    "default_2": "#00d2ff",
}


# ── Fonctions utilitaires ──────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def get_session_drivers(year: int, circuit: str) -> list[str]:
    """Retourne la liste des abréviations pilotes pour une session."""
    try:
        session = fastf1.get_session(year, circuit, "R")
        session.load(laps=True, telemetry=False, weather=False, messages=False)
        drivers = session.laps["Driver"].unique().tolist()
        return sorted(drivers)
    except Exception as e:
        return []


@st.cache_data(show_spinner=False)
def get_driver_lap_numbers(year: int, circuit: str, driver: str) -> list[int]:
    """Retourne la liste des numéros de tours valides pour un pilote."""
    try:
        session = fastf1.get_session(year, circuit, "R")
        session.load(laps=True, telemetry=False, weather=False, messages=False)
        laps = session.laps.pick_driver(driver).pick_quicklaps()
        return sorted(laps["LapNumber"].astype(int).tolist())
    except Exception:
        return []


@st.cache_data(show_spinner=False)
def load_lap_telemetry(
    year: int, circuit: str, driver: str, lap_mode: str, lap_number: int = 0
) -> dict | None:
    """
    Charge la télémétrie d'un tour.
    lap_mode : "fastest" | "specific"
    lap_number : ignoré si lap_mode == "fastest"
    """
    try:
        session = fastf1.get_session(year, circuit, "R")
        session.load(laps=True, telemetry=True, weather=False, messages=False)

        driver_laps = session.laps.pick_driver(driver)

        if lap_mode == "fastest":
            lap = driver_laps.pick_fastest()
            lap_label = "Meilleur tour"
        else:
            lap = driver_laps[driver_laps["LapNumber"] == lap_number]
            if lap.empty:
                st.error(f"Tour {lap_number} introuvable pour {driver}")
                return None
            lap = lap.iloc[0]
            lap_label = f"Tour {lap_number}"

        if lap is None or (hasattr(lap, "empty") and lap.empty):
            return None

        tel = lap.get_telemetry().add_distance()

        try:
            color = fastf1.plotting.get_driver_color(driver, session)
        except Exception:
            color = None

        return {
            "driver":    driver,
            "year":      year,
            "circuit":   circuit,
            "lap_time":  lap["LapTime"],
            "lap_label": lap_label,
            "lap_number": int(lap["LapNumber"]) if lap_mode == "fastest" else lap_number,
            "telemetry": tel,
            "color":     color,
        }
    except Exception as e:
        st.error(f"Erreur chargement {driver} {year} {circuit} : {e}")
        return None


def format_laptime(td) -> str:
    """Formate un timedelta en MM:SS.mmm"""
    try:
        total_s = td.total_seconds()
        minutes = int(total_s // 60)
        seconds = total_s % 60
        return f"{minutes}:{seconds:06.3f}"
    except Exception:
        return "N/A"


def delta_label(v1, v2, unit="", lower_is_better=True) -> str:
    """Génère un label de delta coloré."""
    if v1 is None or v2 is None:
        return ""
    diff = v1 - v2
    sign = "+" if diff > 0 else ""
    arrow = "▲" if diff > 0 else "▼"
    return f"{arrow} {sign}{diff:.1f}{unit}"


# ── Graphiques Plotly ──────────────────────────────────────────────────────────

PLOT_BG = "#0a0a0f"
GRID_COLOR = "#1e1e2e"
FONT_COLOR = "#888888"


def make_telemetry_figure(data1: dict, data2: dict) -> go.Figure:
    """
    Crée la figure principale avec 4 sous-graphiques :
    Speed / Throttle / Brake / Gear
    en fonction de la distance au tour.
    """
    t1 = data1["telemetry"]
    t2 = data2["telemetry"]
    c1 = data1["color"] or DRIVER_COLORS["default_1"]
    c2 = data2["color"] or DRIVER_COLORS["default_2"]
    d1 = data1["driver"]
    d2 = data2["driver"]

    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        subplot_titles=("VITESSE (km/h)", "ACCÉLÉRATEUR (%)", "FREIN (%)", "RAPPORT"),
        row_heights=[0.35, 0.22, 0.22, 0.21],
    )

    # Channels : Speed, Throttle, Brake, nGear
    channels = [
        ("Speed",    1, "%{y:.0f} km/h"),
        ("Throttle", 2, "%{y:.0f}%%"),
        ("Brake",    3, "%{y:.0f}%%"),
        ("nGear",    4, "Rapport %{y}"),
    ]

    for col, (channel, row, htmpl) in enumerate(channels):
        if channel not in t1.columns or channel not in t2.columns:
            continue

        # Pilote 1
        fig.add_trace(go.Scatter(
            x=t1["Distance"], y=t1[channel],
            name=f"{d1} ({data1['year']})",
            line=dict(color=c1, width=2),
            hovertemplate=f"<b>{d1}</b><br>Dist: %{{x:.0f}}m<br>" + htmpl + "<extra></extra>",
            legendgroup="p1",
            showlegend=(row == 1),
        ), row=row, col=1)

        # Pilote 2
        fig.add_trace(go.Scatter(
            x=t2["Distance"], y=t2[channel],
            name=f"{d2} ({data2['year']})",
            line=dict(color=c2, width=2, dash="dot"),
            hovertemplate=f"<b>{d2}</b><br>Dist: %{{x:.0f}}m<br>" + htmpl + "<extra></extra>",
            legendgroup="p2",
            showlegend=(row == 1),
        ), row=row, col=1)

    # Mise en forme globale
    fig.update_layout(
        height=700,
        paper_bgcolor=PLOT_BG,
        plot_bgcolor=PLOT_BG,
        font=dict(family="Barlow Condensed, sans-serif", color=FONT_COLOR, size=11),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right", x=1,
            font=dict(size=13, color="#cccccc"),
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=60, r=30, t=60, b=40),
        hovermode="x unified",
    )

    # Axes
    for i in range(1, 5):
        fig.update_xaxes(
            row=i, col=1,
            gridcolor=GRID_COLOR, zeroline=False,
            tickfont=dict(color=FONT_COLOR),
            title_font=dict(color=FONT_COLOR),
        )
        fig.update_yaxes(
            row=i, col=1,
            gridcolor=GRID_COLOR, zeroline=False,
            tickfont=dict(color=FONT_COLOR),
        )

    # Titre axe X uniquement en bas
    fig.update_xaxes(title_text="Distance (m)", row=4, col=1,
                     title_font=dict(color="#888", size=11))

    # Titres sous-graphiques en rouge F1
    for annotation in fig.layout.annotations:
        annotation.font.color = "#e8002d"
        annotation.font.size = 11
        annotation.font.family = "Barlow Condensed, sans-serif"

    return fig


def make_delta_figure(data1: dict, data2: dict) -> go.Figure:
    """
    Graphique delta de vitesse entre les deux pilotes (pilote1 - pilote2).
    Zone verte = pilote1 plus rapide, zone rouge = pilote2 plus rapide.
    """
    t1 = data1["telemetry"].copy()
    t2 = data2["telemetry"].copy()
    c1 = data1["color"] or DRIVER_COLORS["default_1"]
    c2 = data2["color"] or DRIVER_COLORS["default_2"]

    # Interpolation sur la même grille de distance
    dist_max = min(t1["Distance"].max(), t2["Distance"].max())
    dist_grid = np.linspace(0, dist_max, 1000)

    spd1 = np.interp(dist_grid, t1["Distance"], t1["Speed"])
    spd2 = np.interp(dist_grid, t2["Distance"], t2["Speed"])
    delta = spd1 - spd2

    fig = go.Figure()

    # Zone positive (p1 plus vite)
    fig.add_trace(go.Scatter(
        x=dist_grid, y=np.where(delta > 0, delta, 0),
        fill="tozeroy",
        fillcolor=f"rgba({int(c1[1:3],16)},{int(c1[3:5],16)},{int(c1[5:7],16)},0.25)",
        line=dict(width=0),
        name=f"{data1['driver']} plus rapide",
        hoverinfo="skip",
    ))

    # Zone négative (p2 plus vite)
    fig.add_trace(go.Scatter(
        x=dist_grid, y=np.where(delta < 0, delta, 0),
        fill="tozeroy",
        fillcolor=f"rgba({int(c2[1:3],16)},{int(c2[3:5],16)},{int(c2[5:7],16)},0.25)",
        line=dict(width=0),
        name=f"{data2['driver']} plus rapide",
        hoverinfo="skip",
    ))

    # Ligne delta
    fig.add_trace(go.Scatter(
        x=dist_grid, y=delta,
        line=dict(color="#ffffff", width=1.5),
        name="Δ Vitesse",
        hovertemplate="Dist: %{x:.0f}m<br>Δ: %{y:.1f} km/h<extra></extra>",
    ))

    # Ligne zéro
    fig.add_hline(y=0, line_dash="dash", line_color="#333", line_width=1)

    fig.update_layout(
        title=dict(
            text=f"DELTA VITESSE — {data1['driver']} {data1['year']} vs {data2['driver']} {data2['year']}",
            font=dict(family="Barlow Condensed", size=13, color="#e8002d"),
        ),
        height=220,
        paper_bgcolor=PLOT_BG,
        plot_bgcolor=PLOT_BG,
        font=dict(family="Barlow Condensed, sans-serif", color=FONT_COLOR),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            font=dict(size=11, color="#cccccc"),
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=60, r=30, t=50, b=40),
        xaxis=dict(gridcolor=GRID_COLOR, zeroline=False,
                   title="Distance (m)", title_font=dict(color="#888", size=11)),
        yaxis=dict(gridcolor=GRID_COLOR, zeroline=False,
                   title="Δ km/h", title_font=dict(color="#888", size=11)),
        hovermode="x unified",
    )
    return fig


SPEED_COLORSCALE = [
    [0.0, "#1a0a00"],
    [0.3, "#cc2200"],
    [0.6, "#ffaa00"],
    [0.8, "#ffee00"],
    [1.0, "#00ffcc"],
]

def _base_map_layout(title: str, height: int = 360) -> dict:
    """Layout commun aux trois cartes."""
    return dict(
        height=height,
        paper_bgcolor=PLOT_BG,
        plot_bgcolor=PLOT_BG,
        font=dict(family="Barlow Condensed, sans-serif", color=FONT_COLOR),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            font=dict(size=11, color="#cccccc"),
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(visible=False, scaleanchor="y", scaleratio=1),
        yaxis=dict(visible=False),
        title=dict(
            text=title,
            font=dict(family="Barlow Condensed", size=12, color="#e8002d"),
        ),
    )


def make_track_single(data: dict, label: str) -> go.Figure | None:
    """Carte vitesse d'un seul pilote."""
    t = data["telemetry"]
    if "X" not in t.columns or "Y" not in t.columns:
        return None

    # Fond gris du circuit (contour)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=t["X"], y=t["Y"],
        mode="lines",
        line=dict(color="#2a2a3a", width=8),
        hoverinfo="skip",
        showlegend=False,
    ))
    # Points colorés par vitesse
    fig.add_trace(go.Scatter(
        x=t["X"], y=t["Y"],
        mode="markers",
        marker=dict(
            color=t["Speed"],
            colorscale=SPEED_COLORSCALE,
            size=4,
            colorbar=dict(
                title=dict(text="km/h", font=dict(color="#888", size=9)),
                tickfont=dict(color="#888", size=8),
                thickness=10, len=0.7,
                x=1.02,
            ),
            showscale=True,
        ),
        name=label,
        hovertemplate=f"<b>{label}</b><br>Vitesse: %{{marker.color:.0f}} km/h<extra></extra>",
    ))
    fig.update_layout(**_base_map_layout(label))
    return fig


def make_track_delta_map(data1: dict, data2: dict, label1: str, label2: str) -> go.Figure | None:
    """
    Carte du circuit colorée par le delta de vitesse (pilote1 - pilote2).
    Vert = pilote1 plus rapide, Rouge = pilote2 plus rapide.
    """
    t1 = data1["telemetry"]
    t2 = data2["telemetry"]
    if "X" not in t1.columns or "Y" not in t1.columns:
        return None

    # Interpolation du delta sur la grille de distance de t1
    import numpy as np
    dist_max = min(t1["Distance"].max(), t2["Distance"].max())
    mask1 = t1["Distance"] <= dist_max
    mask2 = t2["Distance"] <= dist_max

    x_interp = t1.loc[mask1, "X"].values
    y_interp = t1.loc[mask1, "Y"].values
    dist1    = t1.loc[mask1, "Distance"].values
    spd1     = t1.loc[mask1, "Speed"].values
    spd2_interp = np.interp(dist1, t2.loc[mask2, "Distance"].values, t2.loc[mask2, "Speed"].values)
    delta    = spd1 - spd2_interp

    fig = go.Figure()
    # Fond circuit
    fig.add_trace(go.Scatter(
        x=x_interp, y=y_interp,
        mode="lines",
        line=dict(color="#2a2a3a", width=8),
        hoverinfo="skip", showlegend=False,
    ))
    # Delta coloré
    fig.add_trace(go.Scatter(
        x=x_interp, y=y_interp,
        mode="markers",
        marker=dict(
            color=delta,
            colorscale=[
                [0.0, "#e8002d"],
                [0.5, "#1e1e2e"],
                [1.0, "#00d2ff"],
            ],
            size=4,
            colorbar=dict(
                title=dict(text="Δ km/h", font=dict(color="#888", size=9)),
                tickfont=dict(color="#888", size=8),
                thickness=10, len=0.7,
                x=1.02,
            ),
            showscale=True,
            cmin=float(-abs(delta).max()),
            cmax=float(abs(delta).max()),
        ),
        name=f"Δ vitesse",
        hovertemplate="<b>Δ</b> %{marker.color:.1f} km/h<extra></extra>",
    ))

    fig.update_layout(**_base_map_layout(f"DELTA CARTE — {label1} (bleu) vs {label2} (rouge)"))
    return fig


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div style='font-family: Barlow Condensed, sans-serif;
                font-weight: 900; font-size: 1.5rem;
                color: #e8002d; letter-spacing: 0.1em;
                text-transform: uppercase; margin-bottom: 1.5rem;'>
        ⬡ Configuration
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<p class="section-title">Circuit</p>', unsafe_allow_html=True)
    circuit = st.selectbox("Circuit", CIRCUITS, label_visibility="collapsed")

    st.markdown('<p class="section-title">Pilote 1</p>', unsafe_allow_html=True)
    year1 = st.selectbox("Année 1", YEARS, key="year1", label_visibility="collapsed",
                         format_func=lambda y: f"Saison {y}")

    drivers1 = get_session_drivers(year1, circuit)
    driver1 = st.selectbox(
        "Pilote 1", drivers1 if drivers1 else ["—"],
        key="driver1", label_visibility="collapsed"
    )
    if not drivers1:
        st.caption("⚠️ Session non disponible")

    lap_mode1 = st.radio(
        "Tour P1", ["Meilleur tour", "Tour spécifique"],
        key="lap_mode1", horizontal=True, label_visibility="collapsed"
    )
    lap_number1 = 0
    if lap_mode1 == "Tour spécifique" and drivers1:
        laps1 = get_driver_lap_numbers(year1, circuit, driver1)
        if laps1:
            lap_number1 = st.selectbox(
                "N° tour P1", laps1, key="lap_num1",
                label_visibility="collapsed",
                format_func=lambda n: f"Tour {n}",
            )
        else:
            st.caption("⚠️ Tours non disponibles")

    st.markdown('<p class="section-title">Pilote 2</p>', unsafe_allow_html=True)
    year2 = st.selectbox("Année 2", YEARS, key="year2", label_visibility="collapsed",
                         format_func=lambda y: f"Saison {y}",
                         index=min(1, len(YEARS)-1))

    drivers2 = get_session_drivers(year2, circuit)
    driver2 = st.selectbox(
        "Pilote 2", drivers2 if drivers2 else ["—"],
        key="driver2", label_visibility="collapsed",
        index=min(1, len(drivers2)-1) if len(drivers2) > 1 else 0,
    )
    if not drivers2:
        st.caption("⚠️ Session non disponible")

    lap_mode2 = st.radio(
        "Tour P2", ["Meilleur tour", "Tour spécifique"],
        key="lap_mode2", horizontal=True, label_visibility="collapsed"
    )
    lap_number2 = 0
    if lap_mode2 == "Tour spécifique" and drivers2:
        laps2 = get_driver_lap_numbers(year2, circuit, driver2)
        if laps2:
            lap_number2 = st.selectbox(
                "N° tour P2", laps2, key="lap_num2",
                label_visibility="collapsed",
                format_func=lambda n: f"Tour {n}",
            )
        else:
            st.caption("⚠️ Tours non disponibles")

    st.markdown("<br>", unsafe_allow_html=True)
    compare_btn = st.button("🏁  Comparer", use_container_width=True)

    st.markdown("""
    <div style='margin-top: 2rem; padding-top: 1rem;
                border-top: 1px solid #1e1e2e;
                font-size: 0.7rem; color: #444;
                line-height: 1.6;'>
        Données : FastF1 + Ergast API<br>
        Meilleur tour ou tour au choix<br>
        Cache local activé
    </div>
    """, unsafe_allow_html=True)


# ── Main ───────────────────────────────────────────────────────────────────────

st.markdown('<div class="f1-header">F1 Telemetry</div>', unsafe_allow_html=True)
st.markdown('<div class="f1-sub">Comparateur de télémétrie · Meilleur tour ou tour spécifique</div>',
            unsafe_allow_html=True)

if not compare_btn:
    # État initial
    st.markdown("""
    <div style='text-align: center; padding: 5rem 2rem;
                color: #333; font-family: Barlow Condensed, sans-serif;'>
        <div style='font-size: 5rem; margin-bottom: 1rem;'>🏎️</div>
        <div style='font-size: 1.2rem; letter-spacing: 0.15em;
                    text-transform: uppercase; color: #444;'>
            Sélectionnez un circuit, deux pilotes<br>et cliquez sur Comparer
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── Chargement des données ─────────────────────────────────────────────────────

col_load1, col_load2 = st.columns(2)

with col_load1:
    _mode1 = "fastest" if lap_mode1 == "Meilleur tour" else "specific"
    with st.spinner(f"Chargement {driver1} {year1}…"):
        data1 = load_lap_telemetry(year1, circuit, driver1, _mode1, lap_number1)

with col_load2:
    _mode2 = "fastest" if lap_mode2 == "Meilleur tour" else "specific"
    with st.spinner(f"Chargement {driver2} {year2}…"):
        data2 = load_lap_telemetry(year2, circuit, driver2, _mode2, lap_number2)

if data1 is None or data2 is None:
    st.error("Impossible de charger les données. Vérifiez votre connexion ou essayez une autre combinaison.")
    st.stop()

# ── Cards pilotes ──────────────────────────────────────────────────────────────

c1_hex = data1["color"] or DRIVER_COLORS["default_1"]
c2_hex = data2["color"] or DRIVER_COLORS["default_2"]
lt1 = format_laptime(data1["lap_time"])
lt2 = format_laptime(data2["lap_time"])
# Ajoute l'année au nom si les deux pilotes sont identiques
same_driver = (driver1 == driver2)
label1 = f"{driver1} {year1}" if same_driver else driver1
label2 = f"{driver2} {year2}" if same_driver else driver2

col1, col2 = st.columns(2)
with col1:
    st.markdown(f"""
    <div class="driver-card" style="--color: {c1_hex}">
        <div class="driver-name">{label1}</div>
        <div class="driver-meta">{circuit} · {year1} · {data1['lap_label']} (T{data1['lap_number']})</div>
        <div style="font-family: 'Barlow Condensed'; font-size: 2rem;
                    font-weight: 700; color: {c1_hex}; margin-top: 0.5rem;">
            {lt1}
        </div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="driver-card" style="--color: {c2_hex}">
        <div class="driver-name">{label2}</div>
        <div class="driver-meta">{circuit} · {year2} · {data2['lap_label']} (T{data2['lap_number']})</div>
        <div style="font-family: 'Barlow Condensed'; font-size: 2rem;
                    font-weight: 700; color: {c2_hex}; margin-top: 0.5rem;">
            {lt2}
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── Stats résumé ───────────────────────────────────────────────────────────────

t1 = data1["telemetry"]
t2 = data2["telemetry"]

vmax1 = t1["Speed"].max() if "Speed" in t1 else None
vmax2 = t2["Speed"].max() if "Speed" in t2 else None
vmoy1 = t1["Speed"].mean() if "Speed" in t1 else None
vmoy2 = t2["Speed"].mean() if "Speed" in t2 else None
thr1  = (t1["Throttle"] > 95).mean() * 100 if "Throttle" in t1 else None
thr2  = (t2["Throttle"] > 95).mean() * 100 if "Throttle" in t2 else None
brk1  = (t1["Brake"] > 50).mean() * 100 if "Brake" in t1 else None
brk2  = (t2["Brake"] > 50).mean() * 100 if "Brake" in t2 else None

st.markdown('<div class="section-title">Statistiques du tour</div>', unsafe_allow_html=True)

cols = st.columns(4)
stats = [
    ("Vmax", vmax1, vmax2, "km/h", True),
    ("Vitesse moy.", vmoy1, vmoy2, "km/h", True),
    ("Plein gaz", thr1, thr2, "%", True),
    ("Freinage", brk1, brk2, "%", False),
]
for col, (label, v1, v2, unit, higher_better) in zip(cols, stats):
    with col:
        if v1 is not None and v2 is not None:
            diff = v1 - v2
            sign = "+" if diff > 0 else ""
            better = (diff > 0) == higher_better
            delta_color = c1_hex if better else c2_hex
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{v1:.0f}<span style='font-size:0.9rem;color:#666'> {unit}</span></div>
                <div class="metric-delta" style="color:{delta_color}">
                    {sign}{diff:.1f} {unit} vs {label2}
                </div>
            </div>
            """, unsafe_allow_html=True)

# ── Graphiques télémétrie ──────────────────────────────────────────────────────

st.markdown('<div class="section-title">Télémétrie comparée</div>', unsafe_allow_html=True)
fig_tel = make_telemetry_figure(data1, data2)
st.plotly_chart(fig_tel, use_container_width=True, config={"displayModeBar": False})

# ── Delta vitesse ──────────────────────────────────────────────────────────────

st.markdown('<div class="section-title">Delta de vitesse</div>', unsafe_allow_html=True)
fig_delta = make_delta_figure(data1, data2)
st.plotly_chart(fig_delta, use_container_width=True, config={"displayModeBar": False})

# ── Carte circuit ──────────────────────────────────────────────────────────────

if "X" in t1.columns and "Y" in t1.columns:
    st.markdown('<div class="section-title">Cartes du circuit</div>', unsafe_allow_html=True)

    # Deux cartes individuelles côte à côte
    map_col1, map_col2 = st.columns(2)
    with map_col1:
        fig_map1 = make_track_single(data1, f"{label1} — Vitesse")
        if fig_map1:
            st.plotly_chart(fig_map1, use_container_width=True, config={"displayModeBar": False})
    with map_col2:
        fig_map2 = make_track_single(data2, f"{label2} — Vitesse")
        if fig_map2:
            st.plotly_chart(fig_map2, use_container_width=True, config={"displayModeBar": False})

    # Carte delta pleine largeur
    fig_map_delta = make_track_delta_map(data1, data2, label1, label2)
    if fig_map_delta:
        st.plotly_chart(fig_map_delta, use_container_width=True, config={"displayModeBar": False})
