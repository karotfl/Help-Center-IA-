# MVP Help Center Agent

Ce projet est un Proof of Concept (POC) d'un agent conversationnel intelligent destiné à aider les étudiants en répondant à leurs questions à partir d'une base de connaissances (FAQ, Tutoriels, Vidéos).

## 🚀 Démarrage Rapide

### Prérequis

- Python 3.9+
- Pip

### Installation

1. Installez les dépendances :

    ```bash
    pip install -r requirements.txt
    ```

2. Construisez la base de données (si ce n'est pas déjà fait) :

    ```bash
    python build_db.py
    ```

### Lancer l'Application

Lancez le serveur backend :

```bash
python main.py
```

Ouvrez ensuite votre navigateur sur [http://localhost:8000](http://localhost:8000).

## 📁 Structure du Projet

- **`main.py`** : Le serveur API (FastAPI) qui gère les requêtes de chat.
- **`build_db.py`** : Script d'ingestion des données Excel vers la base vectorielle ChromaDB.
- **`static/index.html`** : L'interface utilisateur (Vue.js).
- **`data/`** : Dossier contenant les fichiers Excel sources.
- **`chroma_db/`** : Dossier contenant la base de données vectorielle (généré automatiquement).
- **`documentation.md`** : Documentation technique détaillée des scripts.

## 🛠 Fonctionnalités

- **Recherche Sémantique** : Comprend le sens des questions, pas juste les mots-clés.
- **Support Multimédia** : Rendu HTML pour les tutoriels et vidéos.
- **Fallback Intelligent** : Redirige vers le support humain si l'IA n'est pas sûre.
