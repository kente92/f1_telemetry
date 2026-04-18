"""
main.py - F1 App API (FastAPI)
Strategie donnees :
  - CSV locaux (data/) charges en memoire au demarrage
  - Mise a jour automatique : verifie Jolpica toutes les 6h
  - Jolpica sollicite uniquement pour : standings live, qualifs, meteo, maj auto
"""

import asyncio, datetime, logging, os, tempfile, time, json
from functools import lru_cache
from pathlib import Path

import fastf1
import fastf1.plotting
import joblib, pandas as pd, requests
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("f1_api")

_VPS_CACHE = "/var/cache/f1"
_CACHE_DIR = _VPS_CACHE if (os.path.isdir(_VPS_CACHE) and os.access(_VPS_CACHE, os.W_OK)) else tempfile.gettempdir()
fastf1.Cache.enable_cache(_CACHE_DIR)

DATA_DIR   = Path(__file__).parent / "data"
MODELS_DIR = Path(__file__).parent / "models"
DATA_DIR.mkdir(exist_ok=True)
JOLPICA = "https://api.jolpi.ca/ergast/f1"

app = FastAPI(title="F1 API", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

CIRCUITS = ["Bahrain","Saudi Arabia","Australia","Japan","China","Miami","Emilia Romagna",
    "Monaco","Canada","Spain","Austria","Great Britain","Hungary","Belgium","Netherlands",
    "Italy","Azerbaijan","Singapore","United States","Mexico","Brazil","Las Vegas","Qatar","Abu Dhabi"]

CIRCUIT_COORDS = {
    "Bahrain":(26.0325,50.5106),"Saudi Arabia":(21.6319,39.1044),"Australia":(-37.8497,144.968),
    "Japan":(34.8431,136.541),"China":(31.3389,121.220),"Miami":(25.9581,-80.2389),
    "Emilia Romagna":(44.3439,11.7167),"Monaco":(43.7347,7.42056),"Canada":(45.5,-73.5228),
    "Spain":(41.57,2.26111),"Austria":(47.2197,14.7647),"Great Britain":(52.0786,-1.01694),
    "Hungary":(47.5789,19.2486),"Belgium":(50.4372,5.97139),"Netherlands":(52.3888,4.54092),
    "Italy":(45.6156,9.28111),"Azerbaijan":(40.3725,49.8533),"Singapore":(1.29139,103.864),
    "United States":(30.1328,-97.6411),"Mexico":(19.4042,-99.0907),"Brazil":(-23.7036,-46.6997),
    "Las Vegas":(36.1147,-115.173),"Qatar":(25.49,51.4542),"Abu Dhabi":(24.4672,54.6031),
}

FEATURE_COLS_GRID    = ["grid","driverPoints","driverStandingPosition","driverWins","constructorPoints","constructorStandingPosition","constructorWins"]
FEATURE_COLS_NO_GRID = ["driverPoints","driverStandingPosition","driverWins","constructorPoints","constructorStandingPosition","constructorWins"]


class DataStore:
    """
    Charge et maintient races.csv, results_full.csv, sprint_results_full.csv en memoire.
    Mise a jour automatique toutes les 6h via Jolpica pour les nouvelles courses.
    """

    def __init__(self):
        self.races          = pd.DataFrame()
        self.results        = pd.DataFrame()
        self.sprint_results = pd.DataFrame()
        self.driver_codes   = {}
        self.last_check     = 0.0
        self._loaded        = False

    def load_from_csv(self):
        # races.csv
        p = DATA_DIR / "races.csv"
        if p.exists():
            self.races = pd.read_csv(p, na_values="\\N")
            self.races["date"] = pd.to_datetime(self.races["date"], errors="coerce")
            log.info(f"races.csv: {len(self.races)} courses ({int(self.races['year'].min())}-{int(self.races['year'].max())})")
        else:
            log.warning("races.csv introuvable")
            self.races = pd.DataFrame(columns=["year","round","raceName","date","circuitName","country","location","lat","lng"])

        # drivers_codes.csv (driverRef -> code officiel)
        dc = DATA_DIR / "drivers_codes.csv"
        if dc.exists():
            df_codes = pd.read_csv(dc, na_values="\\N", usecols=["driverRef","code"])
            self.driver_codes = dict(zip(df_codes["driverRef"], df_codes["code"]))
            log.info(f"drivers_codes.csv: {len(self.driver_codes)} pilotes")
        else:
            self.driver_codes = {}

        # results_full.csv
        rp = DATA_DIR / "results_full.csv"
        if rp.exists():
            self.results = pd.read_csv(rp, na_values="\\N")
            log.info(f"results_full.csv: {len(self.results)} resultats")
        else:
            log.warning("results_full.csv introuvable — utilisation FastF1 uniquement")
            self.results = pd.DataFrame()

        # sprint_results_full.csv
        sp = DATA_DIR / "sprint_results_full.csv"
        if sp.exists():
            self.sprint_results = pd.read_csv(sp, na_values="\\N")
            log.info(f"sprint_results_full.csv: {len(self.sprint_results)} resultats sprint")
        else:
            self.sprint_results = pd.DataFrame()

        self._loaded = True

    def latest_year_round(self):
        if self.races.empty:
            return (datetime.date.today().year - 1, 0)
        last = self.races.sort_values(["year","round"]).iloc[-1]
        return int(last["year"]), int(last["round"])

    def _fetch_season_races(self, year):
        try:
            r = requests.get(f"{JOLPICA}/{year}/races.json?limit=30", timeout=10)
            r.raise_for_status()
            rows = []
            for race in r.json()["MRData"]["RaceTable"]["Races"]:
                c = race["Circuit"]
                rows.append({"year":int(race["season"]),"round":int(race["round"]),
                    "raceName":race["raceName"],"date":race["date"],
                    "circuitName":c["circuitName"],"country":c["Location"]["country"],
                    "location":c["Location"]["locality"],
                    "lat":float(c["Location"]["lat"]),"lng":float(c["Location"]["long"])})
            return rows
        except Exception as e:
            log.warning(f"Jolpica {year}: {e}")
            return []

    def _update_results_for_race(self, year: int, round_num: int, race_name: str, sprint: bool = False):
        """Recupere et sauvegarde les resultats d une course depuis Jolpica."""
        try:
            import time as _time
            _time.sleep(1.5)
            endpoint = "sprint" if sprint else "results"
            r = requests.get(f"{JOLPICA}/{year}/{round_num}/{endpoint}.json?limit=30", timeout=10)
            r.raise_for_status()
            races_raw = r.json()["MRData"]["RaceTable"]["Races"]
            if not races_raw:
                return
            result_key = "SprintResults" if sprint else "Results"
            rows = []
            for res in races_raw[0].get(result_key, []):
                rows.append({
                    "year": year, "round": round_num, "raceName": race_name,
                    "positionOrder": int(res.get("position", 0)),
                    "driverRef":     res["Driver"]["driverId"],
                    "driverName":    f"{res['Driver']['givenName']} {res['Driver']['familyName']}",
                    "nationality":   res["Driver"].get("nationality",""),
                    "constructorRef":res["Constructor"]["constructorId"],
                    "teamName":      res["Constructor"]["name"],
                    "grid":          int(res.get("grid", 0)),
                    "points":        float(res.get("points", 0)),
                    "laps":          int(res.get("laps", 0)),
                    "status":        res.get("status",""),
                    "fastestLapTime":res.get("FastestLap",{}).get("Time",{}).get("time",""),
                })
            if not rows:
                return
            ndf = pd.DataFrame(rows)
            if sprint:
                self.sprint_results = (
                    pd.concat([self.sprint_results, ndf], ignore_index=True)
                    .drop_duplicates(subset=["year","round","driverRef"])
                    .sort_values(["year","round","positionOrder"]).reset_index(drop=True))
                self.sprint_results.to_csv(DATA_DIR/"sprint_results_full.csv", index=False)
            else:
                self.results = (
                    pd.concat([self.results, ndf], ignore_index=True)
                    .drop_duplicates(subset=["year","round","driverRef"])
                    .sort_values(["year","round","positionOrder"]).reset_index(drop=True))
                self.results.to_csv(DATA_DIR/"results_full.csv", index=False)
            label = "Sprint" if sprint else "Course"
            log.info(f"{label} {year} R{round_num} ajoutee ({len(rows)} pilotes)")
        except Exception as e:
            log.warning(f"Impossible de recuperer {'sprint' if sprint else 'resultats'} {year} R{round_num}: {e}")

    def check_and_update(self, force=False):
        now = time.time()
        if not force and (now - self.last_check) < 6*3600:
            return 0
        self.last_check = now
        today = datetime.date.today()
        current_year = today.year
        known = set()
        if not self.races.empty:
            known = set(zip(self.races["year"].astype(int), self.races["round"].astype(int)))
        start_year = max(y for y,_ in known) if known else current_year
        new_rows = []
        for year in range(start_year, current_year + 1):
            fetched = self._fetch_season_races(year)
            if not fetched:
                continue
            for row in fetched:
                key = (row["year"], row["round"])
                if key in known:
                    continue
                try:
                    rd = datetime.date.fromisoformat(row["date"])
                except Exception:
                    continue
                if rd <= today:
                    new_rows.append(row)
                    known.add(key)
        if new_rows:
            ndf = pd.DataFrame(new_rows)
            ndf["date"] = pd.to_datetime(ndf["date"], errors="coerce")
            self.races = (pd.concat([self.races, ndf], ignore_index=True)
                           .drop_duplicates(subset=["year","round"])
                           .sort_values(["year","round"]).reset_index(drop=True))
            self.races.to_csv(DATA_DIR/"races.csv", index=False)
            log.info(f"{len(new_rows)} course(s) ajoutee(s) au CSV")
            # Met a jour resultats + sprints
            for row in new_rows:
                self._update_results_for_race(row["year"], row["round"], row["raceName"], sprint=False)
                self._update_results_for_race(row["year"], row["round"], row["raceName"], sprint=True)
        return len(new_rows)

    def get_history(self):
        if not self._loaded:
            self.load_from_csv()
        df = self.races.copy()
        df["date"] = df["date"].dt.strftime("%Y-%m-%d").fillna("")
        records = []
        for row in df.to_dict("records"):
            clean = {}
            for k, v in row.items():
                if isinstance(v, float) and (v != v or v == float("inf") or v == float("-inf")):
                    clean[k] = None
                else:
                    clean[k] = v
            records.append(clean)
        return records
store = DataStore()

@app.on_event("startup")
async def startup():
    store.load_from_csv()
    asyncio.create_task(_bg_update())

async def _bg_update():
    await asyncio.sleep(5)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, store.check_and_update)


