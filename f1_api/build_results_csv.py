"""
build_results_csv.py — Construit results_full.csv et sprint_results_full.csv
=============================================================================
A lancer depuis le dossier f1_api/ :
    python build_results_csv.py --src "C:/Users/kente/Documents/Projet Python/F1 2023/f1db_csv"

Génère :
  data/results_full.csv       — résultats de course (toutes années)
  data/sprint_results_full.csv — résultats sprint
"""

import argparse
from pathlib import Path
import pandas as pd

def build(src_dir: str):
    src = Path(src_dir)
    dst = Path(__file__).parent / "data"
    dst.mkdir(exist_ok=True)

    print(f"Source : {src}")

    # ── Tables de référence ───────────────────────────────────────────
    print("\nChargement des tables de référence...")

    races = pd.read_csv(src / "races.csv", na_values="\\N",
                        usecols=["raceId","year","round","name"])
    races = races.rename(columns={"name": "raceName"})

    drivers = pd.read_csv(src / "drivers.csv", na_values="\\N",
                          usecols=["driverId","driverRef","forename","surname","nationality"])
    drivers["driverName"] = drivers["forename"] + " " + drivers["surname"]

    constructors = pd.read_csv(src / "constructors.csv", na_values="\\N",
                               usecols=["constructorId","constructorRef","name","nationality"])
    constructors = constructors.rename(columns={"name": "teamName", "nationality": "teamNationality"})

    status = pd.read_csv(src / "status.csv", na_values="\\N")

    # Génère drivers_codes.csv
    print("\nGénération drivers_codes.csv...")
    drivers_full = pd.read_csv(src / "drivers.csv", na_values="\\N",
                               usecols=["driverRef","code"])
    drivers_full = drivers_full.dropna(subset=["code"])
    drivers_full.to_csv(dst / "drivers_codes.csv", index=False)
    print(f"  ✅ {len(drivers_full)} codes sauvegardés")

    def process_results(csv_name, label):
        print(f"\nTraitement {csv_name}...")
        df = pd.read_csv(src / csv_name, na_values="\\N",
                         usecols=["raceId","driverId","constructorId","number",
                                  "grid","positionOrder","points","laps",
                                  "statusId","fastestLapTime"])

        # Joins
        df = df.merge(races,        on="raceId",        how="left")
        df = df.merge(drivers[["driverId","driverRef","driverName","nationality"]],
                      on="driverId",  how="left")
        df = df.merge(constructors[["constructorId","constructorRef","teamName"]],
                      on="constructorId", how="left")
        df = df.merge(status, on="statusId", how="left")

        # Nettoyage
        df["positionOrder"] = pd.to_numeric(df["positionOrder"], errors="coerce")
        df["grid"]          = pd.to_numeric(df["grid"],          errors="coerce").fillna(0).astype(int)
        df["points"]        = pd.to_numeric(df["points"],        errors="coerce").fillna(0)
        df["fastestLapTime"]= df["fastestLapTime"].fillna("")

        # Colonnes finales
        df = df[["year","round","raceName","positionOrder","driverRef","driverName",
                 "nationality","constructorRef","teamName","grid","points",
                 "laps","status","fastestLapTime"]]
        df = df.sort_values(["year","round","positionOrder"]).reset_index(drop=True)

        out = dst / f"{label}.csv"
        df.to_csv(out, index=False)
        print(f"  ✅ {len(df)} lignes → {out}")
        print(f"  Années : {int(df['year'].min())} → {int(df['year'].max())}")
        return df

    process_results("results.csv",        "results_full")

    sprint_path = src / "sprint_results.csv"
    if sprint_path.exists():
        process_results("sprint_results.csv", "sprint_results_full")
    else:
        print("\n⚠️  sprint_results.csv non trouvé — ignoré")

    print("\n✅ Terminé !")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True)
    args = parser.parse_args()
    build(args.src)
