# 🏎️ F1 Telemetry Comparator

Application Streamlit de comparaison de télémétrie F1 entre deux pilotes.

## Fonctionnalités

- **Sélection libre** : circuit, année 1 & 2 (indépendantes), pilote 1 & 2
- **Télémétrie complète** : Vitesse, Accélérateur, Frein, Rapport
- **Delta de vitesse** : graphique différentiel coloré par pilote
- **Carte du circuit** : trajectoire colorée selon la vitesse
- **Stats résumé** : Vmax, vitesse moyenne, % plein gaz, % freinage
- **Cache local** : les sessions déjà téléchargées ne sont pas rechargées

## Installation

```bash
pip install -r requirements.txt
```

## Lancement

```bash
streamlit run app.py
```

L'application s'ouvre sur http://localhost:8501

## Structure

```
f1_telemetry/
├── app.py           # Application principale
├── requirements.txt
├── README.md
└── cache/           # Cache FastF1 (créé automatiquement)
```

## Notes

- Les données proviennent de **FastF1** (API officielle F1)
- La comparaison porte sur le **meilleur tour en course** de chaque pilote
- Les années peuvent être différentes : comparaison cross-saison possible
- Premier chargement d'une session : ~30–60s (téléchargement + cache)
- Chargements suivants : instantanés (cache local)

## Dépendances

| Package | Usage |
|---|---|
| `fastf1` | Données & télémétrie F1 |
| `streamlit` | Interface web |
| `plotly` | Graphiques interactifs |
| `pandas` / `numpy` | Traitement
des données |