def _fmt_laptime(td):
    try:
        if td is None: return None
        s_td = str(td)
        if s_td in ("NaT","nan","None","") or s_td.startswith("NaT"): return None
        s = td.total_seconds() if hasattr(td,"total_seconds") else float(s_td.split(":")[-1])+int(s_td.split(":")[-2])*60
        if s <= 0 or s != s: return None   # s != s catches NaN
        return f"{int(s//60)}:{s%60:06.3f}"
    except: return None

@lru_cache(maxsize=64)
def _get_session(year, circuit, session_type="R"):
    s = fastf1.get_session(year, circuit, session_type)
    s.load(laps=True, telemetry=True, weather=False, messages=False)
    return s

# Palette de couleurs par écurie (fallback si FastF1 plotting indisponible)
TEAM_COLORS = {
    # Écuries actuelles
    "red bull":         "#3671C6",
    "ferrari":          "#E8002D",
    "mercedes":         "#27F4D2",
    "mclaren":          "#FF8000",
    "aston martin":     "#229971",
    "alpine":           "#FF87BC",
    "williams":         "#64C4FF",
    "rb":               "#6692FF",
    "kick sauber":      "#52E252",
    "haas":             "#B6BABD",
    # Écuries récentes
    "alfa romeo":       "#C92D4B",
    "alphatauri":       "#5E8FAA",
    "racing point":     "#F596C8",
    "renault":          "#FFF500",
    "toro rosso":       "#469BFF",
    "force india":      "#FF80C7",
    "lotus":            "#FFB800",
    "manor":            "#FF0000",
    "marussia":         "#FF0000",
    "hrt":              "#FFFFFF",
    "virgin":           "#CC0000",
    "caterham":         "#00A550",
    # Écuries historiques
    "bmw sauber":       "#6699CC",
    "sauber":           "#9B0000",
    "toyota":           "#CC0000",
    "honda":            "#FFFFFF",
    "super aguri":      "#CC0000",
    "spyker":           "#FF6600",
    "midland":          "#FF6600",
    "minardi":          "#000000",
    "jaguar":           "#00572D",
    "bar":              "#FFFFFF",
    "jordan":           "#FFD700",
    "arrows":           "#FF8000",
    "prost":            "#0033CC",
    "benetton":         "#00CC00",
    "tyrrell":          "#0033FF",
    "stewart":          "#FFFFFF",
    "lola":             "#FF0000",
    "ligier":           "#0000FF",
    "footwork":         "#FF8000",
    "brabham":          "#006400",
    "march":            "#FF6600",
    "leyton house":     "#006400",
    "osella":           "#FF0000",
    "dallara":          "#0000FF",
    "fondmetal":        "#FF8000",
    "coloni":           "#FF0000",
    "life":             "#FF0000",
    "eurobrun":         "#FF8000",
    "ags":              "#FF0000",
    "zakspeed":         "#FF0000",
    "lancia":           "#FF0000",
    "bugatti":          "#0000FF",
    "matra":            "#0000FF",
    "cooper":           "#006400",
    "brm":              "#006400",
    "lotus f1":         "#FFB800",
    "brawn":            "#80FF00",
    "team lotus":       "#FFB800",
    "vanwall":          "#006400",
}

