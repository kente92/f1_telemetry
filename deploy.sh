#!/bin/bash
# deploy.sh — Déploiement F1 App sur VPS
set -e

echo "🏎️  Déploiement F1 App..."

API_DIR="/var/www/f1_api"
FRONTEND_DIR="/var/www/f1_frontend"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

# Dossiers
echo "📁 Création des dossiers..."
sudo mkdir -p "$API_DIR/data" "$API_DIR/models" "$FRONTEND_DIR"
sudo chown -R ubuntu:ubuntu "$API_DIR" "$FRONTEND_DIR"

# API
echo "🐍 Déploiement de l'API..."
cp "$REPO_DIR/f1_api/main.py"          "$API_DIR/"
cp "$REPO_DIR/f1_api/requirements.txt" "$API_DIR/"
cp "$REPO_DIR/f1_api/data/"*.csv       "$API_DIR/data/" 2>/dev/null || true
cp "$REPO_DIR/models/"*.joblib         "$API_DIR/models/" 2>/dev/null || true

# Build React sur le VPS
echo "⚛️  Build du frontend React..."
cd "$REPO_DIR/f1_frontend"
npm install --silent
npm run build
sudo cp -r dist/. "$FRONTEND_DIR/"
cd "$REPO_DIR"

# Venv Python
echo "📦 Installation des dépendances Python..."
if [ ! -d "$API_DIR/venv" ]; then
    python3 -m venv "$API_DIR/venv"
fi
"$API_DIR/venv/bin/pip" install -q --upgrade pip
"$API_DIR/venv/bin/pip" install -q -r "$API_DIR/requirements.txt"

# Service systemd
echo "⚙️  Configuration du service..."
sudo cp "$REPO_DIR/f1_api/f1_api.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable f1_api

if sudo systemctl is-active --quiet f1_api; then
    echo "🔄 Redémarrage..."
    sudo systemctl restart f1_api
else
    echo "▶️  Démarrage..."
    sudo systemctl start f1_api
fi

sleep 3
if sudo systemctl is-active --quiet f1_api; then
    echo ""
    echo "✅ Déploiement terminé !"
    echo "   Site : https://f1.le-petit-labo-du-big-seb.fr"
else
    echo "❌ Erreur — vérifiez : sudo journalctl -u f1_api -n 50"
    exit 1
fi
