# 🏎️ F1 App — Résultats · Télémétrie · Prédictions

Application Streamlit complète autour de la Formule 1 : résultats de course, analyse de télémétrie, dataviz historique et prédictions de podium.

---

## Fonctionnalités

### 🏎️ Onglet Course & Télémétrie

**Résultats de course**
- Podium visuel avec couleurs officielles des écuries
- Tableau complet (position, pilote, écurie, grille, statut, points, meilleur tour)

**Télémétrie — Meilleur tour par pilote**
- Multiselect avec tous les pilotes cochés par défaut (décocher pour masquer)
- 3 graphiques interactifs : Vitesse (km/h) / Frein (%) / Rapport
- Chargement progressif avec barre de progression

**Carte du circuit — Delta vitesse**
- Deux menus déroulants indépendants pour choisir les deux pilotes
- Tracé coloré : bleu = pilote 1 plus rapide, rouge = pilote 2 plus rapide

**⏱️ Chronos tour par tour**
- Comparaison des temps au tour sur l'ensemble de la course
- Marqueurs visuels des arrêts aux stands (triangles ▲)
- Safety Car et stratégies pneus apparaissent clairement

**🌍 Carte mondiale des circuits F1**
- Tous les Grands Prix depuis 1950
- Slider double pour filtrer par plage d'années
- Choix de projection cartographique (natural earth, mercator, orthographic…)
- Points colorés par année pour visualiser l'expansion géographique du sport

**🎂 Course le jour de ton anniversaire**
- Date picker → tableau de toutes les courses disputées ce jour/mois dans l'histoire
- Carte géographique des circuits correspondants

---

### 🔮 Onglet Prédictions

- Sélection : saison, Grand Prix, numéro de manche
- **Sans grille** : prédiction pré-qualifications (disponible dès le jeudi)
- **Avec grille** : post-qualifications — récupération automatique via Jolpica ou saisie manuelle
- **🌦️ Météo** : récupération via Open-Meteo (gratuit, sans clé) ou case "Forcer pluie"
- Affichage : Vainqueur · Podium · Top 6 · Classement complet 20 pilotes
- Graphique comparatif Random Forest / Decision Tree / SVC

---

## Installation

```bash
pip install -r requirements.txt
```

> Sur VPS, créer le dossier de cache FastF1 :
> ```bash
> mkdir -p /var/cache/f1
> ```
> L'app détecte automatiquement si `/var/cache/f1` est accessible en écriture
> et bascule sur `/tmp` sinon (Streamlit Cloud, Heroku).

## Lancement

```bash
streamlit run app_streamlit.py       # Streamlit Cloud / VPS
streamlit run app.py                 # Local (cache dans ./cache/)
```

L'application s'ouvre sur http://localhost:8501

---

## Structure

```
f1_telemetry/
├── app_streamlit.py     # App complète — Streamlit Cloud / VPS
├── app.py               # App télémétrie seule — usage local / Heroku
├── requirements.txt
├── README.md
└── models/              # Modèles pré-entraînés (générer via f1_predictor/)
    ├── f1_model_with_grid.joblib
    └── f1_model_no_grid.joblib
```

---

## Modèles de prédiction

Les modèles sont entraînés via le projet `f1_predictor/` et committés dans `models/`.
À ré-entraîner en début de saison ou après un changement réglementaire majeur (ex : 2026).

**Algorithmes :** Random Forest · Decision Tree · SVC
**Rééchantillonnage :** RandomOverSampler (imbalanced-learn)
**Features :** standings pilote & écurie + grille (optionnel) + météo (pluie/sec)

```bash
cd f1_predictor/
python ingest.py --from-year 2018     # Met à jour les données
python model.py train --train-until 2025
```

---

## APIs utilisées

| API | Usage | Clé requise |
|---|---|---|
| **FastF1** | Télémétrie, résultats, GPS | Non |
| **Jolpica** (ex-Ergast) | Standings, qualifications, historique | Non |
| **Open-Meteo** | Prévisions météo | Non |

---

## Dépendances

| Package | Usage |
|---|---|
| `fastf1` | Données & télémétrie F1 |
| `streamlit` | Interface web |
| `plotly` | Graphiques interactifs |
| `pandas` / `numpy` | Traitement des données |
| `scikit-learn` | Modèles RF, DT, SVC |
| `imbalanced-learn` | RandomOverSampler |
| `joblib` | Sauvegarde/chargement modèles |
| `requests` | Appels API Jolpica & Open-Meteo |

---

## Cache FastF1

| Environnement | Dossier | Persistance |
|---|---|---|
| VPS | `/var/cache/f1` | ✅ Permanente |
| Streamlit Cloud | `/tmp` | ⚠️ Perdu au redémarrage |
| Local | `./cache/` | ✅ Permanente |

Premier chargement d'une session : ~30–60s. Chargements suivants : instantanés.