def _driver_abbr(driver_ref: str, driver_name: str = "") -> str:
    """
    Retourne l abbreviation officielle F1 (HAM, VER, LEC…)
    depuis drivers_codes.csv, ou fallback sur le nom de famille.
    """
    # 1. Code officiel Ergast
    code = store.driver_codes.get(driver_ref, "")
    if code and len(code) == 3:
        return code.upper()
    # 2. Fallback : 3 premieres lettres du nom de famille
    if driver_name and " " in driver_name:
        last = driver_name.strip().split()[-1]
        if len(last) >= 3:
            return last[:3].upper()
    if driver_ref and "_" in driver_ref:
        last = driver_ref.strip().split("_")[-1]
        if len(last) >= 3:
            return last[:3].upper()
    return str(driver_ref)[:3].upper()


def _get_race_results_csv(year: int, race_name: str, sprint: bool = False) -> list:
    """
    Retourne les résultats depuis le CSV local.
    Renvoie [] si la course n'est pas dans le CSV (→ fallback FastF1).
    """
    df = store.sprint_results if sprint else store.results
    if df.empty:
        return []

    race = df[(df["year"] == year) & (df["raceName"] == race_name)]
    if race.empty:
        # Essai avec correspondance partielle sur le nom
        race = df[(df["year"] == year) & (df["raceName"].str.contains(race_name, case=False, na=False))]
    if race.empty:
        return []

    rows = []
    for _, r in race.sort_values("positionOrder").iterrows():
        rows.append({
            "position":     int(r["positionOrder"]) if pd.notna(r["positionOrder"]) else None,
            "abbreviation": _driver_abbr(str(r.get("driverRef","")), str(r.get("driverName",""))),
            "fullName":     r.get("driverName", ""),
            "team":         r.get("teamName", ""),
            "grid":         int(r["grid"]) if pd.notna(r.get("grid")) else None,
            "status":       r.get("status", ""),
            "points":       float(r["points"]) if pd.notna(r.get("points")) else 0,
            "fastestLap":   None if pd.isna(r.get("fastestLapTime","") or "") or r.get("fastestLapTime","") == "" else r.get("fastestLapTime"),
            "color":        _team_color(r.get("teamName", "")),
            "fromCSV":      True,
        })
    # Sanitize NaN values before returning
    clean_rows = []
    for row in rows:
        clean = {k: (None if isinstance(v, float) and v != v else v)
                 for k, v in row.items()}
        clean_rows.append(clean)
    return clean_rows


