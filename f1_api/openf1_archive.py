#!/usr/bin/env python3
"""
openf1_archive.py - Archive locale des donnees OpenF1 (courses et sprints).

Ecrit un fichier JSON compresse par session dans F1_OPENF1_DIR
(defaut /var/lib/f1_openf1) ; l'API (main.py) ne fait que lire ces fichiers.

Contenu par session :
  - flux complets (legers) : drivers, laps (champs utiles), position,
    race_control, stints, pit, weather, session_result
  - telemetrie : car_data + location limites au MEILLEUR TOUR de chaque pilote

Limites OpenF1 respectees : 3 req/s et 25 req/min (limite officielle 30/min),
attente progressive apres 429/5xx. Reprenable : une session terminee est
ecrite atomiquement et notee dans index.json ; elle est sautee ensuite.

Usage :
  python openf1_archive.py                       # saison en cours + precedente
  python openf1_archive.py --years 2023 2024 2025 2026
  python openf1_archive.py --session-keys 11404 9979 --force
  python openf1_archive.py --years 2026 --dry-run
"""

import argparse, collections, datetime as dt, fcntl, gzip, json, logging, os, re
import sys, time, unicodedata
from pathlib import Path

import requests

from openf1_data import MIN_COMPLETENESS, completeness_from_rows

BASE        = "https://api.openf1.org/v1"
ARCHIVE_DIR = Path(os.getenv("F1_OPENF1_DIR", "/var/lib/f1_openf1"))
INDEX_FILE  = ARCHIVE_DIR / "index.json"
FORMAT_VERSION = 1

SESSION_NAMES   = {"Race": "R", "Sprint": "S"}
READY_DELAY     = dt.timedelta(hours=2)   # attendre 2 h apres la fin de session
MAX_EMPTY_TRIES = 3                       # session vide : on abandonne apres 3 essais
TEL_PAD_S       = 1.0                     # marge autour du meilleur tour (s)

# Champs conserves pour les flux volumineux (le reste est inutilise par le site)
KEEP_FIELDS = {
    "laps":     ["driver_number", "lap_number", "lap_duration", "date_start", "is_pit_out_lap"],
    "position": ["date", "driver_number", "position"],
    "car_data": ["date", "speed", "brake", "n_gear"],
    "location": ["date", "x", "y"],
}
DROP_FIELDS = {"session_key", "meeting_key"}   # redondants dans le fichier
LIGHT_ENDPOINTS = ["drivers", "laps", "position", "race_control",
                   "stints", "pit", "weather", "session_result"]

log = logging.getLogger("openf1_archive")

# Code de sortie dedie : OpenF1 refuse l'acces pendant une seance F1 en direct
# (75 = EX_TEMPFAIL : erreur temporaire, relancer plus tard)
EXIT_LIVE_SESSION = 75
LIVE_MARKER = "live f1 session in progress"


class LiveSessionBlocked(Exception):
    """OpenF1 : 401 'Live F1 session in progress' (acces reserve aux abonnes pendant le direct)."""


