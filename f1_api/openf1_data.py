"""
openf1_data.py - Lecture de l'archive OpenF1 locale (ecrite par openf1_archive.py)
et construction des reponses au MEME format que les routes FastF1 de main.py :
  /api/positions, /api/laps, /api/telemetry

Aucun appel reseau ici : uniquement des fichiers .json.gz locaux.
"""

import datetime as dt, gzip, json, os, re
from functools import lru_cache
from pathlib import Path

import numpy as np

ARCHIVE_DIR = Path(os.getenv("F1_OPENF1_DIR", "/var/lib/f1_openf1"))


# ── Lecture ──────────────────────────────────────────────────────────────────
def _parse_date(s):
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    m = re.match(r"^(.*T\d\d:\d\d:\d\d)(\.\d+)?(.*)$", s)
    if m and m.group(2):
        s = m.group(1) + (m.group(2) + "000000")[:7] + m.group(3)
    d = dt.datetime.fromisoformat(s)
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)

def _ts(s):
    d = _parse_date(s)
    return d.timestamp() if d else None

def _rows(block):
    cols = block["cols"]
    return [dict(zip(cols, r)) for r in block["rows"]]

def load_index():
    f = ARCHIVE_DIR / "index.json"
    return json.loads(f.read_text()) if f.exists() else {"sessions": {}}

@lru_cache(maxsize=32)
def _load_file_cached(rel_path, mtime):
    with gzip.open(ARCHIVE_DIR / rel_path, "rt", encoding="utf-8") as f:
        return OpenF1Session(json.load(f))

def load_file(rel_path):
    """Lecture memorisee ; un fichier re-telecharge (mtime different) est relu."""
    return _load_file_cached(rel_path, (ARCHIVE_DIR / rel_path).stat().st_mtime)

def find_session(year, race_name, race_date=None, sprint=False):
    """Retrouve la session archivee : date de course (+/- 1 jour) puis nom du GP."""
    want = "S" if sprint else "R"
    cands = [e for e in load_index()["sessions"].values()
             if e.get("status") == "ok" and e.get("year") == year and e.get("type") == want]
    if race_date:
        try:
            d0 = dt.date.fromisoformat(str(race_date)[:10])
            for e in cands:
                # la date de la course sert aussi pour le sprint du meme week-end
                d = dt.date.fromisoformat(e["date_start"][:10])
                if abs((d - d0).days) <= (1 if want == "R" else 2):
                    return load_file(e["file"])
        except ValueError:
            pass
    norm = lambda s: re.sub(r"[^a-z]", "", (s or "").lower())
    for e in cands:
        if norm(e.get("meeting_name")) == norm(race_name):
            return load_file(e["file"])
    return None


MIN_COMPLETENESS = 0.95   # en dessous, la session n'est pas servie (timing_incomplete)

def completeness_from_rows(laps, results):
    """(tours archives, tours attendus) : tours horodates par pilote, plafonnes au
    nombre de tours du classement (session_result.number_of_laps)."""
    expected = {r["driver_number"]: r.get("number_of_laps") or 0 for r in results}
    seen = set()
    for l in laps:
        n, k = l.get("driver_number"), l.get("lap_number")
        if n in expected and k and k <= expected[n] and (l.get("date_start") or l.get("lap_duration")):
            seen.add((n, k))
    return len(seen), sum(expected.values())


def _fmt_laptime(s):
    if s is None or s != s or s <= 0:
        return None
    return f"{int(s // 60)}:{s % 60:06.3f}"