def _team_color(team_name: str) -> str:
    """Retourne la couleur hex d une écurie depuis son nom (partiel ou complet)."""
    if not team_name:
        return "#888888"
    t = str(team_name).lower()
    # Table de correspondance par mot-clé — ordre du plus spécifique au plus général
    # Ordre important : du plus spécifique au plus général
    KEYWORDS = [
        # 2026 / noms complets Jolpica
        ("red bull racing",         "#3671C6"),
        ("scuderia ferrari",        "#E8002D"),
        ("mercedes-amg",            "#27F4D2"),
        ("mclaren formula 1",       "#FF8000"),
        ("aston martin aramco",     "#229971"),
        ("bwt alpine",              "#FF87BC"),
        ("williams racing",         "#64C4FF"),
        ("visa cash app rb",        "#6692FF"),
        ("racing bulls",            "#6692FF"),
        ("kick sauber",             "#52E252"),
        ("haas f1 team",            "#B6BABD"),
        # Mots-clés courts (fallback)
        ("red bull",                "#3671C6"),
        ("ferrari",                 "#E8002D"),
        ("mercedes",                "#27F4D2"),
        ("mclaren",                 "#FF8000"),
        ("aston martin",            "#229971"),
        ("alpine",                  "#FF87BC"),
        ("williams",                "#64C4FF"),
        ("alphatauri",              "#5E8FAA"),
        ("toro rosso",              "#469BFF"),
        ("sauber",                  "#52E252"),
        ("haas",                    "#B6BABD"),
        ("alfa romeo",              "#C92D4B"),
        ("racing point",            "#F596C8"),
        ("force india",             "#FF80C7"),
        ("renault",                 "#FFF500"),
        ("lotus",                   "#FFB800"),
        ("manor",                   "#FF0000"),
        ("marussia",                "#FF0000"),
        ("caterham",                "#00A550"),
        ("toyota",                  "#CC0000"),
        ("bmw",                     "#6699CC"),
        ("jordan",                  "#FFD700"),
        ("jaguar",                  "#00572D"),
        ("brawn",                   "#80FF00"),
        ("bar",                     "#FFFFFF"),
    ]
    for keyword, color in KEYWORDS:
        if keyword in t:
            return color
    # Log pour debug si aucune couleur trouvée
    log.debug(f"Team color not found for: {team_name!r}")
    return "#888888"


def _get_driver_color(abbr: str, sess) -> str:
    """Robuste à toutes les versions de FastF1."""
    # Essai 1 : FastF1 >= 3.3 avec session
    try:
        return fastf1.plotting.get_driver_color(abbr, sess)
    except Exception:
        pass
    # Essai 2 : FastF1 < 3.3 sans session
    try:
        return fastf1.plotting.driver_color(abbr)
    except Exception:
        pass
    # Essai 3 : couleur d'écurie
    try:
        row = sess.results[sess.results["Abbreviation"] == abbr]
        if not row.empty:
            team = row.iloc[0]["TeamName"].lower()
            for key, color in TEAM_COLORS.items():
                if key in team:
                    return color
    except Exception:
        pass
    return "#888888"


def _load_model(with_grid):
    p = MODELS_DIR/("f1_model_with_grid.joblib" if with_grid else "f1_model_no_grid.joblib")
    return joblib.load(p) if p.exists() else None


@app.get("/api/circuits")
def get_circuits(): return {"circuits": CIRCUITS}

@app.get("/api/health")
def health():
    yr,rnd = store.latest_year_round()
    return {"status":"ok","total_races":len(store.races),"last_race":{"year":yr,"round":rnd},
            "cache_dir":_CACHE_DIR,"models":{"with_grid":(MODELS_DIR/"f1_model_with_grid.joblib").exists(),
            "without_grid":(MODELS_DIR/"f1_model_no_grid.joblib").exists()}}