# ── Client HTTP limite ────────────────────────────────────────────────────────
class RateLimitedClient:
    def __init__(self, per_second=3, per_minute=25, max_tries=6):
        # Espacement regulier (pas de rafale) : max(1/3 s, 60/25 s) = 2,4 s
        self.min_interval = max(1.0 / per_second, 60.0 / per_minute) + 0.01
        self.per_minute   = per_minute
        self.max_tries    = max_tries
        self.calls        = collections.deque()   # horodatages des 60 dernieres s
        self.last         = 0.0
        self.count        = 0
        self.http         = requests.Session()
        self.http.headers["User-Agent"] = "f1-archive/1.0 (archive personnelle)"

    def _wait_slot(self):
        while True:
            now = time.monotonic()
            while self.calls and now - self.calls[0] >= 60:
                self.calls.popleft()
            wait = 0.0
            if len(self.calls) >= self.per_minute:
                wait = 60 - (now - self.calls[0]) + 0.05
            wait = max(wait, self.min_interval - (now - self.last))
            if wait <= 0:
                break
            time.sleep(wait)
        now = time.monotonic()
        self.calls.append(now)
        self.last = now

    def get(self, endpoint, query):
        """query : chaine deja formee (permet date>=...). Renvoie une liste."""
        url = f"{BASE}/{endpoint}?{query}"
        delay = 10
        for attempt in range(1, self.max_tries + 1):
            self._wait_slot()
            self.count += 1
            try:
                r = self.http.get(url, timeout=60)
            except requests.RequestException as e:
                status, retry_after, err = None, None, repr(e)
            else:
                if r.status_code == 200:
                    data = r.json()
                    return data if isinstance(data, list) else []
                if r.status_code == 404:          # OpenF1 : "No results found"
                    return []
                status, retry_after, err = r.status_code, r.headers.get("Retry-After"), r.text[:200]
                if status == 401 and LIVE_MARKER in r.text.lower():
                    raise LiveSessionBlocked(err)
                if status not in (429,) and status < 500:
                    raise RuntimeError(f"{endpoint}: HTTP {status} {err}")
            pause = delay
            if retry_after and str(retry_after).isdigit():
                pause = max(pause, int(retry_after))
            pause = min(pause, 300)
            log.warning(f"{endpoint}: {status or 'erreur reseau'} (essai {attempt}/{self.max_tries}), "
                        f"attente {pause}s - {err}")
            time.sleep(pause)
            delay = min(delay * 2, 300)
        raise RuntimeError(f"{endpoint}: abandon apres {self.max_tries} essais")


# ── Utilitaires ───────────────────────────────────────────────────────────────
def parse_date(s):
    """ISO 8601 OpenF1 -> datetime UTC (tolere 0 a 6 decimales et 'Z')."""
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    m = re.match(r"^(.*T\d\d:\d\d:\d\d)(\.\d+)?(.*)$", s)
    if m and m.group(2):
        s = m.group(1) + (m.group(2) + "000000")[:7] + m.group(3)
    d = dt.datetime.fromisoformat(s)
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)

def iso(d):
    return d.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")

def slug(text):
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", t).strip("_")

def columnar(rows, endpoint):
    """Liste de dicts -> {"cols": [...], "rows": [[...]]} (compact)."""
    if endpoint in KEEP_FIELDS:
        cols = KEEP_FIELDS[endpoint]
    else:
        cols = []
        for r in rows:
            for k in r:
                if k not in DROP_FIELDS and k not in cols:
                    cols.append(k)
    return {"cols": cols, "rows": [[r.get(c) for c in cols] for r in rows]}