# ── Session ──────────────────────────────────────────────────────────────────
class OpenF1Session:
    def __init__(self, doc):
        self.doc = doc
        self.drivers = {d["driver_number"]: d for d in _rows(doc["drivers"])}
        self.abbr_to_num = {d["name_acronym"]: n for n, d in self.drivers.items()}
        self.results = sorted(_rows(doc["session_result"]),
                              key=lambda r: (r.get("position") is None, r.get("position") or 99))
        self.laps = _rows(doc["laps"])
        got, exp = completeness_from_rows(self.laps, _rows(doc["session_result"]))
        self.laps_archived, self.laps_expected = got, exp
        self.completeness = got / exp if exp else 0.0

    # -- pilotes
    def order(self):
        """Ordre du classement (comme sess.results), puis pilotes absents du classement."""
        nums = [r["driver_number"] for r in self.results if r["driver_number"] in self.drivers]
        return nums + [n for n in self.drivers if n not in nums]

    def color(self, num):
        c = (self.drivers.get(num) or {}).get("team_colour")
        return f"#{c}" if c else "#888888"

    def dash(self, num):
        team = (self.drivers.get(num) or {}).get("team_name")
        mates = [n for n in self.order() if (self.drivers.get(n) or {}).get("team_name") == team]
        return "dot" if mates and mates.index(num) > 0 else "solid"

    def abbr(self, num):
        return (self.drivers.get(num) or {}).get("name_acronym", str(num))

    # -- SC / VSC depuis race_control, convention FastF1 :
    #    periodes horodatees, puis un tour est marque s'il CHEVAUCHE une periode,
    #    union sur tous les pilotes (comme sess.laps.TrackStatus contient "4"/"6").
    def _lap_intervals(self):
        """[(lap_number, t_debut, t_fin)] pour chaque tour de chaque pilote."""
        if hasattr(self, "_intervals"):
            return self._intervals
        by = {}
        for l in self.laps:
            if l.get("date_start") and l.get("lap_number"):
                by.setdefault(l["driver_number"], {})[l["lap_number"]] = l
        out = []
        for laps in by.values():
            for n, l in laps.items():
                t0 = _ts(l["date_start"])
                nxt = laps.get(n + 1)
                if nxt:
                    t1 = _ts(nxt["date_start"])
                elif l.get("lap_duration"):
                    t1 = t0 + l["lap_duration"]
                else:
                    continue
                out.append((n, t0, t1))
        self._intervals = out
        return out

    def _leader_lap_end(self, lap_number):
        ends = [t1 for n, _, t1 in self._lap_intervals() if n == lap_number]
        return min(ends) if ends else None

    def sc_vsc_periods(self):
        """[(kind 'SC'|'VSC', t_debut, t_fin)] depuis race_control."""
        msgs = sorted(_rows(self.doc["race_control"]), key=lambda m: m.get("date") or "")
        intervals = self._lap_intervals()
        t_last = max((t1 for _, _, t1 in intervals), default=None)
        periods, open_ = [], {}
        cur_lap = 1

        def close(kind, t_end):
            if kind in open_ and t_end is not None:
                periods.append((kind, open_.pop(kind), t_end))

        for m in msgs:
            if m.get("lap_number"):
                cur_lap = m["lap_number"]
            t = (m.get("message") or "").upper()
            tm = _ts(m.get("date"))
            # Drapeau rouge / suspension : clot SC et VSC ("\b" : CHEQUERED FLAG contient RED FLAG)
            if (re.search(r"\bRED FLAG", t) or m.get("flag") == "RED"
                    or (m.get("category") == "SessionStatus" and ("ABORTED" in t or "SUSPENDED" in t))):
                close("SC", tm); close("VSC", tm)
                continue
            if m.get("category") != "SafetyCar" or tm is None:
                continue
            kind = "VSC" if ("VIRTUAL" in t or "VSC" in t) else "SC"
            if "DEPLOYED" in t:
                open_.setdefault(kind, tm)
            elif kind == "VSC" and "ENDING" in t:
                close("VSC", tm)
            elif kind == "SC" and "IN THIS LAP" in t:
                # la SC rentre a la fin du tour en cours du leader
                close("SC", self._leader_lap_end(cur_lap) or tm)
        for kind in list(open_):
            close(kind, t_last)
        return periods

    def sc_vsc_laps(self):
        sc, vsc = set(), set()
        intervals = self._lap_intervals()
        for kind, a, b in self.sc_vsc_periods():
            target = sc if kind == "SC" else vsc
            for n, t0, t1 in intervals:
                if t0 < b and t1 > a:
                    target.add(n)
        return sorted(sc), sorted(vsc)

    # -- /api/laps
    def driver_laps(self, abbr):
        num = self.abbr_to_num.get(abbr)
        laps = sorted((l for l in self.laps if l["driver_number"] == num and l.get("lap_duration")),
                      key=lambda l: l["lap_number"])
        return {"driver": abbr, "color": self.color(num),
                "laps":  [l["lap_number"] for l in laps],
                "times": [round(l["lap_duration"], 3) for l in laps],
                "pits":  [l["lap_number"] for l in laps if l.get("is_pit_out_lap")]}

    def laps_payload(self, d1, d2):
        sc, vsc = self.sc_vsc_laps()
        return {"driver1": self.driver_laps(d1), "driver2": self.driver_laps(d2),
                "sc_laps": sc, "vsc_laps": vsc, "source": "openf1"}

    # -- /api/positions : position a la fin de chaque tour
    def positions_payload(self, year, circuit):
        pos_by_drv = {}
        for p in _rows(self.doc["position"]):
            pos_by_drv.setdefault(p["driver_number"], []).append((_ts(p["date"]), p["position"]))
        drivers_data = []
        for num in self.order():
            laps = sorted((l for l in self.laps if l["driver_number"] == num and l.get("date_start")),
                          key=lambda l: l["lap_number"])
            changes = sorted(pos_by_drv.get(num, []))
            if not laps or not changes:
                continue
            times = [c[0] for c in changes]
            out_laps, out_pos = [], []
            for i, l in enumerate(laps):
                if i + 1 < len(laps) and laps[i + 1]["lap_number"] == l["lap_number"] + 1:
                    end = _ts(laps[i + 1]["date_start"])
                elif l.get("lap_duration"):
                    end = _ts(l["date_start"]) + l["lap_duration"]
                else:
                    continue
                k = np.searchsorted(times, end, side="right") - 1
                if k >= 0:
                    out_laps.append(l["lap_number"]); out_pos.append(changes[k][1])
            if out_laps:
                drivers_data.append({"driver": self.abbr(num), "color": self.color(num),
                                     "dash": self.dash(num), "laps": out_laps, "positions": out_pos})
        sc, vsc = self.sc_vsc_laps()
        return {"drivers": drivers_data, "sc_laps": sc, "vsc_laps": vsc,
                "year": year, "circuit": circuit, "source": "openf1"}

    # -- /api/telemetry : meilleur tour
    def lap_length(self):
        """Longueur de reference du tour : mediane des distances brutes de tous les pilotes."""
        if not hasattr(self, "_lap_length"):
            totals = []
            for num in self.drivers:
                raw = self._raw_telemetry(num)
                if raw is not None:
                    totals.append(raw["dist"][-1])
            self._lap_length = float(np.median(totals)) if totals else None
        return self._lap_length

    def telemetry_payload(self, abbr):
        num = self.abbr_to_num.get(abbr)
        raw = self._raw_telemetry(num)
        if raw is None:
            return None
        # Distance ramenee a la mediane de la session (meme circuit pour tous) :
        # corrige la sous-estimation de l'integration a ~3,7 Hz
        dist = raw["dist"]
        ref = self.lap_length()
        if ref and dist[-1] > 0:
            dist = dist * (ref / dist[-1])
        car = raw["car"]
        return {"driver": abbr, "lapTime": _fmt_laptime(raw["lap_duration"]),
                "color": self.color(num), "dash": self.dash(num),
                "distance": dist.round(2).tolist(), "speed": raw["speed"].tolist(),
                "brake": [100.0 if (c.get("brake") or 0) > 0 else 0.0 for _, c in car],
                "gear": [c.get("n_gear") for _, c in car],
                "x": raw["x"], "y": raw["y"], "source": "openf1"}

    def _raw_telemetry(self, num):
        cache = self.__dict__.setdefault("_raw_cache", {})
        if num in cache:
            return cache[num]
        cache[num] = None
        tel = self.doc["fastest_lap_telemetry"].get(str(num))
        if not tel:
            return None
        t0 = _ts(tel["lap_start"]); t1 = t0 + tel["lap_duration"]
        car = [c for c in _rows(tel["car_data"]) if c.get("speed") is not None]
        car = [(_ts(c["date"]), c) for c in car]
        car = [(t, c) for t, c in car if t0 <= t <= t1]
        if len(car) < 2:
            return None
        t = np.array([x[0] for x in car]) - t0
        speed = np.array([float(x[1]["speed"]) for x in car])
        # distance : integration trapeze de la vitesse (km/h -> m/s)
        dist = np.concatenate([[0.0], np.cumsum((speed[1:] + speed[:-1]) / 2 / 3.6 * np.diff(t))])
        loc = sorted((_ts(p["date"]) - t0, p["x"], p["y"]) for p in _rows(tel["location"])
                     if p.get("x") is not None)
        if len(loc) >= 2:
            lt = np.array([p[0] for p in loc])
            x = np.interp(t, lt, [p[1] for p in loc]).round(1).tolist()
            y = np.interp(t, lt, [p[2] for p in loc]).round(1).tolist()
        else:
            x, y = [], []
        cache[num] = {"car": car, "speed": speed, "dist": dist, "x": x, "y": y,
                      "lap_duration": tel["lap_duration"]}
        return cache[num]