@app.get("/api/gp-history")
def get_gp_history(background_tasks: BackgroundTasks):
    if not store._loaded: store.load_from_csv()
    background_tasks.add_task(lambda: store.check_and_update(force=False))
    return {"races": store.get_history(), "total": len(store.races)}

@app.post("/api/admin/update")
def force_update():
    added = store.check_and_update(force=True)
    yr,rnd = store.latest_year_round()
    return {"added":added,"last_year":yr,"last_round":rnd,"total":len(store.races)}

@app.get("/api/sessions/{year}/{circuit}")
def get_session_results(year: int, circuit: str, sprint: bool = False):
    """Résultats depuis CSV local (instantané) ou FastF1 en fallback."""
    # CSV first
    csv_rows = _get_race_results_csv(year, circuit, sprint=sprint)
    # Check if sprint exists for this race
    has_sprint = not store.sprint_results.empty and len(
        store.sprint_results[
            (store.sprint_results["year"] == year) &
            (store.sprint_results["raceName"] == circuit)
        ]
    ) > 0
    if csv_rows:
        return {"results": csv_rows,
                "drivers": [r["abbreviation"] for r in csv_rows if r["abbreviation"]],
                "year": year, "circuit": circuit, "source": "csv",
                "hasSprint": has_sprint}
    # FastF1 fallback
    try:
        sess = _get_session(year, circuit, "S" if sprint else "R")
        fastest = {}
        for drv in sess.results["Abbreviation"].dropna().unique():
            try:
                lap = sess.laps.pick_driver(drv).pick_fastest()
                if lap is not None: fastest[drv] = _fmt_laptime(lap["LapTime"])
            except: pass
        rows = []
        for _, r in sess.results.sort_values("Position").iterrows():
            abbr = r.get("Abbreviation", "")
            rows.append({
                "position":     int(r["Position"]) if pd.notna(r.get("Position")) else None,
                "abbreviation": abbr,
                "fullName":     r.get("FullName", ""),
                "team":         r.get("TeamName", ""),
                "grid":         int(r["GridPosition"]) if pd.notna(r.get("GridPosition")) else None,
                "status":       r.get("Status", ""),
                "points":       float(r["Points"]) if pd.notna(r.get("Points")) else 0,
                "fastestLap":   fastest.get(abbr) or None,
                "color":        _get_driver_color(abbr, sess),
            })
        return {"results": rows,
                "drivers": [r["abbreviation"] for r in rows if r["abbreviation"]],
                "year": year, "circuit": circuit, "source": "fastf1",
                "hasSprint": has_sprint}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/positions/{year}/{circuit}")
def get_race_positions(year: int, circuit: str, sprint: bool = False):
    """Positions tour par tour pour tous les pilotes + SC/VSC."""
    try:
        sess = _get_session(year, circuit, "S" if sprint else "R")
        laps = sess.laps[["DriverNumber","LapNumber","Position","TrackStatus"]].copy()
        laps = laps.dropna(subset=["Position","LapNumber"])
        laps["Position"]  = laps["Position"].astype(int)
        laps["LapNumber"] = laps["LapNumber"].astype(int)

        # Repere les coequipiers (meme ecurie) pour alterner plein/pointille
        team_seen = {}  # team -> bool (premier pilote = plein, second = pointille)
        drivers_data = []
        for abbr in sess.results["Abbreviation"].dropna().unique():
            try:
                row = sess.results[sess.results["Abbreviation"]==abbr].iloc[0]
                drv_num = row["DriverNumber"]
                team    = row.get("TeamName", "")
                drv_laps = laps[laps["DriverNumber"]==drv_num].sort_values("LapNumber")
                if drv_laps.empty:
                    continue
                color = _get_driver_color(abbr, sess)
                # Premier pilote de l ecurie = trait plein, second = pointille
                dash = "solid"
                if team in team_seen:
                    dash = "dot"
                else:
                    team_seen[team] = True
                drivers_data.append({
                    "driver":    abbr,
                    "color":     color,
                    "dash":      dash,
                    "laps":      drv_laps["LapNumber"].tolist(),
                    "positions": drv_laps["Position"].tolist(),
                })
            except Exception:
                continue

        # SC / VSC
        sc_laps, vsc_laps = [], []
        try:
            ts = laps[["LapNumber","TrackStatus"]].drop_duplicates()
            sc_laps  = ts[ts["TrackStatus"].astype(str).str.contains("4")]["LapNumber"].astype(int).unique().tolist()
            vsc_laps = ts[ts["TrackStatus"].astype(str).str.contains("6")]["LapNumber"].astype(int).unique().tolist()
        except Exception:
            pass

        return {"drivers": drivers_data, "sc_laps": sc_laps, "vsc_laps": vsc_laps,
                "year": year, "circuit": circuit}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/telemetry/{year}/{circuit}/{driver}")