def write_atomic(path, payload: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

def load_index():
    if INDEX_FILE.exists():
        return json.loads(INDEX_FILE.read_text())
    return {"format": FORMAT_VERSION, "sessions": {}}

def save_index(index):
    write_atomic(INDEX_FILE, json.dumps(index, ensure_ascii=False, indent=1, sort_keys=True).encode())


# ── Selection des sessions ────────────────────────────────────────────────────
def list_sessions(client, years):
    out = []
    for year in years:
        meetings = {m["meeting_key"]: m for m in client.get("meetings", f"year={year}")}
        for s in client.get("sessions", f"year={year}"):
            if s.get("session_name") not in SESSION_NAMES or s.get("session_type") != "Race":
                continue
            m = meetings.get(s["meeting_key"], {})
            out.append({
                "session_key":  s["session_key"],
                "meeting_key":  s["meeting_key"],
                "year":         s["year"],
                "type":         SESSION_NAMES[s["session_name"]],
                "meeting_name": m.get("meeting_name") or f"{s.get('country_name')} Grand Prix",
                "country_name": s.get("country_name"),
                "location":     s.get("location"),
                "date_start":   s["date_start"],
                "date_end":     s["date_end"],
                "gmt_offset":   s.get("gmt_offset"),
                "cancelled":    bool(s.get("is_cancelled")) or bool(m.get("is_cancelled")),
            })
    return sorted(out, key=lambda x: x["date_start"])

def needs_fetch(sess, index, now, force):
    if sess["cancelled"]:
        return False, "annulee"
    if parse_date(sess["date_end"]) + READY_DELAY > now:
        return False, "pas encore disputee"
    entry = index["sessions"].get(str(sess["session_key"]))
    if force or entry is None:
        return True, "nouvelle" if entry is None else "forcee"
    if entry["status"] == "ok":
        return False, "deja archivee"
    if entry["status"] == "empty" and entry.get("tries", 0) >= MAX_EMPTY_TRIES:
        return False, "vide (abandon)"
    return True, f"reprise ({entry['status']})"


# ── Recuperation d'une session ───────────────────────────────────────────────
def fastest_laps(laps):
    """Meilleur tour par pilote : plus petit lap_duration hors tour 1 et sorties de stand."""
    best = {}
    for l in laps:
        if not l.get("lap_duration") or not l.get("date_start"):
            continue
        if l.get("is_pit_out_lap") or l.get("lap_number") == 1:
            continue
        d = l["driver_number"]
        if d not in best or l["lap_duration"] < best[d]["lap_duration"]:
            best[d] = l
    return best

def fetch_session(client, sess):
    key = sess["session_key"]
    q = f"session_key={key}"
    data = {}
    for ep in LIGHT_ENDPOINTS:
        data[ep] = client.get(ep, q)

    tel = {}
    for drv, lap in sorted(fastest_laps(data["laps"]).items()):
        start = parse_date(lap["date_start"])
        a = iso(start - dt.timedelta(seconds=TEL_PAD_S))
        b = iso(start + dt.timedelta(seconds=lap["lap_duration"] + TEL_PAD_S))
        win = f"{q}&driver_number={drv}&date>={a}&date<={b}"
        tel[str(drv)] = {
            "lap_number":   lap["lap_number"],
            "lap_duration": lap["lap_duration"],
            "lap_start":    lap["date_start"],
            "car_data":     columnar(client.get("car_data", win), "car_data"),
            "location":     columnar(client.get("location", win), "location"),
        }

    doc = {
        "format":     FORMAT_VERSION,
        "session":    sess,
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source":     BASE,
        **{ep: columnar(rows, ep) for ep, rows in data.items()},
        "fastest_lap_telemetry": tel,
    }
    empty = not data["laps"] or not data["position"]
    return doc, empty

def session_path(sess):
    day = sess["date_start"][:10]
    return ARCHIVE_DIR / str(sess["year"]) / f"{day}_{slug(sess['meeting_name'])}_{sess['type']}.json.gz"


# ── Completude ────────────────────────────────────────────────────────────────
def data_rows(doc):
    rows = lambda b: [dict(zip(b["cols"], r)) for r in b["rows"]]
    return rows(doc["laps"]), rows(doc["session_result"])

def completeness_fields(laps_results):
    got, exp = completeness_from_rows(*laps_results)
    ratio = round(got / exp, 4) if exp else 0.0
    return {"laps_archived": got, "laps_expected": exp, "completeness": ratio,
            "complete": ratio >= MIN_COMPLETENESS}

def reindex(index):
    for key, e in sorted(index["sessions"].items(), key=lambda kv: kv[1].get("date_start", "")):
        if not e.get("file") or not (ARCHIVE_DIR / e["file"]).exists():
            continue
        with gzip.open(ARCHIVE_DIR / e["file"], "rt", encoding="utf-8") as f:
            e.update(completeness_fields(data_rows(json.load(f))))
        log.info(f"{e['year']} {e['type']} {e['meeting_name']:<28} tours {e['laps_archived']}/{e['laps_expected']} "
                 f"({100 * e['completeness']:.1f} %){'' if e['complete'] else '  INCOMPLETE'}")
    save_index(index)
    return 0


def live_blocked_exit(err, where, remaining, client):
    log.error("ARRET : OpenF1 refuse l'acces car une seance F1 est en direct "
              "(401 'Live F1 session in progress'). " + (f"Interrompu sur {where}. " if where else "")
              + f"{remaining} session(s) non traitee(s), laissee(s) intacte(s) dans index.json ; "
              f"{client.count} requete(s) envoyee(s). Relancer apres la fin de la seance "
              f"(les sessions deja archivees seront sautees). Detail : {str(err)[:160]}")
    return EXIT_LIVE_SESSION


# ── Programme principal ──────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--years", type=int, nargs="+", help="saisons (defaut : en cours + precedente)")
    p.add_argument("--session-keys", type=int, nargs="+", help="limiter a ces sessions OpenF1")
    p.add_argument("--force", action="store_true", help="retelecharger meme si deja archivee")
    p.add_argument("--dry-run", action="store_true", help="lister sans telecharger")
    p.add_argument("--reindex", action="store_true",
                   help="recalculer la completude des fichiers deja archives (sans reseau)")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        stream=sys.stdout)
    now = dt.datetime.now(dt.timezone.utc)
    years = args.years or [now.year - 1, now.year]

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    lock = open(ARCHIVE_DIR / ".lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log.error("Une autre execution est en cours (verrou), arret.")
        return 1

    index  = load_index()
    if args.reindex:
        return reindex(index)
    client = RateLimitedClient()
    try:
        sessions = list_sessions(client, years)
    except LiveSessionBlocked as e:
        return live_blocked_exit(e, None, 0, client)
    if args.session_keys:
        sessions = [s for s in sessions if s["session_key"] in args.session_keys]

    todo = []
    for s in sessions:
        ok, why = needs_fetch(s, index, now, args.force)
        log.info(f"{'A FAIRE ' if ok else 'ignoree '} {s['year']} {s['type']} {s['meeting_name']:<32} "
                 f"cle {s['session_key']} - {why}")
        if ok:
            todo.append(s)

    est = sum(len(LIGHT_ENDPOINTS) + 2 * (22 if s["year"] >= 2026 else 20) for s in todo)
    log.info(f"{len(todo)} session(s) a recuperer, ~{est} requetes, ~{est / 25:.0f} min a 25 req/min")
    if args.dry_run:
        return 0

    failures = 0
    for i, s in enumerate(todo, 1):
        key = str(s["session_key"])
        entry = index["sessions"].get(key, {})
        t0, n0 = time.monotonic(), client.count
        try:
            try:
                doc, empty = fetch_session(client, s)
            except LiveSessionBlocked as e:
                # Session en cours et suivantes laissees intactes dans index.json
                return live_blocked_exit(e, f"[{i}/{len(todo)}] {s['year']} {s['type']} {s['meeting_name']}",
                                         len(todo) - i + 1, client)
            path = session_path(s)
            payload = gzip.compress(json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode(), 9)
            write_atomic(path, payload)
            entry = {**{k: s[k] for k in ("year", "type", "meeting_name", "date_start", "date_end",
                                           "meeting_key", "country_name", "location", "gmt_offset")},
                     "file": str(path.relative_to(ARCHIVE_DIR)),
                     "status": "empty" if empty else "ok",
                     "tries": entry.get("tries", 0) + 1,
                     "bytes": len(payload),
                     "drivers_with_telemetry": len(doc["fastest_lap_telemetry"]),
                     **completeness_fields(data_rows(doc)),
                     "fetched_at": doc["fetched_at"]}
            log.info(f"[{i}/{len(todo)}] {s['year']} {s['type']} {s['meeting_name']} : {entry['status']}, "
                     f"tours {entry['laps_archived']}/{entry['laps_expected']} "
                     f"({100 * entry['completeness']:.0f} %{'' if entry['complete'] else ', INCOMPLETE'}), "
                     f"{len(payload) / 1024:.0f} Ko, {client.count - n0} req, {time.monotonic() - t0:.0f}s")
        except Exception as e:
            failures += 1
            entry = {**entry, "year": s["year"], "type": s["type"], "meeting_name": s["meeting_name"],
                     "date_start": s["date_start"], "status": "error", "error": str(e)[:300],
                     "tries": entry.get("tries", 0) + 1}
            log.error(f"[{i}/{len(todo)}] {s['year']} {s['type']} {s['meeting_name']} : ECHEC {e}")
        index["sessions"][key] = entry
        save_index(index)

    log.info(f"Termine : {len(todo) - failures} ok/vide, {failures} echec(s), {client.count} requetes")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
