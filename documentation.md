# Documentation Technique - Scripts Python

Ce document détaille le fonctionnement, l'architecture et l'utilité de chaque script Python du projet MVP Help Center.

## Architecture Générale

Le projet repose sur une architecture **RAG (Retrieval-Augmented Generation)** simplifiée :

1. **Ingestion** : Les fichiers Excel sont convertis en vecteurs (`build_db.py`).
2. **Stockage** : Les vecteurs sont stockés dans une base locale ChromaDB.
3. **Serveur** : Une API FastAPI (`main.py`) reçoit les questions.
4. **Intelligence** : L'API cherche les vecteurs les plus proches et applique une logique de re-ranking pour privilégier les contenus riches (Tutoriels/Vidéos).
5. **Interface** : Une page web Vue.js affiche le chat.

---

## 1. `build_db.py` (Ingestion des Données)

**Rôle** : Construit la "mémoire" de l'IA.
Il lit les fichiers Excel, nettoie les données, et génère des embeddings (représentations mathématiques du sens) pour chaque question/tutoriel.

**Fonctionnement** :

- Lit `Questions...xlsx`, `Tutoriels...xlsx`, `Videos...xlsx`.
- Extrait `Title` et `Content`.
- Ajoute des métadonnées (`type="faq"`, `type="tuto"`, etc.).
- Sauvegarde le tout dans le dossier `./chroma_db`.

**Utilisation** :
À lancer une seule fois au début ou à chaque fois que vous modifiez les fichiers Excel.

```bash
python build_db.py
```

---

## 2. `main.py` (Serveur Backend & API)

**Rôle** : Cerveau de l'application.

**Fonctionnalités Clés** :

- **Endpoint `/chat`** : Traite les questions utilisateurs.
- **Recherche Sémantique** : Trouve les documents les plus proches de la question.
- **Re-ranking Intelligent** : Si un Tutoriel ou une Vidéo est presque aussi pertinent qu'une FAQ (écart de score < 0.2), il est priorisé car souvent plus complet.
- **Formatage HTML** : Préserve le HTML des tutoriels/vidéos, mais convertit le texte simple des FAQs pour le web.
- **Seuil de Pertinence** : Si le score de distance > 1.3, l'IA répond qu'elle ne sait pas (Fallback).

**Utilisation** :
Pour démarrer le serveur de l'application.

```bash
python main.py
```

Accès : `http://localhost:8000`

---

## 3. Frontend (`static/index.html`)

Interface utilisateur légère en **Vue.js 3** (sans étape de build complexe, utilise un CDN).

- Gère l'historique de chat.
- Envoie les requêtes à l'API.
- Affiche le HTML renvoyé (liens, iframes vidéo, mises en forme).