def get_telemetry(year:int, circuit:str, driver:str, sprint:bool=False):
    try:
        sess = _get_session(year,circuit)
        lap = sess.laps.pick_driver(driver).pick_fastest()
        if lap is None: raise HTTPException(404,f"Pas de tour pour {driver}")
        tel = lap.get_telemetry().add_distance()
        color = _get_driver_color(driver, sess)
        # Coequipier dash
        try:
            team = sess.results[sess.results["Abbreviation"]==driver]["TeamName"].iloc[0]
            teammates = sess.results[sess.results["TeamName"]==team]["Abbreviation"].tolist()
            dash = "dot" if teammates.index(driver) > 0 else "solid"
        except Exception:
            dash = "solid"
        return {"driver":driver,"lapTime":_fmt_laptime(lap["LapTime"]),"color":color,"dash":dash,
                "distance":tel["Distance"].tolist(),"speed":tel["Speed"].tolist(),
                "brake":(tel["Brake"].astype(float)*100).tolist(),
                "gear":tel["nGear"].tolist() if "nGear" in tel.columns else [],
                "x":tel["X"].tolist() if "X" in tel.columns else [],
                "y":tel["Y"].tolist() if "Y" in tel.columns else []}
    except HTTPException: raise
    except Exception as e: raise HTTPException(500,str(e))

@app.get("/api/laps/{year}/{circuit}/{driver1}/{driver2}")
def get_lap_times(year:int, circuit:str, driver1:str, driver2:str, sprint:bool=False):
    try:
        sess = _get_session(year, circuit, "S" if sprint else "R")
        def _dl(drv):
            laps = sess.laps.pick_driver(drv)[["LapNumber","LapTime","PitOutTime"]].copy()
            laps["s"] = laps["LapTime"].dt.total_seconds()
            laps = laps.dropna(subset=["s"])
            color = _get_driver_color(drv, sess)
            return {"driver":drv,"color":color,"laps":laps["LapNumber"].astype(int).tolist(),
                    "times":laps["s"].round(3).tolist(),
                    "pits":laps[laps["PitOutTime"].notna()]["LapNumber"].astype(int).tolist()}

        # Safety Car et Virtual Safety Car (statut global de la piste)
        sc_laps, vsc_laps = [], []
        try:
            ts = sess.laps[["LapNumber","TrackStatus"]].dropna()
            sc_laps  = ts[ts["TrackStatus"].astype(str).str.contains("4")]["LapNumber"].astype(int).unique().tolist()
            vsc_laps = ts[ts["TrackStatus"].astype(str).str.contains("6")]["LapNumber"].astype(int).unique().tolist()
        except Exception:
            pass
        return {"driver1":_dl(driver1),"driver2":_dl(driver2),"sc_laps":sc_laps,"vsc_laps":vsc_laps}
    except Exception as e: raise HTTPException(500,str(e))

@app.get("/api/sprint/{year}/{circuit}")
def get_sprint_results(year: int, circuit: str):
    """Résultats de la course sprint (si disponible). Fallback Jolpica pour années récentes."""
    # CSV first
    rows = _get_race_results_csv(year, circuit, sprint=True)
    if rows:
        return {"results": rows, "drivers": [r["abbreviation"] for r in rows],
                "year": year, "circuit": circuit, "available": True}
    # Jolpica fallback pour 2025+
    try:
        race_info = store.races[store.races["raceName"] == circuit]
        if race_info.empty:
            return {"results": [], "available": False}
        round_num = int(race_info.iloc[0]["round"])
        r = requests.get(f"{JOLPICA}/{year}/{round_num}/sprint.json?limit=30", timeout=8)
        races_raw = r.json()["MRData"]["RaceTable"]["Races"]
        if not races_raw or not races_raw[0].get("SprintResults"):
            return {"results": [], "available": False}
        rows = []
        for res in races_raw[0]["SprintResults"]:
            rows.append({
                "position":     int(res.get("position", 0)),
                "abbreviation": res["Driver"]["driverId"][:3].upper(),
                "fullName":     f"{res['Driver']['givenName']} {res['Driver']['familyName']}",
                "team":         res["Constructor"]["name"],
                "grid":         int(res.get("grid", 0)),
                "status":       res.get("status", ""),
                "points":       float(res.get("points", 0)),
                "fastestLap":   None,
                "color":        "#888888",
            })
        return {"results": rows, "drivers": [r["abbreviation"] for r in rows],
                "year": year, "circuit": circuit, "available": True}
    except Exception:
        return {"results": [], "available": False}


