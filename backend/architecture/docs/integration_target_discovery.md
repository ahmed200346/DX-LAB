# Intégration du Système Intelligent Target Discovery

Ce document explique comment configurer et exécuter le système multi-agent intégré avec le sous-système de découverte de cibles moléculaires (`intelligent_target_discovery`).

## Architecture de l'Intégration

Le système `intelligent_target_discovery` fonctionne de manière autonome avec son propre serveur FastAPI (par défaut sur le port `8000`).
Pour permettre à l'architecture principale (Planner & Executor) de communiquer avec ce système, un agent proxy (`discovery_agent.py`) a été créé.

Cet agent proxy :
1. Est enregistré auprès de l'architecture principale.
2. Reçoit les requêtes de l'Executor via le protocole ACP.
3. Transfère ces requêtes au serveur `intelligent_target_discovery` via des requêtes HTTP (`/generate`).
4. Gère les erreurs spécifiques (comme l'absence de clés API) et renvoie un message lisible à l'utilisateur.

## Configuration des Clés API

Le système `intelligent_target_discovery` requiert des clés API pour fonctionner (par exemple, pour faire appel aux modèles de langage via Groq ou OpenAI).

1. Accédez au dossier `backend/intelligent_target_discovery/`.
2. Assurez-vous d'avoir un fichier `.env` contenant vos clés API, ou configurez-les dans votre environnement.
   Exemple de fichier `.env` :
   ```env
   GROQ_API_KEY=votre_cle_api_groq
   ```
   
> **Remarque :** Si les clés API sont manquantes ou invalides, le système ne plantera pas. L'agent proxy interceptera l'erreur et affichera le message suivant dans l'interface :
> *"La requête a été transférée pour ce système afin d'être traitée mais le problème de clé API a interrompu le processus."*

## Exécution du Système Intégré

Pour exécuter l'ensemble du système, vous devez lancer trois terminaux distincts pour démarrer les différents services.

### 1. Démarrer les services dépendants (Docker)
Le système `intelligent_target_discovery` nécessite des bases de données (Qdrant pour les vecteurs, Redis pour le cache) et SearXNG. Ces services sont conteneurisés.
Assurez-vous que **Docker Desktop** est démarré sur votre machine.

Dans un **premier terminal**, lancez les conteneurs :
```bash
cd backend/intelligent_target_discovery
docker compose up -d
```
*(Attendez quelques secondes que les bases de données soient prêtes).*

### 2. Démarrer le serveur Target Discovery
Dans le même terminal (ou un deuxième), lancez le serveur FastAPI du sous-système :
```bash
python api_server.py
```
*(Le serveur démarrera sur `http://127.0.0.1:8000`)*

### 2. Démarrer le Serveur ACP Principal
Dans un **deuxième terminal**, lancez l'architecture principale (contenant le Planner, l'Executor, et le proxy Discovery) :
```bash
cd backend/architecture
python main.py
```
*(Le serveur démarrera sur le port `8001` et enregistrera tous les agents)*

### 3. Lancer l'Interface Utilisateur (Gradio)
Dans un **troisième terminal**, lancez l'application UI pour visualiser et interagir avec le système :
```bash
cd backend/architecture
python ui_app.py
```
*(L'interface sera accessible via votre navigateur, généralement sur `http://127.0.0.1:7860`)*

## Visualisation

Dans l'interface Gradio (`ui_app.py`) :
- **Onglet "Interaction Planner"** : Vous pouvez formuler vos requêtes (ex: "Trouve-moi des cibles moléculaires pour le cancer du poumon"). Le Planner associera la tâche à l'agent `intelligent_target_discovery` et l'Executor coordonnera l'exécution.
- **Onglet "Dashboard Métriques"** : Vous y trouverez une nouvelle colonne dédiée à l'agent `intelligent_target_discovery` affichant ses statistiques en temps réel (nombre de requêtes API envoyées, erreurs, etc.).
