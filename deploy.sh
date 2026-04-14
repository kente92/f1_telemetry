#!/bin/bash
# deploy.sh — Déploiement F1 App sur VPS
# Usage : bash deploy.sh

set -e

echo "🏎️  Déploiement F1 App..."

# ── Chemins ────────────────────────────────────────────────────────────────
API_DIR="/var/www/f1_api"
FRONTEND_DIR="/var/www/f1_frontend"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Création des dossiers ──────────────────────────────────────────────────
echo "📁 Création des dossiers..."
sudo mkdir -p "$API_DIR/data"
sudo mkdir -p "$API_DIR/models"
sudo mkdir -p "$FRONTEND_DIR"
sudo chown -R ubuntu:ubuntu "$API_DIR" "$FRONTEND_DIR"

# ── Déploiement API ────────────────────────────────────────────────────────
echo "🐍 Déploiement de l'API..."
cp "$REPO_DIR/f1_api/main.py"          "$API_DIR/"
cp "$REPO_DIR/f1_api/requirements.txt" "$API_DIR/"

# CSV data
echo "📊 Copie des données CSV..."
cp "$REPO_DIR/f1_api/data/"*.csv "$API_DIR/data/" 2>/dev/null || true

# Modèles ML
echo "🤖 Copie des modèles..."
cp "$REPO_DIR/models/"*.joblib "$API_DIR/models/" 2>/dev/null || true

# ── Déploiement Frontend ───────────────────────────────────────────────────
echo "⚛️  Déploiement du frontend..."
cp -r "$REPO_DIR/f1_frontend/dist/." "$FRONTEND_DIR/"

# ── Venv + dépendances ─────────────────────────────────────────────────────
echo "📦 Installation des dépendances Python..."
if [ ! -d "$API_DIR/venv" ]; then
    python3 -m venv "$API_DIR/venv"
fi
"$API_DIR/venv/bin/pip" install -q --upgrade pip
"$API_DIR/venv/bin/pip" install -q -r "$API_DIR/requirements.txt"

# ── Service systemd ────────────────────────────────────────────────────────
echo "⚙️  Configuration du service systemd..."
sudo cp "$REPO_DIR/f1_api/f1_api.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable f1_api

# Redémarre si déjà actif, sinon démarre
if sudo systemctl is-active --quiet f1_api; then
    echo "🔄 Redémarrage du service..."
    sudo systemctl restart f1_api
else
    echo "▶️  Démarrage du service..."
    sudo systemctl start f1_api
fi

# ── Vérification ───────────────────────────────────────────────────────────
sleep 3
if sudo systemctl is-active --quiet f1_api; then
    echo ""
    echo "✅ Déploiement terminé !"
    echo "   API    : http://localhost:8001/api/health"
    echo "   Site   : https://f1-analyse.le-petit-labo-du-big-seb.fr"
else
    echo "❌ Le service ne démarre pas. Vérifiez les logs :"
    echo "   sudo journalctl -u f1_api -n 50"
    exit 1
fi