@app.get("/api/standings/{year}/{round_num}")
def get_standings(year:int, round_num:int):
    prev = round_num - 1
    # Pour les courses futures, prev peut dépasser le dernier round disputé
    # On utilise le dernier round connu dans le CSV comme plafond
    if prev > 0 and not store.races.empty:
        past_rounds = store.races[
            (store.races["year"] == year) &
            (store.races["round"] < round_num) &
            (store.races["date"].notna())
        ]
        # Filtre sur les courses passées (date <= aujourd'hui)
        today_str = datetime.date.today().isoformat()
        past_rounds = past_rounds[past_rounds["date"].astype(str) <= today_str]
        if not past_rounds.empty:
            prev = int(past_rounds["round"].max())
        elif prev > 0:
            prev = 0  # Aucune course passée → standings saison précédente
    if prev==0:
        # Manche 1 : standings finaux de la saison precedente (points remis a 0)
        try:
            r  = requests.get(f"{JOLPICA}/{year-1}/driverStandings.json?limit=30", timeout=10)
            r2 = requests.get(f"{JOLPICA}/{year-1}/constructorStandings.json?limit=30", timeout=10)
            dl = r.json()["MRData"]["StandingsTable"]["StandingsLists"]
            cl = r2.json()["MRData"]["StandingsTable"]["StandingsLists"]
            drivers, constructors = [], []
            for s in (dl[0]["DriverStandings"] if dl else []):
                try:
                    drivers.append({
                        "driverId":      s["Driver"]["driverId"],
                        "name":          f"{s['Driver']['givenName']} {s['Driver']['familyName']}",
                        "constructor":   s["Constructors"][0]["name"] if s.get("Constructors") else "",
                        "constructorId": s["Constructors"][0]["constructorId"] if s.get("Constructors") else "",
                        "points":        0.0,
                        "position":      int(s.get("position", 99)),
                        "wins":          0,
                        "color":         _team_color(s["Constructors"][0]["name"] if s.get("Constructors") else ""),
                    })
                except Exception: continue
            for s in (cl[0]["ConstructorStandings"] if cl else []):
                try:
                    constructors.append({
                        "constructorId": s["Constructor"]["constructorId"],
                        "name":          s["Constructor"]["name"],
                        "points":        0.0,
                        "position":      int(s.get("position", 99)),
                        "wins":          0,
                        "color":         _team_color(s["Constructor"]["name"]),
                    })
                except Exception: continue
            if drivers:
                return {"drivers": drivers, "constructors": constructors}
        except Exception:
            pass
        return {"drivers": [], "constructors": []}
    try:
        r1 = requests.get(f"{JOLPICA}/{year}/{prev}/driverStandings.json",timeout=10)
        r2 = requests.get(f"{JOLPICA}/{year}/{prev}/constructorStandings.json",timeout=10)
        dl = r1.json()["MRData"]["StandingsTable"]["StandingsLists"]
        cl = r2.json()["MRData"]["StandingsTable"]["StandingsLists"]
        drivers = []
        for s in (dl[0]["DriverStandings"] if dl else []):
            try:
                drivers.append({
                    "driverId":      s["Driver"]["driverId"],
                    "name":          f"{s['Driver']['givenName']} {s['Driver']['familyName']}",
                    "constructor":   s["Constructors"][0]["name"] if s.get("Constructors") else "",
                    "constructorId": s["Constructors"][0]["constructorId"] if s.get("Constructors") else "",
                    "points":        float(s.get("points", 0)),
                    "position":      int(s.get("position", s.get("positionText", 99))),
                    "wins":          int(s.get("wins", 0)),
                    "color":         _team_color(s["Constructors"][0]["name"] if s.get("Constructors") else ""),
                })
            except Exception:
                continue
        constructors = []
        for s in (cl[0]["ConstructorStandings"] if cl else []):
            try:
                constructors.append({
                    "constructorId": s["Constructor"]["constructorId"],
                    "name":          s["Constructor"]["name"],
                    "points":        float(s.get("points", 0)),
                    "position":      int(s.get("position", s.get("positionText", 99))),
                    "wins":          int(s.get("wins", 0)),
                    "color":         _team_color(s["Constructor"]["name"]),
                })
            except Exception:
                continue
        return {"drivers":drivers,"constructors":constructors}
    except Exception as e: raise HTTPException(500,str(e))

@app.get("/api/qualifying/{year}/{round_num}")
def get_qualifying(year:int, round_num:int):
    try:
        r = requests.get(f"{JOLPICA}/{year}/{round_num}/qualifying.json",timeout=10)
        races = r.json()["MRData"]["RaceTable"]["Races"]
        if not races: return {"grid":[]}
        return {"grid":[{"position":int(res["position"]),"driverId":res["Driver"]["driverId"],
            "name":f"{res['Driver']['givenName']} {res['Driver']['familyName']}"}
            for res in races[0].get("QualifyingResults",[])]}
    except Exception as e: raise HTTPException(500,str(e))

