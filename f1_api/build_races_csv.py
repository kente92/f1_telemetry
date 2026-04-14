"""
build_races_csv.py — Construit le races.csv pour l'API F1
==========================================================
A lancer depuis le dossier f1_api/ :
    python build_races_csv.py --src "C:/Users/kente/Documents/Projet Python/F1 2023/f1db_csv"

Génère data/races.csv avec les colonnes :
    year, round, raceName, date, circuitName, country, location, lat, lng
"""

import argparse
from pathlib import Path
import pandas as pd

def build(src_dir: str):
    src = Path(src_dir)
    dst = Path(__file__).parent / "data"
    dst.mkdir(exist_ok=True)

    print(f"Source : {src}")

    # Circuits (lat/lng)
    print("Chargement circuits.csv...")
    circuits = pd.read_csv(src / "circuits.csv", na_values="\\N",
                           usecols=["circuitId","name","location","country","lat","lng"])
    circuits = circuits.rename(columns={"name": "circuitName"})
    print(f"  {len(circuits)} circuits")

    # Races
    print("Chargement races.csv...")
    races = pd.read_csv(src / "races.csv", na_values="\\N",
                        usecols=["raceId","year","round","circuitId","name","date"])
    races = races.rename(columns={"name": "raceName"})
    print(f"  {len(races)} courses brutes")

    # Merge
    df = races.merge(circuits[["circuitId","circuitName","location","country","lat","lng"]],
                     on="circuitId", how="left")

    # Garde uniquement les colonnes utiles
    df = df[["year","round","raceName","date","circuitName","country","location","lat","lng"]]
    df = df.sort_values(["year","round"]).reset_index(drop=True)

    # Vérification
    print(f"\n  {len(df)} courses au total")
    print(f"  Années : {int(df['year'].min())} → {int(df['year'].max())}")
    print(f"  Circuits avec lat/lng : {df['lat'].notna().sum()}/{len(df)}")
    print(f"\nSample :")
    print(df[["year","round","raceName","circuitName","lat","lng"]].head(3).to_string(index=False))

    out = dst / "races.csv"
    df.to_csv(out, index=False)
    print(f"\n✅ Sauvegardé → {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True,
                        help="Chemin vers le dossier f1db_csv Ergast")
    args = parser.parse_args()
    build(args.src)