@app.get("/api/calendar/{year}")
def get_calendar(year: int):
    """Retourne tout le calendrier d une saison (courses passées ET futures)."""
    # D abord depuis le CSV local
    if not store.races.empty:
        yr = store.races[store.races["year"] == year].sort_values("round")
        if not yr.empty:
            rows = []
            for _, r in yr.iterrows():
                d = str(r.get("date",""))[:10] if pd.notna(r.get("date")) else None
                rows.append({
                    "round":    int(r["round"]),
                    "raceName": r["raceName"],
                    "date":     d,
                    "country":  r.get("country",""),
                })
            # Si la saison est en cours, complète avec Jolpica pour les courses futures
            if year == datetime.date.today().year:
                try:
                    r2 = requests.get(f"{JOLPICA}/{year}/races.json?limit=30", timeout=8)
                    races_raw = r2.json()["MRData"]["RaceTable"]["Races"]
                    known_rounds = {row["round"] for row in rows}
                    for race in races_raw:
                        rnd = int(race["round"])
                        if rnd not in known_rounds:
                            rows.append({
                                "round":    rnd,
                                "raceName": race["raceName"],
                                "date":     race["date"],
                                "country":  race["Circuit"]["Location"]["country"],
                            })
                    rows.sort(key=lambda x: x["round"])
                except Exception:
                    pass
            return {"races": rows, "year": year}

    # Fallback Jolpica complet
    try:
        r = requests.get(f"{JOLPICA}/{year}/races.json?limit=30", timeout=10)
        races_raw = r.json()["MRData"]["RaceTable"]["Races"]
        rows = [{"round": int(race["round"]), "raceName": race["raceName"],
                 "date": race["date"], "country": race["Circuit"]["Location"]["country"]}
                for race in races_raw]
        return {"races": rows, "year": year}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/round/{year}/{circuit}")
def get_round(year: int, circuit: str):
    """Retourne le numéro de manche pour une année + nom de GP."""
    if store.races.empty:
        return {"round": None}
    match = store.races[
        (store.races["year"] == year) &
        (store.races["raceName"] == circuit)
    ]
    if match.empty:
        # Recherche partielle
        match = store.races[
            (store.races["year"] == year) &
            (store.races["raceName"].str.contains(circuit, case=False, na=False))
        ]
    if match.empty:
        return {"round": None}
    row = match.iloc[0]
    return {
        "round":    int(row["round"]),
        "raceName": row["raceName"],
        "date":     str(row["date"])[:10] if pd.notna(row["date"]) else None,
    }


@app.get("/api/weather/{circuit}")
def get_weather(circuit:str):
    coords = CIRCUIT_COORDS.get(circuit)
    if not coords: return {"rainfall":0,"probability":0}
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast",
            params={"latitude":coords[0],"longitude":coords[1],
                    "daily":"precipitation_probability_max","forecast_days":3,"timezone":"auto"},timeout=8)
        prob = r.json()["daily"]["precipitation_probability_max"][0]
        return {"rainfall":1 if prob>=50 else 0,"probability":prob}
    except: return {"rainfall":0,"probability":0}

@app.get("/api/predict")
def predict(year:int=Query(...),round_num:int=Query(...),circuit:str=Query(...),
            use_grid:bool=Query(False),rainfall:float=Query(0.0),grid_json:str=Query("{}")):
    bundle = _load_model(use_grid)
    if bundle is None: raise HTTPException(503,"Modele non disponible")
    std = get_standings(year,round_num)
    if not std["drivers"]: raise HTTPException(404,"Aucun standings")
    gmap = json.loads(grid_json) if grid_json!="{}" else {}
    cmap = {c["constructorId"]:c for c in std["constructors"]}
    fc   = FEATURE_COLS_GRID if use_grid else FEATURE_COLS_NO_GRID
    rows = []
    for d in std["drivers"]:
        cst = cmap.get(d["constructorId"],{})
        row = {"driverId":d["driverId"],"name":d["name"],"constructor":d["constructor"],
               "driverPoints":d["points"] if round_num>1 else 0.0,
               "driverStandingPosition":d["position"] if round_num>1 else 20.0,
               "driverWins":d["wins"] if round_num>1 else 0.0,
               "constructorPoints":cst.get("points",0.0) if round_num>1 else 0.0,
               "constructorStandingPosition":cst.get("position",10.0) if round_num>1 else 10.0,
               "constructorWins":cst.get("wins",0.0) if round_num>1 else 0.0}
        if use_grid: row["grid"] = gmap.get(d["driverId"],20)
        rows.append(row)
    df = pd.DataFrame(rows)
    avail = [f for f in fc if f in df.columns]
    Xsc  = bundle["scaler"].transform(df[avail].values)
    prf  = bundle["rf"].predict_proba(Xsc)[:,1]
    pdt  = bundle["dt"].predict_proba(Xsc)[:,1]
    psvc = bundle["svc"].predict_proba(Xsc)[:,1] if bundle.get("svc") else None
    pavg = (prf+pdt+(psvc if psvc is not None else prf))/(3 if psvc is not None else 2)
    df["proba_rf"]=prf; df["proba_dt"]=pdt; df["proba_avg"]=pavg
    if psvc is not None: df["proba_svc"]=psvc
    df["position"]=df["proba_avg"].rank(ascending=False,method="first").astype(int)
    df=df.sort_values("position")
    cols=["position","driverId","name","constructor","proba_rf","proba_dt","proba_avg"]
    if use_grid: cols.append("grid")
    if psvc is not None: cols.insert(-1,"proba_svc")
    return {"predictions":df[cols].to_dict("records"),
            "models":["Random Forest","Decision Tree"]+(["SVC"] if psvc is not None else []),
            "rainfall":rainfall}
